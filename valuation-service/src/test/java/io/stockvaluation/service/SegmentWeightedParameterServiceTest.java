package io.stockvaluation.service;

import io.stockvaluation.domain.SectorMapping;
import io.stockvaluation.domain.IndustryAveragesUS;
import io.stockvaluation.domain.IndustryAveragesGlobal;
import io.stockvaluation.domain.InputStatDistribution;
import io.stockvaluation.dto.BasicInfoDataDTO;
import io.stockvaluation.dto.CompanyDataDTO;
import io.stockvaluation.dto.CompanyDriveDataDTO;
import io.stockvaluation.dto.SegmentWeightedParameters;
import io.stockvaluation.dto.SegmentResponseDTO;
import io.stockvaluation.form.FinancialDataInput;
import io.stockvaluation.form.SectorParameterOverride;
import io.stockvaluation.repository.IndustryAveragesGlobalRepository;
import io.stockvaluation.repository.IndustryAveragesUSRepository;
import io.stockvaluation.repository.InputStatRepository;
import io.stockvaluation.repository.SectorMappingRepository;
import io.stockvaluation.utils.SegmentParameterContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Optional;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class SegmentWeightedParameterServiceTest {

    @Mock
    private SectorMappingRepository sectorMappingRepository;
    @Mock
    private IndustryAveragesUSRepository industryAvgUSRepository;
    @Mock
    private IndustryAveragesGlobalRepository industryAvgGloRepository;
    @Mock
    private InputStatRepository inputStatRepository;

    @InjectMocks
    private SegmentWeightedParameterService service;

    @AfterEach
    void tearDown() {
        SegmentParameterContext.clear();
    }

    @Test
    void applySegmentWeightedParameters_singleSegment_returnsWithoutChanges() {
        FinancialDataInput input = baselineInput();
        input.setSegments(new SegmentResponseDTO(List.of(
                new SegmentResponseDTO.Segment("software", "tech", List.of("core"), 1.0, 1.0, 0.2)
        )));

        Double revenueBefore = input.getRevenueNextYear();
        Double marginBefore = input.getTargetPreTaxOperatingMargin();
        Double stcBefore = input.getSalesToCapitalYears1To5();

        service.applySegmentWeightedParameters(input, companyData("United States"), List.of(), 0.04);

        assertEquals(revenueBefore, input.getRevenueNextYear());
        assertEquals(marginBefore, input.getTargetPreTaxOperatingMargin());
        assertEquals(stcBefore, input.getSalesToCapitalYears1To5());
        assertNull(SegmentParameterContext.getParameters());
        verifyNoInteractions(sectorMappingRepository, industryAvgUSRepository, industryAvgGloRepository, inputStatRepository);
    }

    @Test
    void applySegmentWeightedParameters_twoSegments_withValidOverride_setsSectorContext() {
        FinancialDataInput input = baselineInput();
        input.setSegments(new SegmentResponseDTO(List.of(
                new SegmentResponseDTO.Segment("sector-a", "tech", List.of("A"), 0.9, 0.6, 0.2),
                new SegmentResponseDTO.Segment("sector-b", "tech", List.of("B"), 0.9, 0.4, 0.2)
        )));
        input.setSectorOverrides(List.of(
                new SectorParameterOverride("sector-a", "operating_margin", 5.0, "relative_additive", "both"),
                new SectorParameterOverride("unknown-sector", "operating_margin", 5.0, "relative_additive", "both")
        ));

        when(sectorMappingRepository.findByIndustryName("sector-a"))
                .thenReturn(new SectorMapping(1L, "yahoo-a", "sector-a", "Industry A"));
        when(sectorMappingRepository.findByIndustryName("sector-b"))
                .thenReturn(new SectorMapping(2L, "yahoo-b", "sector-b", "Industry B"));

        when(inputStatRepository.findFirstByIndustryGroupOrderByIdAsc(anyString())).thenReturn(Optional.empty());
        when(industryAvgUSRepository.findByIndustryName(anyString())).thenReturn(null);

        service.applySegmentWeightedParameters(input, companyData("United States"), List.of(), 0.04);

        SegmentWeightedParameters context = SegmentParameterContext.getParameters();
        assertNotNull(context);
        assertTrue(context.hasSectorParameters());
        assertEquals(2, context.getSectorNames().size());

        SegmentWeightedParameters.SectorParameters a = context.getSectorParameters("sector-a");
        SegmentWeightedParameters.SectorParameters b = context.getSectorParameters("sector-b");

        assertNotNull(a);
        assertNotNull(b);
        assertEquals(23.0, a.getTargetPreTaxOperatingMargin(), 0.0001);
        assertEquals(18.0, b.getTargetPreTaxOperatingMargin(), 0.0001);

        assertEquals(3.0, input.getRevenueNextYear(), 0.0001);
        assertNotNull(input.getInitialCostCapital());
    }

    @Test
    void applySegmentWeightedParameters_missingSectorMapping_redistributesToMappedSegments() {
        FinancialDataInput input = baselineInput();
        input.setSegments(new SegmentResponseDTO(List.of(
                new SegmentResponseDTO.Segment("missing-sector", "tech", List.of("A"), 0.9, 0.7, 0.2),
                new SegmentResponseDTO.Segment("mapped-sector", "tech", List.of("B"), 0.9, 0.3, 0.2)
        )));

        when(sectorMappingRepository.findByIndustryName("missing-sector")).thenReturn(null);
        when(sectorMappingRepository.findByIndustryName("mapped-sector"))
                .thenReturn(new SectorMapping(2L, "yahoo-b", "mapped-sector", "Industry B"));

        service.applySegmentWeightedParameters(input, companyData("United States"), List.of(), 0.04);

        SegmentWeightedParameters context = SegmentParameterContext.getParameters();
        assertNotNull(context);
        assertTrue(context.hasSectorParameters());
        assertNotNull(context.getSectorParameters("mapped-sector"));
        assertNull(context.getSectorParameters("missing-sector"));

        // With 70% missing-share redistributed to the only mapped segment,
        // weighted revenue next-year should reflect full 100% mapped weight.
        assertEquals(3.0, input.getRevenueNextYear(), 0.0001);
    }

    @Test
    void applySegmentWeightedParameters_explicitTopLevelOverrides_remainAuthoritativeInSegmentMode() {
        FinancialDataInput input = baselineInput();
        input.setRevenueNextYear(12.5);
        input.setCompoundAnnualGrowth2_5(12.5);
        input.setOperatingMarginNextYear(36.0);
        input.setTargetPreTaxOperatingMargin(36.0);
        input.setSalesToCapitalYears1To5(3.6);
        input.setSalesToCapitalYears6To10(3.6);
        input.setInitialCostCapital(9.2);
        input.setSegments(new SegmentResponseDTO(List.of(
                new SegmentResponseDTO.Segment("sector-a", "tech", List.of("A"), 0.9, 0.6, 0.2),
                new SegmentResponseDTO.Segment("sector-b", "tech", List.of("B"), 0.9, 0.4, 0.2)
        )));

        when(sectorMappingRepository.findByIndustryName("sector-a"))
                .thenReturn(new SectorMapping(1L, "yahoo-a", "sector-a", "Industry A"));
        when(sectorMappingRepository.findByIndustryName("sector-b"))
                .thenReturn(new SectorMapping(2L, "yahoo-b", "sector-b", "Industry B"));

        IndustryAveragesUS highIndustryAverages = new IndustryAveragesUS();
        highIndustryAverages.setAnnualAverageRevenueGrowth(40.0);
        highIndustryAverages.setPreTaxOperatingMargin(45.0);
        highIndustryAverages.setSalesToCapital(6.0);
        highIndustryAverages.setCostOfCapital(0.11);
        when(industryAvgUSRepository.findByIndustryName(anyString())).thenReturn(highIndustryAverages);
        when(inputStatRepository.findFirstByIndustryGroupOrderByIdAsc(anyString())).thenReturn(Optional.empty());

        service.applySegmentWeightedParameters(
                input,
                companyData("United States"),
                List.of(
                        "revenueNextYear",
                        "compoundAnnualGrowth2_5",
                        "operatingMarginNextYear",
                        "targetPreTaxOperatingMargin",
                        "salesToCapitalYears1To5",
                        "salesToCapitalYears6To10",
                        "initialCostCapital"),
                0.04);

        SegmentWeightedParameters context = SegmentParameterContext.getParameters();
        assertNotNull(context);
        assertEquals(12.5, input.getRevenueNextYear(), 0.0001);
        assertEquals(12.5, input.getCompoundAnnualGrowth2_5(), 0.0001);
        assertEquals(36.0, input.getTargetPreTaxOperatingMargin(), 0.0001);
        assertEquals(3.6, input.getSalesToCapitalYears1To5(), 0.0001);
        assertEquals(3.6, input.getSalesToCapitalYears6To10(), 0.0001);
        assertEquals(9.2, input.getInitialCostCapital(), 0.0001);

        SegmentWeightedParameters.SectorParameters sectorA = context.getSectorParameters("sector-a");
        SegmentWeightedParameters.SectorParameters sectorB = context.getSectorParameters("sector-b");
        assertNotNull(sectorA);
        assertNotNull(sectorB);
        assertEquals(12.5, sectorA.getCompoundAnnualGrowth2_5(), 0.0001);
        assertEquals(12.5, sectorB.getCompoundAnnualGrowth2_5(), 0.0001);
        assertEquals(36.0, sectorA.getTargetPreTaxOperatingMargin(), 0.0001);
        assertEquals(36.0, sectorB.getTargetPreTaxOperatingMargin(), 0.0001);
    }

    @Test
    void validateAndApplySectorOverridesCoverPrivateBranches() {
        SegmentResponseDTO segments = new SegmentResponseDTO(List.of(
                new SegmentResponseDTO.Segment("software", "tech", List.of("core"), 0.8, 0.6, 0.2),
                new SegmentResponseDTO.Segment("hardware", "tech", List.of("device"), 0.8, 0.4, 0.2)
        ));
        List<SectorParameterOverride> overrides = List.of(
                new SectorParameterOverride("software", "revenue_growth", 15.0, "absolute", null),
                new SectorParameterOverride("software", "operating_margin", 3.0, "relative_additive", "both"),
                new SectorParameterOverride("hardware", "sales_to_capital", 10.0, "relative_multiplier", "years_6_to_10"),
                new SectorParameterOverride("hardware", "unknown", 10.0, "absolute", "both"),
                new SectorParameterOverride("", "revenue_growth", 10.0, "absolute", "both"),
                new SectorParameterOverride("missing", "revenue_growth", 10.0, "absolute", "both"));

        @SuppressWarnings("unchecked")
        List<SectorParameterOverride> validated = (List<SectorParameterOverride>) ReflectionTestUtils.invokeMethod(
                service, "validateSectorOverrides", overrides, segments);

        assertEquals(3, validated.size());
        assertEquals("both", validated.get(0).getTimeframe());

        SegmentWeightedParameters.SectorParameters sectorParams = new SegmentWeightedParameters.SectorParameters();
        sectorParams.setSectorName("software");
        sectorParams.setRevenueNextYear(5.0);
        sectorParams.setCompoundAnnualGrowth2_5(6.0);
        sectorParams.setOperatingMarginNextYear(20.0);
        sectorParams.setTargetPreTaxOperatingMargin(22.0);
        sectorParams.setSalesToCapitalYears1To5(2.0);
        sectorParams.setSalesToCapitalYears6To10(2.5);

        ReflectionTestUtils.invokeMethod(service, "applySectorOverrides", validated, sectorParams, "software");
        assertEquals(15.0, sectorParams.getRevenueNextYear());
        assertEquals(15.0, sectorParams.getCompoundAnnualGrowth2_5());
        assertEquals(23.0, sectorParams.getOperatingMarginNextYear());
        assertEquals(25.0, sectorParams.getTargetPreTaxOperatingMargin());
    }

    @Test
    void applySegmentWeightedParameters_usesGlobalIndustryAndInputStatData() {
        FinancialDataInput input = baselineInput();
        input.setSegments(new SegmentResponseDTO(List.of(
                new SegmentResponseDTO.Segment("sector-a", "tech", List.of("A"), 0.9, 0.6, 0.2),
                new SegmentResponseDTO.Segment("sector-b", "tech", List.of("B"), 0.9, 0.4, 0.2)
        )));

        when(sectorMappingRepository.findByIndustryName("sector-a"))
                .thenReturn(new SectorMapping(1L, "yahoo-a", "sector-a", "Industry A"));
        when(sectorMappingRepository.findByIndustryName("sector-b"))
                .thenReturn(new SectorMapping(2L, "yahoo-b", "sector-b", "Industry B"));

        IndustryAveragesGlobal industryA = new IndustryAveragesGlobal();
        industryA.setAnnualAverageRevenueGrowth(12.0);
        industryA.setPreTaxOperatingMargin(22.0);
        industryA.setSalesToCapital(3.0);
        industryA.setCostOfCapital(0.09);
        IndustryAveragesGlobal industryB = new IndustryAveragesGlobal();
        industryB.setAnnualAverageRevenueGrowth(6.0);
        industryB.setPreTaxOperatingMargin(18.0);
        industryB.setSalesToCapital(2.5);
        industryB.setCostOfCapital(0.08);
        when(industryAvgGloRepository.findByIndustryName("Industry A")).thenReturn(industryA);
        when(industryAvgGloRepository.findByIndustryName("Industry B")).thenReturn(industryB);

        InputStatDistribution stats = new InputStatDistribution();
        stats.setPreTaxOperatingMarginFirstQuartile(10.0);
        stats.setPreTaxOperatingMarginMedian(15.0);
        stats.setPreTaxOperatingMarginThirdQuartile(20.0);
        stats.setSalesToInvestedCapitalThirdQuartile(4.0);
        when(inputStatRepository.findFirstByIndustryGroupOrderByIdAsc(anyString())).thenReturn(Optional.of(stats));

        service.applySegmentWeightedParameters(input, companyData("Sweden"), List.of(), 0.04);

        SegmentWeightedParameters context = SegmentParameterContext.getParameters();
        assertNotNull(context);
        assertEquals(2, context.getSegmentCount());
        assertEquals(Set.of("sector-a", "sector-b"), context.getSectorNames());
        assertTrue(context.getWeightedInitialCostCapital() > 0);
        assertTrue(context.getSectorParameters("sector-a").getTerminalGrowthRate() > 0);
    }

    @Test
    void staticHelpersRecomputeWeightedAveragesAndRespectTopLevelOverrides() {
        assertEquals(0.5, ReflectionTestUtils.invokeMethod(service, "convertPercentage", 50.0));
        assertEquals(5.0, ReflectionTestUtils.invokeMethod(service, "coalesce", null, 5.0));
        assertEquals(10.0, ReflectionTestUtils.invokeMethod(service, "asPercent", 0.10));
        assertEquals(4.0, ReflectionTestUtils.invokeMethod(service, "reAdjustSalesToCapitalFirstPhases", 8.0, 3.0));

        SegmentWeightedParameters segmentParams = new SegmentWeightedParameters();
        SegmentWeightedParameters.SectorParameters software = new SegmentWeightedParameters.SectorParameters();
        software.setSectorName("software");
        software.setRevenueShare(0.6);
        software.setRevenueNextYear(10.0);
        software.setCompoundAnnualGrowth2_5(12.0);
        software.setOperatingMarginNextYear(20.0);
        software.setTargetPreTaxOperatingMargin(25.0);
        software.setSalesToCapitalYears1To5(3.0);
        software.setSalesToCapitalYears6To10(2.5);
        software.setInitialCostCapital(8.0);
        SegmentWeightedParameters.SectorParameters hardware = new SegmentWeightedParameters.SectorParameters();
        hardware.setSectorName("hardware");
        hardware.setRevenueShare(0.4);
        hardware.setRevenueNextYear(6.0);
        hardware.setCompoundAnnualGrowth2_5(8.0);
        hardware.setOperatingMarginNextYear(18.0);
        hardware.setTargetPreTaxOperatingMargin(20.0);
        hardware.setSalesToCapitalYears1To5(2.0);
        hardware.setSalesToCapitalYears6To10(1.8);
        hardware.setInitialCostCapital(7.0);
        segmentParams.setSectorParameters("software", software);
        segmentParams.setSectorParameters("hardware", hardware);

        ReflectionTestUtils.invokeMethod(service, "recomputeWeightedFromSectorParameters", segmentParams);
        assertEquals(8.4, segmentParams.getWeightedRevenueNextYear(), 1e-9);
        assertEquals(10.4, segmentParams.getWeightedCompoundAnnualGrowth2_5(), 1e-9);

        FinancialDataInput overrides = baselineInput();
        overrides.setRevenueNextYear(15.0);
        overrides.setCompoundAnnualGrowth2_5(16.0);
        overrides.setOperatingMarginNextYear(30.0);
        overrides.setTargetPreTaxOperatingMargin(32.0);
        overrides.setSalesToCapitalYears1To5(4.0);
        overrides.setSalesToCapitalYears6To10(3.5);
        overrides.setInitialCostCapital(9.5);

        ReflectionTestUtils.invokeMethod(service, "applyTopLevelOverridesToSector",
                software,
                overrides,
                Set.of("revenueNextYear", "compoundAnnualGrowth2_5", "operatingMarginNextYear",
                        "targetPreTaxOperatingMargin", "salesToCapitalYears1To5", "salesToCapitalYears6To10",
                        "initialCostCapital"),
                List.of());

        assertEquals(15.0, software.getRevenueNextYear());
        assertEquals(16.0, software.getCompoundAnnualGrowth2_5());
        assertEquals(30.0, software.getOperatingMarginNextYear());
        assertEquals(32.0, software.getTargetPreTaxOperatingMargin());
        assertEquals(4.0, software.getSalesToCapitalYears1To5());
        assertEquals(3.5, software.getSalesToCapitalYears6To10());
        assertEquals(9.5, software.getInitialCostCapital());
    }

    private static FinancialDataInput baselineInput() {
        FinancialDataInput input = new FinancialDataInput();
        input.setRevenueNextYear(3.0);
        input.setCompoundAnnualGrowth2_5(4.0);
        input.setOperatingMarginNextYear(20.0);
        input.setTargetPreTaxOperatingMargin(18.0);
        input.setSalesToCapitalYears1To5(2.0);
        input.setSalesToCapitalYears6To10(2.5);
        input.setInitialCostCapital(8.0);
        input.setIndustry("technology");
        return input;
    }

    private static CompanyDataDTO companyData(String country) {
        BasicInfoDataDTO basic = new BasicInfoDataDTO();
        basic.setTicker("AAPL");
        basic.setCountryOfIncorporation(country);
        basic.setIndustryUs("technology");

        CompanyDriveDataDTO drive = new CompanyDriveDataDTO();
        drive.setRevenueNextYear(0.10);
        drive.setOperatingMarginNextYear(0.20);
        drive.setTargetPreTaxOperatingMargin(20.0);
        drive.setCompoundAnnualGrowth2_5(5.0);
        drive.setSalesToCapitalYears1To5(2.5);
        drive.setSalesToCapitalYears6To10(2.5);
        drive.setRiskFreeRate(0.04);
        drive.setInitialCostCapital(0.08);
        drive.setConvergenceYearMargin(0.15);

        CompanyDataDTO dto = new CompanyDataDTO();
        dto.setBasicInfoDataDTO(basic);
        dto.setCompanyDriveDataDTO(drive);
        return dto;
    }
}
