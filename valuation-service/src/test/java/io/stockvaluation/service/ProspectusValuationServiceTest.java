package io.stockvaluation.service;

import io.stockvaluation.dto.BasicInfoDataDTO;
import io.stockvaluation.dto.CompanyDataDTO;
import io.stockvaluation.dto.CompanyDriveDataDTO;
import io.stockvaluation.dto.FinancialDataDTO;
import io.stockvaluation.dto.SegmentResponseDTO;
import io.stockvaluation.dto.SegmentWeightedParameters;
import io.stockvaluation.dto.ValuationOutputDTO;
import io.stockvaluation.dto.valuationoutput.AssumptionTransparencyDTO;
import io.stockvaluation.dto.valuationoutput.CompanyDTO;
import io.stockvaluation.form.FinancialDataInput;
import io.stockvaluation.provider.prospectus.ProspectusPacketValidationResult;
import io.stockvaluation.provider.prospectus.ProspectusPacketValidator;
import io.stockvaluation.provider.prospectus.ProspectusTestPackets;
import io.stockvaluation.provider.prospectus.ProspectusValuationRequest;
import io.stockvaluation.provider.prospectus.ProspectusValuationResult;
import io.stockvaluation.utils.SegmentParameterContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ProspectusValuationServiceTest {

    @AfterEach
    void tearDown() {
        SegmentParameterContext.clear();
    }

    @Test
    void rejectsUnreviewedPacketsBeforeValuation() {
        ProspectusCompanyDataAssembler assembler = mock(ProspectusCompanyDataAssembler.class);
        CommonService commonService = mock(CommonService.class);
        ValuationTemplateService templateService = mock(ValuationTemplateService.class);
        ValuationOutputService outputService = mock(ValuationOutputService.class);
        ProspectusValuationService service = new ProspectusValuationService(
                new ProspectusPacketValidator(),
                assembler,
                commonService,
                templateService,
                outputService);
        var packet = ProspectusTestPackets.reviewedPacket();
        packet.setReviewStatus("review_required");

        IllegalArgumentException exception = assertThrows(
                IllegalArgumentException.class,
                () -> service.value(new ProspectusValuationRequest(packet)));

        assertEquals("prospectus packet is blocked: unreviewed_packet", exception.getMessage());
        verify(outputService, never()).getValuationOutput(any(), any(), any());
    }

    @Test
    void valuesReviewedPacketThroughDeterministicOutputServiceWithoutProviderLookup() {
        ProspectusCompanyDataAssembler assembler = mock(ProspectusCompanyDataAssembler.class);
        CommonService commonService = mock(CommonService.class);
        ValuationTemplateService templateService = mock(ValuationTemplateService.class);
        ValuationOutputService outputService = mock(ValuationOutputService.class);
        ProspectusValuationService service = new ProspectusValuationService(
                new ProspectusPacketValidator(),
                assembler,
                commonService,
                templateService,
                outputService);
        var packet = ProspectusTestPackets.reviewedPacket();
        CompanyDataDTO companyData = companyData();
        ValuationOutputDTO output = new ValuationOutputDTO();
        output.setCompanyName("Space Exploration Technologies Corp.");
        when(assembler.assemble(packet)).thenReturn(companyData);
        when(templateService.determineTemplate(any(), eq(companyData))).thenReturn(null);
        when(outputService.getValuationOutput(eq("SPCX"), any(), eq(null))).thenReturn(output);

        ProspectusValuationResult result = service.value(new ProspectusValuationRequest(packet));

        assertEquals("valued", result.status());
        assertEquals("offering_price", result.priceBasis());
        assertEquals(output, result.valuation());
        assertEquals("primary_filing", result.sourceProvenance().getSourceClass());
        assertEquals("sec-edgar-prospectus", result.sourceProvenance().getProvider());
        assertEquals("not_required", result.sourceQualityGate().getStatus());
        verify(assembler).assemble(packet);
        verify(commonService, never()).applySegmentWeightedParameters(any(), any(), anyList());
        verify(outputService).getValuationOutput(eq("SPCX"), any(), eq(null));
    }

    @Test
    void postOfferingSharesWithoutProFormaCashReturnChallengedBasis() {
        ProspectusCompanyDataAssembler assembler = mock(ProspectusCompanyDataAssembler.class);
        CommonService commonService = mock(CommonService.class);
        ValuationTemplateService templateService = mock(ValuationTemplateService.class);
        ValuationOutputService outputService = mock(ValuationOutputService.class);
        ProspectusValuationService service = new ProspectusValuationService(
                new ProspectusPacketValidator(),
                assembler,
                commonService,
                templateService,
                outputService);
        var packet = ProspectusTestPackets.reviewedPacket();
        packet.getOffering().setNetProceeds(null);
        packet.getOffering().setProceedsBasis(null);
        CompanyDataDTO companyData = companyData();
        ValuationOutputDTO output = valuationOutput();
        when(assembler.assemble(packet)).thenReturn(companyData);
        when(templateService.determineTemplate(any(), eq(companyData))).thenReturn(null);
        when(outputService.getValuationOutput(eq("SPCX"), any(), eq(null))).thenReturn(output);

        ProspectusValuationResult result = service.value(new ProspectusValuationRequest(packet));

        assertEquals("pro_forma_cash_missing", result.valuationBasisStatus());
        assertEquals("challenged_valuation_case", result.valuationCaseStatus());
        assertEquals("pro_forma_cash_missing", result.valuation().getAssumptionTransparency().getValuationBasisStatus());
        assertEquals("challenged_valuation_case", result.valuation().getAssumptionTransparency().getValuationCaseStatus());
        assertTrue(result.valuation().getAssumptionTransparency().getBaselineWarnings().stream()
                .anyMatch(warning -> warning.contains("post-offering shares require pro-forma cash")));
        assertTrue(result.valuation().getAssumptionTransparency().getUnsupportedBaselineDrivers().stream()
                .anyMatch(issue -> "cash_share_basis".equals(issue.getField())
                        && "pro_forma_cash_missing".equals(issue.getStatus())));
    }

    @Test
    void disclosedNetProceedsAreAddedToCashAndReturnCleanProFormaBasis() {
        ProspectusCompanyDataAssembler assembler = mock(ProspectusCompanyDataAssembler.class);
        CommonService commonService = mock(CommonService.class);
        ValuationTemplateService templateService = mock(ValuationTemplateService.class);
        ValuationOutputService outputService = mock(ValuationOutputService.class);
        ProspectusValuationService service = new ProspectusValuationService(
                new ProspectusPacketValidator(),
                assembler,
                commonService,
                templateService,
                outputService);
        var packet = ProspectusTestPackets.reviewedPacket();
        packet.getOffering().setNetProceeds(74_000_000_000.0);
        packet.getOffering().setProceedsBasis("net_proceeds_disclosed");
        CompanyDataDTO companyData = companyData();
        companyData.getFinancialDataDTO().setCashAndMarkablTTM(24_747_000_000.0);
        companyData.getFinancialDataDTO().setCashAndMarkablLTM(24_747_000_000.0);
        ValuationOutputDTO output = valuationOutput();
        when(assembler.assemble(packet)).thenReturn(companyData);
        when(templateService.determineTemplate(any(), eq(companyData))).thenReturn(null);
        when(outputService.getValuationOutput(eq("SPCX"), any(), eq(null))).thenAnswer(invocation -> {
            FinancialDataInput projectionInput = invocation.getArgument(1);
            assertEquals(98_747_000_000.0, projectionInput.getFinancialDataDTO().getCashAndMarkablTTM(), 0.001);
            assertEquals(98_747_000_000.0, projectionInput.getFinancialDataDTO().getCashAndMarkablLTM(), 0.001);
            return output;
        });

        ProspectusValuationResult result = service.value(new ProspectusValuationRequest(packet));

        assertEquals("clean_pro_forma_basis", result.valuationBasisStatus());
        assertEquals("clean_valuation_case", result.valuationCaseStatus());
        assertEquals("net_proceeds_disclosed", result.proceedsBasis());
        assertEquals("clean_pro_forma_basis", result.valuation().getAssumptionTransparency().getValuationBasisStatus());
    }

    @Test
    void grossProceedsEstimateDoesNotReturnCleanProFormaBasis() {
        ProspectusCompanyDataAssembler assembler = mock(ProspectusCompanyDataAssembler.class);
        CommonService commonService = mock(CommonService.class);
        ValuationTemplateService templateService = mock(ValuationTemplateService.class);
        ValuationOutputService outputService = mock(ValuationOutputService.class);
        ProspectusValuationService service = new ProspectusValuationService(
                new ProspectusPacketValidator(),
                assembler,
                commonService,
                templateService,
                outputService);
        var packet = ProspectusTestPackets.reviewedPacket();
        packet.getOffering().setSharesOffered(555_555_555.0);
        packet.getOffering().setNetProceeds(null);
        packet.getOffering().setProceedsBasis(null);
        CompanyDataDTO companyData = companyData();
        ValuationOutputDTO output = valuationOutput();
        when(assembler.assemble(packet)).thenReturn(companyData);
        when(templateService.determineTemplate(any(), eq(companyData))).thenReturn(null);
        when(outputService.getValuationOutput(eq("SPCX"), any(), eq(null))).thenReturn(output);

        ProspectusValuationResult result = service.value(new ProspectusValuationRequest(packet));

        assertEquals("gross_proceeds_estimate_only", result.valuationBasisStatus());
        assertEquals("challenged_valuation_case", result.valuationCaseStatus());
        assertEquals("gross_proceeds_estimate_only", result.proceedsBasis());
    }

    @Test
    void valuesSpaceXStyleSegmentMixWithRevenueWeightsInsteadOfFirstMappedSegment() {
        ProspectusCompanyDataAssembler assembler = mock(ProspectusCompanyDataAssembler.class);
        CommonService commonService = mock(CommonService.class);
        ValuationTemplateService templateService = mock(ValuationTemplateService.class);
        ValuationOutputService outputService = mock(ValuationOutputService.class);
        ProspectusValuationService service = new ProspectusValuationService(
                new ProspectusPacketValidator(),
                assembler,
                commonService,
                templateService,
                outputService);
        var packet = ProspectusTestPackets.spaceXSegmentMixPacket();
        CompanyDataDTO companyData = companyData();
        ValuationOutputDTO output = valuationOutput();
        when(assembler.assemble(packet)).thenReturn(companyData);
        when(templateService.determineTemplate(any(), eq(companyData))).thenReturn(null);
        when(outputService.getValuationOutput(eq("SPCX"), any(), eq(null))).thenAnswer(invocation -> {
            FinancialDataInput projectionInput = invocation.getArgument(1);
            SegmentResponseDTO projectionSegments = projectionInput.getSegments();
            assertNotNull(projectionSegments);
            assertEquals(2, projectionSegments.getSegments().size());
            assertEquals("telecom-services", projectionSegments.getSegments().get(0).getSector());
            assertEquals(0.695, projectionSegments.getSegments().get(0).getRevenueShare(), 0.0001);
            assertEquals("aerospace-defense", projectionSegments.getSegments().get(1).getSector());
            assertEquals(0.305, projectionSegments.getSegments().get(1).getRevenueShare(), 0.0001);
            assertTrue(projectionSegments.getSegments().stream()
                    .noneMatch(segment -> segment.getSector() == null));
            return output;
        });
        doAnswer(invocation -> {
            FinancialDataInput input = invocation.getArgument(0);
            SegmentResponseDTO segments = input.getSegments();
            assertNotNull(segments);
            assertEquals(3, segments.getSegments().size());
            assertEquals("telecom-services", segments.getSegments().get(0).getSector());
            assertEquals(0.61, segments.getSegments().get(0).getRevenueShare(), 0.0001);
            assertEquals("aerospace-defense", segments.getSegments().get(1).getSector());
            assertEquals(0.22, segments.getSegments().get(1).getRevenueShare(), 0.0001);
            assertNull(segments.getSegments().get(2).getSector());
            assertEquals(0.17, segments.getSegments().get(2).getRevenueShare(), 0.0001);
            SegmentParameterContext.setParameters(spaceXWeightedParameters());
            return null;
        }).when(commonService).applySegmentWeightedParameters(any(FinancialDataInput.class), eq(companyData), anyList());

        ProspectusValuationResult result = service.value(new ProspectusValuationRequest(packet));

        AssumptionTransparencyDTO transparency = result.valuation().getAssumptionTransparency();
        assertNotNull(transparency);
        assertEquals("segment_weighted_baseline", transparency.getBaselineQuality());
        assertEquals("challenged_baseline", transparency.getBaselineUseStatus());
        assertTrue(transparency.isSegmentAware());
        assertEquals(3, transparency.getSegmentCount());
        assertEquals(83.0, transparency.getSegmentCoveragePct(), 0.001);
        assertTrue(transparency.getMappedIndustries().contains("Telecom. Services"));
        assertTrue(transparency.getMappedIndustries().contains("Aerospace/Defense"));
        assertEquals(6.771385,
                ((Number) transparency.getWeightedBaselineAssumptions().get("initialCostOfCapital")).doubleValue(),
                0.000001);
        assertTrue(transparency.getBaselineWarnings().stream()
                .anyMatch(warning -> warning.contains("partial segment coverage")));
        assertTrue(transparency.getBaselineWarnings().stream()
                .anyMatch(warning -> warning.contains("material unmapped prospectus revenue")));
        assertTrue(transparency.getUnsupportedBaselineDrivers().stream()
                .anyMatch(issue -> "segments".equals(issue.getField())
                        && "segment_mapping_material_gap".equals(issue.getStatus())));
        assertFalse(transparency.getTargetOperatingMarginSource().contains("Single-industry"));
    }

    @Test
    void labelsProspectusSegmentFailureAsTypedWarningNotMechanicalOnly() {
        ProspectusCompanyDataAssembler assembler = mock(ProspectusCompanyDataAssembler.class);
        CommonService commonService = mock(CommonService.class);
        ValuationTemplateService templateService = mock(ValuationTemplateService.class);
        ValuationOutputService outputService = mock(ValuationOutputService.class);
        ProspectusValuationService service = new ProspectusValuationService(
                new ProspectusPacketValidator(),
                assembler,
                commonService,
                templateService,
                outputService);
        var packet = ProspectusTestPackets.reviewedPacket();
        packet.setSegments(List.of(
                ProspectusTestPackets.segment("Connectivity", 240_000_000.0, 0.2, "telecom-services", "Telecom. Services", "medium"),
                ProspectusTestPackets.segment("Space", 240_000_000.0, 0.2, "aerospace-defense", "Aerospace/Defense", "medium"),
                ProspectusTestPackets.segment("AI", 720_000_000.0, 0.6, null, null, "low")));
        CompanyDataDTO companyData = companyData();
        ValuationOutputDTO output = valuationOutput();
        when(assembler.assemble(packet)).thenReturn(companyData);
        when(templateService.determineTemplate(any(), eq(companyData))).thenReturn(null);
        when(outputService.getValuationOutput(eq("SPCX"), any(), eq(null))).thenAnswer(invocation -> {
            FinancialDataInput projectionInput = invocation.getArgument(1);
            assertNull(projectionInput.getSegments());
            return output;
        });
        doAnswer(invocation -> {
            FinancialDataInput input = invocation.getArgument(0);
            assertEquals(3, input.getSegments().getSegments().size());
            SegmentWeightedParameters blocked = new SegmentWeightedParameters();
            blocked.setSegmentWeighted(false);
            blocked.setSegmentCount(3);
            blocked.setBaselineQuality("segment_mapping_blocked");
            blocked.setSegmentCoveragePct(40.0);
            blocked.setSegmentWarnings(List.of("Prospectus segment mapped revenue coverage 40.00% is below the 80% threshold."));
            SegmentParameterContext.setParameters(blocked);
            return null;
        }).when(commonService).applySegmentWeightedParameters(any(FinancialDataInput.class), eq(companyData), anyList());

        ProspectusValuationResult result = service.value(new ProspectusValuationRequest(packet));

        AssumptionTransparencyDTO transparency = result.valuation().getAssumptionTransparency();
        assertNotNull(transparency);
        assertEquals("segment_mapping_blocked", transparency.getBaselineQuality());
        assertEquals("challenged_baseline", transparency.getBaselineUseStatus());
        assertFalse(transparency.isSegmentAware());
        assertEquals(40.0, transparency.getSegmentCoveragePct(), 0.001);
        assertTrue(transparency.getBaselineWarnings().stream()
                .anyMatch(warning -> warning.contains("below the 80% threshold")));
        assertTrue(transparency.getBaselineWarnings().stream()
                .anyMatch(warning -> warning.contains("material unmapped prospectus revenue")));
    }

    @Test
    void validatorResultExposesBlockingCodesForMcpAndControllerPayloads() {
        var packet = ProspectusTestPackets.reviewedPacket();
        packet.setReviewStatus("review_required");

        ProspectusPacketValidationResult result = new ProspectusPacketValidator().validateForValuation(packet);

        assertEquals("blocked", result.status());
        assertEquals("unreviewed_packet", result.blockingIssues().get(0).code());
    }

    private static ValuationOutputDTO valuationOutput() {
        ValuationOutputDTO output = new ValuationOutputDTO();
        output.setCompanyName("Space Exploration Technologies Corp.");
        output.setCurrency("USD");
        output.setStockCurrency("USD");
        output.setIndustryUs("aerospace-defense");
        output.setIndustryGlobal("aerospace-defense");
        CompanyDTO company = new CompanyDTO();
        company.setEstimatedValuePerShare(42.0);
        company.setPrice(135.0);
        output.setCompanyDTO(company);
        return output;
    }

    private static SegmentWeightedParameters spaceXWeightedParameters() {
        SegmentWeightedParameters params = new SegmentWeightedParameters();
        params.setWeightedRevenueNextYear(33.0);
        params.setWeightedCompoundAnnualGrowth2_5(33.0);
        params.setWeightedOperatingMarginNextYear(-13.9);
        params.setWeightedTargetPreTaxOperatingMargin(18.0);
        params.setConvergenceYearMargin(5.0);
        params.setWeightedSalesToCapitalYears1To5(2.5);
        params.setWeightedSalesToCapitalYears6To10(2.3);
        params.setWeightedInitialCostCapital(677.1385);
        params.setRiskFreeRate(4.5);
        params.setSegmentWeighted(true);
        params.setSegmentCount(3);
        params.setBaselineQuality("segment_weighted_baseline");
        params.setSegmentCoveragePct(83.0);
        params.setSegmentWarnings(List.of(
                "Prospectus segment weighting used partial segment coverage: 83.00% mapped; unmapped revenue stayed explicit."));

        SegmentWeightedParameters.SectorParameters telecom = new SegmentWeightedParameters.SectorParameters();
        telecom.setSectorName("telecom-services");
        telecom.setRevenueShare(0.695);
        telecom.setIndustryAsPerExcel("Telecom. Services");
        SegmentWeightedParameters.SectorParameters aerospace = new SegmentWeightedParameters.SectorParameters();
        aerospace.setSectorName("aerospace-defense");
        aerospace.setRevenueShare(0.305);
        aerospace.setIndustryAsPerExcel("Aerospace/Defense");
        params.setSectorParameters("telecom-services", telecom);
        params.setSectorParameters("aerospace-defense", aerospace);
        return params;
    }

    private static CompanyDataDTO companyData() {
        BasicInfoDataDTO basic = new BasicInfoDataDTO();
        basic.setTicker("SPCX");
        basic.setCompanyName("Space Exploration Technologies Corp.");
        basic.setCountryOfIncorporation("United States");
        basic.setCurrency("USD");
        basic.setStockCurrency("USD");
        basic.setIndustryUs("aerospace-defense");
        basic.setIndustryGlobal("aerospace-defense");
        FinancialDataDTO financial = new FinancialDataDTO();
        financial.setStockPrice(135.0);
        CompanyDriveDataDTO drive = new CompanyDriveDataDTO();
        drive.setRevenueNextYear(0.1);
        drive.setOperatingMarginNextYear(0.1);
        drive.setCompoundAnnualGrowth2_5(0.08);
        drive.setTargetPreTaxOperatingMargin(0.12);
        drive.setSalesToCapitalYears1To5(2.0);
        drive.setSalesToCapitalYears6To10(2.0);
        drive.setRiskFreeRate(4.6);
        drive.setInitialCostCapital(0.08);
        CompanyDataDTO data = new CompanyDataDTO();
        data.setBasicInfoDataDTO(basic);
        data.setFinancialDataDTO(financial);
        data.setCompanyDriveDataDTO(drive);
        return data;
    }
}
