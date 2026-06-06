package io.stockvaluation.service;

import io.stockvaluation.constant.RDResult;
import io.stockvaluation.dto.BasicInfoDataDTO;
import io.stockvaluation.dto.FinancialDataDTO;
import io.stockvaluation.dto.OverrideAssumption;
import io.stockvaluation.dto.SegmentResponseDTO;
import io.stockvaluation.dto.SegmentWeightedParameters;
import io.stockvaluation.dto.valuationoutput.FinancialDTO;
import io.stockvaluation.form.FinancialDataInput;
import io.stockvaluation.repository.IndustryAveragesGlobalRepository;
import io.stockvaluation.repository.InputStatRepository;
import io.stockvaluation.repository.SectorMappingRepository;
import io.stockvaluation.utils.SegmentParameterContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ValuationOutputServiceSegmentMetricsTest {

    @Mock
    private CommonService commonService;
    @Mock
    private OptionValueService optionValueService;
    @Mock
    private CostOfCapitalService costOfCapitalService;
    @Mock
    private SyntheticRatingService syntheticRatingService;
    @Mock
    private IndustryAveragesGlobalRepository industryAvgGloRepository;
    @Mock
    private InputStatRepository inputStatRepository;
    @Mock
    private SectorMappingRepository sectorMappingRepository;

    @AfterEach
    void tearDown() {
        SegmentParameterContext.clear();
    }

    @Test
    void calculateFinancialData_withSegmentContext_populatesSectorMapsAndAggregates() {
        ValuationOutputService service = service();
        when(commonService.resolveEquityRiskPremiumForCountry("United States")).thenReturn(4.0);

        FinancialDataInput input = baseInput();
        input.setSegments(new SegmentResponseDTO(List.of(
                new SegmentResponseDTO.Segment("software", "technology", List.of("cloud"), 1.0, 0.6, 0.3),
                new SegmentResponseDTO.Segment("hardware", "technology", List.of("devices"), 1.0, 0.4, 0.2)
        )));

        SegmentWeightedParameters params = new SegmentWeightedParameters();
        params.setSegmentWeighted(true);
        params.setSegmentCount(2);
        params.setWeightedRevenueNextYear(8.0);
        params.setWeightedCompoundAnnualGrowth2_5(6.0);
        params.setWeightedOperatingMarginNextYear(25.0);
        params.setWeightedTargetPreTaxOperatingMargin(25.0);
        params.setConvergenceYearMargin(5.0);
        params.setWeightedSalesToCapitalYears1To5(2.0);
        params.setWeightedSalesToCapitalYears6To10(2.0);
        params.setWeightedInitialCostCapital(8.0);
        params.setRiskFreeRate(4.0);

        params.setSectorParameters("software", sectorParams("software", 0.6, 9.0, 7.0, 0.04, 30.0, 30.0, 5.0, 2.0, 2.0));
        params.setSectorParameters("hardware", sectorParams("hardware", 0.4, 6.0, 5.5, 0.04, 22.0, 22.0, 5.0, 2.0, 2.0));
        SegmentParameterContext.setParameters(params);

        FinancialDTO financial = service.calculateFinancialData(
                input,
                new RDResult(0.0, 0.0, 0.0, 0.0),
                new io.stockvaluation.dto.LeaseResultDTO(0.0, 0.0, 0.0, 0.0),
                "AAPL",
                null
        );

        assertEquals(12, financial.getArrayLength());

        assertEquals(2, financial.getRevenuesBySector().size());
        assertEquals(2, financial.getRevenueGrowthRateBySector().size());
        assertEquals(2, financial.getEbitOperatingMarginBySector().size());
        assertEquals(2, financial.getEbitOperatingIncomeSector().size());

        assertEquals(2, financial.getEbit1MinusTaxBySector().size());
        assertEquals(2, financial.getSalesToCapitalRatioBySector().size());
        assertEquals(2, financial.getReinvestmentBySector().size());
        assertEquals(2, financial.getInvestedCapitalBySector().size());
        assertEquals(2, financial.getFcffBySector().size());
        assertEquals(2, financial.getRoicBySector().size());
        assertEquals(2, financial.getCostOfCapitalBySector().size());
        assertEquals(2, financial.getPvFcffBySector().size());
        assertEquals(8.0, financial.getCostOfCapital()[financial.getTerminalYearIndex()], 0.0001);

        assertEquals(9.0, financial.getRevenueGrowthRateBySector().get("software")[1], 0.0001);
        assertEquals(6.0, financial.getRevenueGrowthRateBySector().get("hardware")[1], 0.0001);
        assertEquals(30.0, financial.getEbitOperatingMarginBySector().get("software")[1], 0.0001);
        assertTrue(financial.getEbitOperatingMargin()[1] > 26.8);
        assertTrue(financial.getEbitOperatingMargin()[1] < 27.0);

        assertNotNull(financial.getEbitOperatingMarginBySector().get("software")[10]);
        assertTrue(financial.getEbitOperatingMarginBySector().get("software")[10] > 30.0,
                "forced convergence should increase software margin when base ~= target");
        assertTrue(financial.getSalesToCapitalRatioBySector().get("software")[10] > 2.0,
                "forced convergence should increase sales-to-capital when phase1 ~= phase2");

        double sectorRevenueYear0 = financial.getRevenuesBySector().get("software")[0]
                + financial.getRevenuesBySector().get("hardware")[0];
        assertEquals(sectorRevenueYear0, financial.getRevenues()[0], 0.0001);

        double sectorFcffYear3 = financial.getFcffBySector().get("software")[3]
                + financial.getFcffBySector().get("hardware")[3];
        assertEquals(sectorFcffYear3, financial.getFcff()[3], 0.0001);
    }

    @Test
    void calculateFinancialData_withSegmentsWithoutContext_usesCompanyGrowthFallbackPerSector() {
        ValuationOutputService service = service();
        when(commonService.resolveEquityRiskPremiumForCountry("United States")).thenReturn(4.0);

        FinancialDataInput input = baseInput();
        input.setSegments(new SegmentResponseDTO(List.of(
                new SegmentResponseDTO.Segment("software", "technology", List.of("cloud"), 1.0, 0.5, 0.3),
                new SegmentResponseDTO.Segment("hardware", "technology", List.of("devices"), 1.0, 0.5, 0.2)
        )));

        FinancialDTO financial = service.calculateFinancialData(
                input,
                new RDResult(0.0, 0.0, 0.0, 0.0),
                new io.stockvaluation.dto.LeaseResultDTO(0.0, 0.0, 0.0, 0.0),
                "AAPL",
                null
        );

        assertEquals(2, financial.getRevenueGrowthRateBySector().size());
        assertEquals(financial.getRevenueGrowthRate()[1], financial.getRevenueGrowthRateBySector().get("software")[1], 0.0001);
        assertEquals(financial.getRevenueGrowthRate()[1], financial.getRevenueGrowthRateBySector().get("hardware")[1], 0.0001);

        assertEquals(2, financial.getFcffBySector().size());
        assertNotNull(financial.getCostOfCapitalBySector().get("software")[1]);
        assertNotNull(financial.getCostOfCapitalBySector().get("hardware")[1]);
    }

    @Test
    void calculateFinancialData_honorsLowerSectorSalesToCapitalOverride() {
        ValuationOutputService service = service();
        when(commonService.resolveEquityRiskPremiumForCountry("United States")).thenReturn(4.0);

        FinancialDataInput input = baseInput();
        input.setSalesToCapitalYears1To5(4.0);
        input.setSalesToCapitalYears6To10(4.0);
        input.setSegments(new SegmentResponseDTO(List.of(
                new SegmentResponseDTO.Segment("software", "technology", List.of("cloud"), 1.0, 0.6, 0.3),
                new SegmentResponseDTO.Segment("hardware", "technology", List.of("devices"), 1.0, 0.4, 0.2)
        )));

        SegmentWeightedParameters params = new SegmentWeightedParameters();
        params.setSegmentWeighted(true);
        params.setSegmentCount(2);
        params.setWeightedRevenueNextYear(8.0);
        params.setWeightedCompoundAnnualGrowth2_5(6.0);
        params.setWeightedOperatingMarginNextYear(25.0);
        params.setWeightedTargetPreTaxOperatingMargin(25.0);
        params.setConvergenceYearMargin(5.0);
        params.setWeightedSalesToCapitalYears1To5(3.68);
        params.setWeightedSalesToCapitalYears6To10(3.68);
        params.setWeightedInitialCostCapital(8.0);
        params.setRiskFreeRate(4.0);

        // Intentionally lower than company-level sales-to-capital to verify override is respected.
        params.setSectorParameters("software", sectorParams("software", 0.6, 9.0, 7.0, 0.04, 30.0, 30.0, 5.0, 3.2, 3.2));
        params.setSectorParameters("hardware", sectorParams("hardware", 0.4, 6.0, 5.5, 0.04, 22.0, 22.0, 5.0, 4.0, 4.0));
        SegmentParameterContext.setParameters(params);

        FinancialDTO financial = service.calculateFinancialData(
                input,
                new RDResult(0.0, 0.0, 0.0, 0.0),
                new io.stockvaluation.dto.LeaseResultDTO(0.0, 0.0, 0.0, 0.0),
                "MSFT",
                null
        );

        assertEquals(3.2, financial.getSalesToCapitalRatioBySector().get("software")[1], 0.0001);
    }

    @Test
    void calculateFinancialData_usesDamodaranStyleProspectusSegmentRevenueFixture() {
        ValuationOutputService service = service();
        when(commonService.resolveEquityRiskPremiumForCountry("United States")).thenReturn(3.69);

        FinancialDataInput input = baseInput();
        input.getFinancialDataDTO().setRevenueTTM(18_674_000_000.0);
        input.getFinancialDataDTO().setOperatingIncomeTTM(-2_589_000_000.0);
        input.setRevenueNextYear(20.0);
        input.setCompoundAnnualGrowth2_5(35.0);
        input.setOperatingMarginNextYear(20.0);
        input.setTargetPreTaxOperatingMargin(42.0);
        input.setSalesToCapitalYears1To5(3.0);
        input.setSalesToCapitalYears6To10(4.0);
        input.setRiskFreeRate(4.56);
        input.setInitialCostCapital(837.450225998141);
        input.setTerminalGrowthRate(4.56);
        input.setOverrideAssumptionReturnOnCapital(new OverrideAssumption(15.0, true, 0.0, null));
        input.setOverrideAssumptionCostCapital(new OverrideAssumption(8.25, true, 0.0, null));
        input.setSegments(new SegmentResponseDTO(List.of(
                new SegmentResponseDTO.Segment("launch", "Launch", List.of("Launch"), 1.0, 40_000.0 / 420_000.0, null),
                new SegmentResponseDTO.Segment("starlink-connectivity", "Starlink / Connectivity", List.of("Starlink / Connectivity"), 1.0, 120_000.0 / 420_000.0, null),
                new SegmentResponseDTO.Segment("ai", "AI", List.of("AI"), 1.0, 160_000.0 / 420_000.0, null),
                new SegmentResponseDTO.Segment("other-expansion", "Other or expansion revenue", List.of("Other or expansion revenue"), 1.0, 100_000.0 / 420_000.0, null)
        )));

        SegmentWeightedParameters params = new SegmentWeightedParameters();
        params.setSegmentWeighted(true);
        params.setSegmentCount(4);
        params.setWeightedRevenueNextYear(30.0);
        params.setWeightedCompoundAnnualGrowth2_5(35.0);
        params.setWeightedOperatingMarginNextYear(20.0);
        params.setWeightedTargetPreTaxOperatingMargin(42.0);
        params.setConvergenceYearMargin(10.0);
        params.setWeightedSalesToCapitalYears1To5(2.6905);
        params.setWeightedSalesToCapitalYears6To10(3.8095);
        params.setWeightedInitialCostCapital(837.450225998141);
        params.setRiskFreeRate(4.56);
        params.setBaselineQuality("prospectus_explicit_scenario");
        params.setSegmentCoveragePct(100.0);
        params.setSectorParameters("launch", spacexSector(
                "launch",
                40_000.0 / 420_000.0,
                4_086_000_000.0,
                40_000_000_000.0,
                List.of(4_086_000_000.0, 5_500_000_000.0, 7_500_000_000.0, 10_000_000_000.0, 13_500_000_000.0,
                        18_000_000_000.0, 23_000_000_000.0, 28_000_000_000.0, 33_000_000_000.0,
                        37_000_000_000.0, 40_000_000_000.0),
                45.0,
                3.0,
                4.0));
        params.setSectorParameters("starlink-connectivity", spacexSector(
                "starlink-connectivity",
                120_000.0 / 420_000.0,
                11_387_000_000.0,
                120_000_000_000.0,
                List.of(11_387_000_000.0, 18_000_000_000.0, 27_000_000_000.0, 39_000_000_000.0, 52_000_000_000.0,
                        65_000_000_000.0, 78_000_000_000.0, 91_000_000_000.0, 104_000_000_000.0,
                        114_000_000_000.0, 120_000_000_000.0),
                60.0,
                3.0,
                5.0));
        params.setSectorParameters("ai", spacexSector(
                "ai",
                160_000.0 / 420_000.0,
                3_201_000_000.0,
                160_000_000_000.0,
                List.of(3_201_000_000.0, 7_500_000_000.0, 15_000_000_000.0, 28_000_000_000.0, 45_000_000_000.0,
                        65_000_000_000.0, 88_000_000_000.0, 112_000_000_000.0, 135_000_000_000.0,
                        151_000_000_000.0, 160_000_000_000.0),
                25.0,
                1.5,
                2.5));
        params.setSectorParameters("other-expansion", spacexSector(
                "other-expansion",
                100_000.0 / 420_000.0,
                0.0,
                100_000_000_000.0,
                List.of(0.0, 5_000_000_000.0, 12_000_000_000.0, 22_000_000_000.0, 34_000_000_000.0,
                        47_000_000_000.0, 60_000_000_000.0, 72_000_000_000.0, 84_000_000_000.0,
                        94_000_000_000.0, 100_000_000_000.0),
                30.0,
                5.0,
                5.0));
        SegmentParameterContext.setParameters(params);

        FinancialDTO financial = service.calculateFinancialData(
                input,
                new RDResult(0.0, 0.0, 0.0, 0.0),
                new io.stockvaluation.dto.LeaseResultDTO(0.0, 0.0, 0.0, 0.0),
                "SPCX",
                null
        );

        assertEquals(4_086_000_000.0, financial.getRevenuesBySector().get("launch")[0], 0.001);
        assertEquals(40_000_000_000.0, financial.getRevenuesBySector().get("launch")[10], 0.001);
        assertEquals(120_000_000_000.0, financial.getRevenuesBySector().get("starlink-connectivity")[10], 0.001);
        assertEquals(160_000_000_000.0, financial.getRevenuesBySector().get("ai")[10], 0.001);
        assertEquals(0.0, financial.getRevenuesBySector().get("other-expansion")[0], 0.001);
        assertEquals(100_000_000_000.0, financial.getRevenuesBySector().get("other-expansion")[10], 0.001);
        assertEquals(420_000_000_000.0, financial.getRevenues()[10], 0.001);
        assertEquals(439_152_000_000.0, financial.getRevenues()[11], 0.001);
        assertNull(financial.getRevenueGrowthRateBySector().get("other-expansion")[1]);
        assertEquals(4.56, financial.getRevenueGrowthRateBySector().get("launch")[11], 0.0001);
        assertEquals(15.0, financial.getRoic()[financial.getTerminalYearIndex()], 0.0001);
    }

    private ValuationOutputService service() {
        return new ValuationOutputService(
                commonService,
                optionValueService,
                costOfCapitalService,
                syntheticRatingService,
                industryAvgGloRepository,
                inputStatRepository,
                sectorMappingRepository
        );
    }

    private static SegmentWeightedParameters.SectorParameters sectorParams(
            String name,
            double share,
            double revenueNext,
            double cagr,
            double terminalGrowthDecimal,
            double baseMargin,
            double targetMargin,
            double convergenceYear,
            double salesToCapital1To5,
            double salesToCapital6To10
    ) {
        SegmentWeightedParameters.SectorParameters s = new SegmentWeightedParameters.SectorParameters();
        s.setSectorName(name);
        s.setRevenueShare(share);
        s.setRevenueNextYear(revenueNext);
        s.setCompoundAnnualGrowth2_5(cagr);
        s.setTerminalGrowthRate(terminalGrowthDecimal);
        s.setOperatingMarginNextYear(baseMargin);
        s.setTargetPreTaxOperatingMargin(targetMargin);
        s.setConvergenceYearMargin(convergenceYear);
        s.setSalesToCapitalYears1To5(salesToCapital1To5);
        s.setSalesToCapitalYears6To10(salesToCapital6To10);
        s.setInitialCostCapital(8.0);
        s.setIndustryAsPerExcel("Technology");
        return s;
    }

    private static SegmentWeightedParameters.SectorParameters spacexSector(
            String name,
            double share,
            double baseRevenue,
            double targetRevenue,
            List<Double> projectedRevenues,
            double targetMargin,
            double salesToCapital1To5,
            double salesToCapital6To10) {
        SegmentWeightedParameters.SectorParameters s = sectorParams(
                name,
                share,
                30.0,
                35.0,
                0.0456,
                targetMargin,
                targetMargin,
                10.0,
                salesToCapital1To5,
                salesToCapital6To10);
        s.setBaseRevenue(baseRevenue);
        s.setTargetRevenue(targetRevenue);
        s.setProjectedRevenues(projectedRevenues);
        s.setInitialCostCapital(837.450225998141);
        s.setIndustryAsPerExcel(name);
        return s;
    }

    private static FinancialDataInput baseInput() {
        FinancialDataInput input = new FinancialDataInput();
        BasicInfoDataDTO basicInfo = new BasicInfoDataDTO();
        basicInfo.setCountryOfIncorporation("United States");
        input.setBasicInfoDataDTO(basicInfo);
        input.setFinancialDataDTO(baseFinancialData());
        input.setRevenueNextYear(0.08);
        input.setOperatingMarginNextYear(0.25);
        input.setCompoundAnnualGrowth2_5(6.0);
        input.setTargetPreTaxOperatingMargin(25.0);
        input.setConvergenceYearMargin(5.0);
        input.setSalesToCapitalYears1To5(2.0);
        input.setSalesToCapitalYears6To10(2.0);
        input.setRiskFreeRate(4.0);
        input.setInitialCostCapital(8.0);
        input.setIndustry("technology");
        input.setIsExpensesCapitalize(false);
        input.setHasOperatingLease(false);
        input.setHasEmployeeOptions(false);

        input.setOverrideAssumptionCostCapital(noOverride());
        input.setOverrideAssumptionReturnOnCapital(noOverride());
        input.setOverrideAssumptionProbabilityOfFailure(new OverrideAssumption(0.0, false, 0.0, "V"));
        input.setOverrideAssumptionReinvestmentLag(noOverride());
        input.setOverrideAssumptionTaxRate(noOverride());
        input.setOverrideAssumptionNOL(noOverride());
        input.setOverrideAssumptionRiskFreeRate(noOverride());
        input.setOverrideAssumptionGrowthRate(noOverride());
        input.setOverrideAssumptionCashPosition(noOverride());
        return input;
    }

    private static FinancialDataDTO baseFinancialData() {
        FinancialDataDTO dto = new FinancialDataDTO();
        dto.setRevenueTTM(100_000.0);
        dto.setRevenueLTM(95_000.0);
        dto.setOperatingIncomeTTM(25_000.0);
        dto.setEffectiveTaxRate(0.21);
        dto.setMarginalTaxRate(25.0);
        dto.setBookValueEqualityTTM(60_000.0);
        dto.setBookValueDebtTTM(20_000.0);
        dto.setCashAndMarkablTTM(10_000.0);
        dto.setNonOperatingAssetTTM(0.0);
        dto.setMinorityInterestTTM(0.0);
        dto.setNoOfShareOutstanding(1_000.0);
        dto.setStockPrice(100.0);
        return dto;
    }

    private static OverrideAssumption noOverride() {
        return new OverrideAssumption(0.0, false, 0.0, null);
    }
}
