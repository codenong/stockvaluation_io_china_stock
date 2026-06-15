package io.stockvaluation.service;

import io.stockvaluation.constant.RDResult;
import io.stockvaluation.domain.SectorMapping;
import io.stockvaluation.dto.BasicInfoDataDTO;
import io.stockvaluation.dto.LeaseResultDTO;
import io.stockvaluation.dto.OptionValueResultDTO;
import io.stockvaluation.dto.OverrideAssumption;
import io.stockvaluation.dto.SegmentResponseDTO;
import io.stockvaluation.dto.SegmentWeightedParameters;
import io.stockvaluation.dto.valuationoutput.CompanyDTO;
import io.stockvaluation.dto.valuationoutput.FinancialDTO;
import io.stockvaluation.exception.InsufficientFinancialDataException;
import io.stockvaluation.form.FinancialDataInput;
import io.stockvaluation.repository.IndustryAveragesGlobalRepository;
import io.stockvaluation.repository.InputStatRepository;
import io.stockvaluation.repository.SectorMappingRepository;
import io.stockvaluation.dto.FinancialDataDTO;
import io.stockvaluation.utils.SegmentParameterContext;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Map;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ValuationOutputServiceTest {

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

    @InjectMocks
    private ValuationOutputService valuationOutputService;

    private FinancialDataInput financialDataInput;

    @BeforeEach
    void setUp() {
        financialDataInput = new FinancialDataInput();
        FinancialDataDTO dto = new FinancialDataDTO();
        financialDataInput.setFinancialDataDTO(dto);
        dto.setBookValueDebtTTM(100.0);
        dto.setCashAndMarkablTTM(50.0);
        dto.setBookValueEqualityTTM(200.0);
        dto.setStockPrice(10.0);
        dto.setNoOfShareOutstanding(100.0);

        financialDataInput.setOverrideAssumptionReturnOnCapital(new OverrideAssumption(0.0, false, 0.0, "V"));
        financialDataInput.setOverrideAssumptionCostCapital(new OverrideAssumption(0.0, false, 0.0, "V"));
        financialDataInput.setOverrideAssumptionProbabilityOfFailure(new OverrideAssumption(0.0, false, 0.0, "V"));
        financialDataInput.setOverrideAssumptionReinvestmentLag(new OverrideAssumption(0.0, false, 0.0, "V"));
        financialDataInput.setOverrideAssumptionTaxRate(new OverrideAssumption(0.0, false, 0.0, "V"));
        financialDataInput.setOverrideAssumptionNOL(new OverrideAssumption(0.0, false, 0.0, "V"));
        financialDataInput.setOverrideAssumptionRiskFreeRate(new OverrideAssumption(0.0, false, 0.0, "V"));
        financialDataInput.setOverrideAssumptionGrowthRate(new OverrideAssumption(0.0, false, 0.0, "V"));
        financialDataInput.setOverrideAssumptionCashPosition(new OverrideAssumption(0.0, false, 0.0, "V"));

        financialDataInput.setTargetPreTaxOperatingMargin(20.0);
        financialDataInput.setSalesToCapitalYears1To5(2.0);
        financialDataInput.setSalesToCapitalYears6To10(2.0);
    }

    @Test
    void testCalculateDebt_NoLease() {
        financialDataInput.setHasOperatingLease(false);
        LeaseResultDTO leaseResultDTO = new LeaseResultDTO();
        leaseResultDTO.setAdjustmentToTotalDebt(20.0);

        Double result = ReflectionTestUtils.invokeMethod(valuationOutputService, "calculateDebt", financialDataInput,
                leaseResultDTO);
        assertEquals(100.0, result);
    }

    @Test
    void testCalculateDebt_WithLease() {
        financialDataInput.setHasOperatingLease(true);
        LeaseResultDTO leaseResultDTO = new LeaseResultDTO();
        leaseResultDTO.setAdjustmentToTotalDebt(20.0);

        Double result = ReflectionTestUtils.invokeMethod(valuationOutputService, "calculateDebt", financialDataInput,
                leaseResultDTO);
        assertEquals(120.0, result);
    }

    @Test
    void testCalculateCash() {
        Double result = ReflectionTestUtils.invokeMethod(valuationOutputService, "calculateCash", financialDataInput);
        assertEquals(50.0, result);
    }

    @Test
    void testCalculateProbablityOfFailure() {
        Double result = ReflectionTestUtils.invokeMethod(valuationOutputService, "calculateProbablityOfFailure",
                financialDataInput);
        assertEquals(0.0, result);
    }

    @Test
    void testCalculateValueOfOptions_HasOptions() {
        financialDataInput.setHasEmployeeOptions(true);
        OptionValueResultDTO optionValueResultDTO = new OptionValueResultDTO(15.0, 5.0);

        Double result = ReflectionTestUtils.invokeMethod(valuationOutputService, "calculateValueOfOptions",
                financialDataInput, optionValueResultDTO);
        assertEquals(5.0, result);
    }

    @Test
    void testCalculateValueOfOptions_NoOptions() {
        financialDataInput.setHasEmployeeOptions(false);
        OptionValueResultDTO optionValueResultDTO = new OptionValueResultDTO(15.0, 5.0);

        Double result = ReflectionTestUtils.invokeMethod(valuationOutputService, "calculateValueOfOptions",
                financialDataInput, optionValueResultDTO);
        assertEquals(0.0, result);
    }

    @Test
    void testCalculateOptionValueIfRequired_NoOptionsSkipsProviderLookup() {
        financialDataInput.setHasEmployeeOptions(false);

        OptionValueResultDTO result = ReflectionTestUtils.invokeMethod(
                valuationOutputService,
                "calculateOptionValueIfRequired",
                "PROSPECTUS",
                financialDataInput);

        assertEquals(0.0, result.getValuePerOption());
        assertEquals(0.0, result.getValueOfAllOptionsOutstanding());
        verifyNoInteractions(optionValueService);
    }

    @Test
    void getValuationOutput_passesScenarioRdAmortizationPeriodToConverter() {
        BasicInfoDataDTO basic = new BasicInfoDataDTO();
        basic.setCompanyName("Space Exploration Technologies Corp.");
        basic.setTicker("SPCX");
        basic.setIndustryUs("aerospace-defense");
        basic.setCountryOfIncorporation("United States");
        basic.setCurrency("USD");
        basic.setStockCurrency("USD");
        financialDataInput.setBasicInfoDataDTO(basic);
        financialDataInput.setIndustry("aerospace-defense");
        financialDataInput.setIsExpensesCapitalize(true);
        financialDataInput.setRdAmortizationPeriodYears(5);
        financialDataInput.setHasOperatingLease(false);
        financialDataInput.setHasEmployeeOptions(false);
        financialDataInput.setRevenueNextYear(5.0);
        financialDataInput.setOperatingMarginNextYear(15.0);
        financialDataInput.setCompoundAnnualGrowth2_5(6.0);
        financialDataInput.setConvergenceYearMargin(5.0);
        financialDataInput.setRiskFreeRate(4.5);
        financialDataInput.setInitialCostCapital(850.0);
        financialDataInput.getFinancialDataDTO().setRevenueTTM(1_000.0);
        financialDataInput.getFinancialDataDTO().setRevenueLTM(900.0);
        financialDataInput.getFinancialDataDTO().setOperatingIncomeTTM(100.0);
        financialDataInput.getFinancialDataDTO().setEffectiveTaxRate(0.21);
        financialDataInput.getFinancialDataDTO().setMarginalTaxRate(25.0);
        financialDataInput.getFinancialDataDTO().setMinorityInterestTTM(0.0);
        financialDataInput.getFinancialDataDTO().setNonOperatingAssetTTM(0.0);
        financialDataInput.getFinancialDataDTO().setResearchAndDevelopmentMap(Map.of(
                "currentR&D-0", 250.0,
                "currentR&D-1", 200.0,
                "currentR&D-2", 150.0,
                "currentR&D-3", 100.0,
                "currentR&D-4", 50.0));

        SectorMapping mapping = new SectorMapping();
        mapping.setIndustryAsPerExcel("Aerospace/Defense");
        when(sectorMappingRepository.findByIndustryName("aerospace-defense")).thenReturn(mapping);
        when(commonService.calculateRDConverterValue(
                "aerospace-defense",
                25.0,
                financialDataInput.getFinancialDataDTO().getResearchAndDevelopmentMap(),
                5)).thenReturn(new RDResult(300.0, 60.0, 190.0, 47.5));
        when(commonService.calculateOperatingLeaseConverter()).thenReturn(new LeaseResultDTO(0.0, 0.0, 0.0, 0.0));
        when(commonService.resolveEquityRiskPremiumForCountry("United States")).thenReturn(4.0);
        when(industryAvgGloRepository.findRevenueGrowth("Aerospace/Defense")).thenReturn(Optional.empty());
        when(industryAvgGloRepository.findOperatingMargin("Aerospace/Defense")).thenReturn(Optional.empty());

        valuationOutputService.getValuationOutput("SPCX", financialDataInput, null);

        verify(commonService).calculateRDConverterValue(
                "aerospace-defense",
                25.0,
                financialDataInput.getFinancialDataDTO().getResearchAndDevelopmentMap(),
                5);
    }

    @Test
    void getValuationOutput_skipsIndustryComparisonWhenProspectusIndustryIsUnmapped() {
        BasicInfoDataDTO basic = new BasicInfoDataDTO();
        basic.setCompanyName("Amazon.com, Inc.");
        basic.setTicker("SPCX");
        basic.setIndustryUs("unmapped-prospectus");
        basic.setCountryOfIncorporation("United States");
        basic.setCurrency("USD");
        basic.setStockCurrency("USD");
        financialDataInput.setBasicInfoDataDTO(basic);
        financialDataInput.setIndustry("unmapped-prospectus");
        financialDataInput.setIsExpensesCapitalize(true);
        financialDataInput.setRdAmortizationPeriodYears(5);
        financialDataInput.setHasOperatingLease(false);
        financialDataInput.setHasEmployeeOptions(false);
        financialDataInput.setRevenueNextYear(5.0);
        financialDataInput.setOperatingMarginNextYear(15.0);
        financialDataInput.setCompoundAnnualGrowth2_5(6.0);
        financialDataInput.setConvergenceYearMargin(5.0);
        financialDataInput.setRiskFreeRate(4.5);
        financialDataInput.setInitialCostCapital(850.0);
        financialDataInput.getFinancialDataDTO().setRevenueTTM(1_000.0);
        financialDataInput.getFinancialDataDTO().setRevenueLTM(900.0);
        financialDataInput.getFinancialDataDTO().setOperatingIncomeTTM(100.0);
        financialDataInput.getFinancialDataDTO().setEffectiveTaxRate(0.21);
        financialDataInput.getFinancialDataDTO().setMarginalTaxRate(25.0);
        financialDataInput.getFinancialDataDTO().setMinorityInterestTTM(0.0);
        financialDataInput.getFinancialDataDTO().setNonOperatingAssetTTM(0.0);
        financialDataInput.getFinancialDataDTO().setResearchAndDevelopmentMap(Map.of(
                "currentR&D-0", 250.0,
                "currentR&D-1", 200.0,
                "currentR&D-2", 150.0,
                "currentR&D-3", 100.0,
                "currentR&D-4", 50.0));

        when(sectorMappingRepository.findByIndustryName("unmapped-prospectus")).thenReturn(null);
        when(commonService.calculateRDConverterValue(
                "unmapped-prospectus",
                25.0,
                financialDataInput.getFinancialDataDTO().getResearchAndDevelopmentMap(),
                5)).thenReturn(new RDResult(300.0, 60.0, 190.0, 47.5));
        when(commonService.calculateOperatingLeaseConverter()).thenReturn(new LeaseResultDTO(0.0, 0.0, 0.0, 0.0));
        when(commonService.resolveEquityRiskPremiumForCountry("United States")).thenReturn(4.0);

        var result = valuationOutputService.getValuationOutput("SPCX", financialDataInput, null);

        assertEquals("Amazon.com, Inc.", result.getCompanyName());
        assertEquals(0.0, result.getBaseYearComparison().getRevenueGrowthIndustry());
        assertEquals(0.0, result.getBaseYearComparison().getOperatingMarginIndustry());
        verifyNoInteractions(industryAvgGloRepository);
    }

    @Test
    void segmentTerminalReinvestmentUsesTerminalReturnOnCapitalOverride() {
        BasicInfoDataDTO basic = new BasicInfoDataDTO();
        basic.setCompanyName("Scenario Company");
        basic.setTicker("SCEN");
        basic.setIndustryUs("unmapped-prospectus");
        basic.setCountryOfIncorporation("United States");
        basic.setCurrency("USD");
        basic.setStockCurrency("USD");
        financialDataInput.setBasicInfoDataDTO(basic);
        financialDataInput.setIndustry("unmapped-prospectus");
        financialDataInput.setIsExpensesCapitalize(false);
        financialDataInput.setHasOperatingLease(false);
        financialDataInput.setHasEmployeeOptions(false);
        financialDataInput.setRevenueNextYear(10.0);
        financialDataInput.setOperatingMarginNextYear(10.0);
        financialDataInput.setCompoundAnnualGrowth2_5(10.0);
        financialDataInput.setTargetPreTaxOperatingMargin(20.0);
        financialDataInput.setConvergenceYearMargin(10.0);
        financialDataInput.setRiskFreeRate(4.0);
        financialDataInput.setInitialCostCapital(800.0);
        financialDataInput.setSegments(new SegmentResponseDTO(List.of(
                new SegmentResponseDTO.Segment("segment-a", "Segment A", List.of("Segment A"), 1.0, 0.5, null),
                new SegmentResponseDTO.Segment("segment-b", "Segment B", List.of("Segment B"), 1.0, 0.5, null))));
        financialDataInput.getOverrideAssumptionReturnOnCapital()
                .setIsOverride(true);
        financialDataInput.getOverrideAssumptionReturnOnCapital()
                .setOverrideCost(15.0);
        financialDataInput.getFinancialDataDTO().setRevenueTTM(100.0);
        financialDataInput.getFinancialDataDTO().setRevenueLTM(90.0);
        financialDataInput.getFinancialDataDTO().setOperatingIncomeTTM(10.0);
        financialDataInput.getFinancialDataDTO().setEffectiveTaxRate(0.25);
        financialDataInput.getFinancialDataDTO().setMarginalTaxRate(25.0);
        financialDataInput.getFinancialDataDTO().setMinorityInterestTTM(0.0);
        financialDataInput.getFinancialDataDTO().setNonOperatingAssetTTM(0.0);
        financialDataInput.getFinancialDataDTO().setResearchAndDevelopmentMap(Map.of("currentR&D-0", 0.0));

        SegmentWeightedParameters params = new SegmentWeightedParameters();
        params.setWeightedRevenueNextYear(10.0);
        params.setWeightedCompoundAnnualGrowth2_5(10.0);
        params.setWeightedOperatingMarginNextYear(10.0);
        params.setWeightedTargetPreTaxOperatingMargin(20.0);
        params.setConvergenceYearMargin(10.0);
        params.setWeightedSalesToCapitalYears1To5(2.0);
        params.setWeightedSalesToCapitalYears6To10(2.0);
        params.setWeightedInitialCostCapital(800.0);
        params.setRiskFreeRate(4.0);
        params.setSegmentWeighted(true);
        params.setSegmentCount(2);
        params.setBaselineQuality("prospectus_explicit_scenario");
        params.setSegmentCoveragePct(100.0);
        params.setSectorParameters("segment-a", sectorParams("segment-a", 0.5));
        params.setSectorParameters("segment-b", sectorParams("segment-b", 0.5));

        when(commonService.calculateRDConverterValue(
                "unmapped-prospectus",
                25.0,
                financialDataInput.getFinancialDataDTO().getResearchAndDevelopmentMap(),
                null)).thenReturn(new RDResult(0.0, 0.0, 0.0, 0.0));
        when(commonService.calculateOperatingLeaseConverter()).thenReturn(new LeaseResultDTO(0.0, 0.0, 0.0, 0.0));
        when(commonService.resolveEquityRiskPremiumForCountry("United States")).thenReturn(4.0);

        try {
            SegmentParameterContext.setParameters(params);
            var output = valuationOutputService.getValuationOutput("SCEN", financialDataInput, null);
            int terminalIndex = output.getFinancialDTO().getArrayLength() - 1;
            double ebitAfterTax = output.getFinancialDTO().getEbit1MinusTaxBySector().values().stream()
                    .mapToDouble(values -> values[terminalIndex])
                    .sum();
            double reinvestment = output.getFinancialDTO().getReinvestment()[terminalIndex];

            assertEquals((4.0 / 15.0) * ebitAfterTax, reinvestment, 0.0001);
        } finally {
            SegmentParameterContext.clear();
        }
    }

    @Test
    void testCalculatePVCFOverNextYear() {
        Double[] pvFcff = new Double[] { 10.0, 20.0, 30.0 };
        Double result = ReflectionTestUtils.invokeMethod(valuationOutputService, "calculatePVCFOverNextYear",
                (Object) pvFcff);
        assertEquals(60.0, result);
    }

    private static SegmentWeightedParameters.SectorParameters sectorParams(String sectorName, double revenueShare) {
        SegmentWeightedParameters.SectorParameters params = new SegmentWeightedParameters.SectorParameters();
        params.setSectorName(sectorName);
        params.setRevenueShare(revenueShare);
        params.setBaseRevenue(50.0);
        params.setTargetRevenue(100.0);
        params.setRevenueNextYear(10.0);
        params.setCompoundAnnualGrowth2_5(10.0);
        params.setTerminalGrowthRate(0.04);
        params.setOperatingMarginNextYear(10.0);
        params.setTargetPreTaxOperatingMargin(20.0);
        params.setConvergenceYearMargin(10.0);
        params.setSalesToCapitalYears1To5(2.0);
        params.setSalesToCapitalYears6To10(2.0);
        params.setInitialCostCapital(800.0);
        params.setIndustryAsPerExcel(sectorName);
        return params;
    }

    @Test
    void testCalculatePVFCFF() {
        Double[] fcff = new Double[] { 100.0, 110.0, 120.0, 130.0 };
        Double[] discountFactor = new Double[] { 0.9, 0.8, 0.7, 0.6 };

        Double[] result = ReflectionTestUtils.invokeMethod(valuationOutputService, "calculatePVFCFF", fcff,
                discountFactor);

        assertEquals(4, result.length);
        assertNotNull(result[1]);
        assertEquals(88.0, result[1]);
        assertEquals(84.0, result[2]);
        assertNull(result[3]); // Terminal year is null because of object array initialization
    }

    @Test
    void testCalculateDiscountFactor() {
        Double[] costOfCapital = new Double[] { 0.1, 0.1, 0.1 };
        Double[] result = ReflectionTestUtils.invokeMethod(valuationOutputService, "calculateDiscountFactor",
                (Object) costOfCapital);

        assertEquals(3, result.length);
        assertNotNull(result[1]);
        assertTrue(result[1] > 0);
    }

    @Test
    void testCalculateEarningBeforeTaxAndIntrest() {
        Double[] ebit = new Double[] { 100.0, 200.0, 300.0 };
        Double[] taxRate = new Double[] { 0.2, 0.25, 0.2 };
        Double[] nol = new Double[] { 0.0, 0.0, 0.0 };

        Double[] result = ReflectionTestUtils.invokeMethod(valuationOutputService,
                "calculateEarningBeforeTaxAndIntrest", ebit, taxRate, nol);

        assertEquals(3, result.length);
        assertNotNull(result[1]);
        assertNotNull(result[2]);
    }

    @Test
    void testCalculateFCFF() {
        Double[] reinvestment = new Double[] { 20.0, 30.0, 40.0 };
        Double[] ebitAfterTaxes = new Double[] { 80.0, 150.0, 200.0 };

        Double[] result = ReflectionTestUtils.invokeMethod(valuationOutputService, "calculateFCFF", reinvestment,
                ebitAfterTaxes);

        assertEquals(3, result.length);
        assertNotNull(result[1]);
        assertEquals(120.0, result[1], 0.001);
    }

    @Test
    void testCalculateProceedsIfCompanyFails() {
        Double sumOfPV = 1000.0;
        financialDataInput.getFinancialDataDTO().setBookValueDebtTTM(200.0);
        financialDataInput.getFinancialDataDTO().setBookValueEqualityTTM(800.0);

        Double result = ReflectionTestUtils.invokeMethod(valuationOutputService, "calculateProceedsIfCompanyFails",
                financialDataInput, sumOfPV);

        assertNotNull(result);
    }

    @Test
    void testCalculateReinvestment() {
        Double[] revenues = new Double[] { 100.0, 120.0, 150.0 };
        Double[] salesToCapitalRatio = new Double[] { 2.0, 2.0, 2.0 };
        Double[] revenueGrowth = new Double[] { 0.1, 0.2, 0.25 };
        Double[] costOfCapital = new Double[] { 0.1, 0.1, 0.1 };
        Double[] ebitBeforeTax = new Double[] { 10.0, 12.0, 15.0 };

        Double[] result = ReflectionTestUtils.invokeMethod(valuationOutputService, "calculateReinvestment",
                financialDataInput, revenues, salesToCapitalRatio, revenueGrowth, costOfCapital, ebitBeforeTax, "AAPL");

        assertNotNull(result);
        assertEquals(3, result.length);
    }

    @Test
    void testCalculateCompanyData() {
        FinancialDTO financialDTO = new FinancialDTO();
        financialDTO.setPvFcff(new Double[] { 10.0, 20.0, 0.0 });
        financialDTO.setComulatedDiscountedFactor(new Double[] { 0.9, 0.8, 0.7 });
        financialDTO.setArrayLength(3);

        OptionValueResultDTO optionValueResultDTO = new OptionValueResultDTO(0.0, 0.0);
        LeaseResultDTO leaseResultDTO = new LeaseResultDTO();

        financialDTO.setFcff(new Double[] { 10.0, 20.0, 100.0 });
        financialDTO.setCostOfCapital(new Double[] { 0.1, 0.1, 0.1 });
        financialDTO.setRevenueGrowthRate(new Double[] { 0.1, 0.1, 0.05 });
        financialDTO.setRevenues(new Double[] { 100.0, 110.0, 115.0 });
        financialDataInput.setRiskFreeRate(4.0);

        CompanyDTO companyDTO = valuationOutputService.calculateCompanyData(financialDTO, financialDataInput,
                optionValueResultDTO, leaseResultDTO);

        assertNotNull(companyDTO);
        assertEquals(0.0, companyDTO.getProbabilityOfFailure());
    }

    @Test
    void calculateCompanyDataRejectsMissingShareCountBeforePerShareMath() {
        FinancialDTO financialDTO = new FinancialDTO();
        financialDTO.setPvFcff(new Double[] { 10.0, 20.0, 0.0 });
        financialDTO.setComulatedDiscountedFactor(new Double[] { 0.9, 0.8, 0.7 });
        financialDTO.setArrayLength(3);
        financialDTO.setFcff(new Double[] { 10.0, 20.0, 100.0 });
        financialDTO.setCostOfCapital(new Double[] { 0.1, 0.1, 0.1 });
        financialDTO.setRevenueGrowthRate(new Double[] { 0.1, 0.1, 0.05 });
        financialDTO.setRevenues(new Double[] { 100.0, 110.0, 115.0 });
        financialDataInput.setRiskFreeRate(4.0);
        financialDataInput.getFinancialDataDTO().setNoOfShareOutstanding(null);

        InsufficientFinancialDataException error = assertThrows(
                InsufficientFinancialDataException.class,
                () -> valuationOutputService.calculateCompanyData(
                        financialDTO,
                        financialDataInput,
                        new OptionValueResultDTO(0.0, 0.0),
                        new LeaseResultDTO()));

        assertEquals("shares_outstanding is required for per-share valuation.", error.getMessage());
    }
}
