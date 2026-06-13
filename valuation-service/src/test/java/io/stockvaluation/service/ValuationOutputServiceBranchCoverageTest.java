package io.stockvaluation.service;

import io.stockvaluation.constant.RDResult;
import io.stockvaluation.dto.LeaseResultDTO;
import io.stockvaluation.dto.OptionValueResultDTO;
import io.stockvaluation.dto.OverrideAssumption;
import io.stockvaluation.dto.valuationoutput.CompanyDTO;
import io.stockvaluation.dto.valuationoutput.FinancialDTO;
import io.stockvaluation.dto.FinancialDataDTO;
import io.stockvaluation.form.FinancialDataInput;
import io.stockvaluation.repository.IndustryAveragesGlobalRepository;
import io.stockvaluation.repository.InputStatRepository;
import io.stockvaluation.repository.SectorMappingRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Arrays;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Branch-coverage focused tests for ValuationOutputService.
 * Uses ReflectionTestUtils to invoke private methods directly so each
 * conditional path is exercised independently of the full DCF pipeline.
 */
@ExtendWith(MockitoExtension.class)
class ValuationOutputServiceBranchCoverageTest {

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

    private FinancialDataInput baseInput;

    @BeforeEach
    void setUp() {
        baseInput = new FinancialDataInput();
        FinancialDataDTO dto = new FinancialDataDTO();
        dto.setBookValueDebtTTM(100.0);
        dto.setCashAndMarkablTTM(50.0);
        dto.setBookValueEqualityTTM(300.0);
        dto.setStockPrice(150.0);
        dto.setNoOfShareOutstanding(1_000.0);
        dto.setOperatingIncomeTTM(200.0);
        dto.setRevenueTTM(1_000.0);
        dto.setMarginalTaxRate(21.0);
        baseInput.setFinancialDataDTO(dto);

        // Default overrides (all disabled)
        baseInput.setOverrideAssumptionReinvestmentLag(new OverrideAssumption(0.0, false, 0.0, null));
        baseInput.setOverrideAssumptionReturnOnCapital(new OverrideAssumption(0.0, false, 0.0, null));
        baseInput.setOverrideAssumptionNOL(new OverrideAssumption(0.0, false, 0.0, null));
        baseInput.setOverrideAssumptionCostCapital(new OverrideAssumption(0.0, false, 0.0, null));
        baseInput.setOverrideAssumptionRiskFreeRate(new OverrideAssumption(0.0, false, 0.0, null));
        baseInput.setOverrideAssumptionGrowthRate(new OverrideAssumption(0.0, false, 0.0, null));
        baseInput.setOverrideAssumptionProbabilityOfFailure(new OverrideAssumption(0.0, false, 0.0, "V"));
        baseInput.setOverrideAssumptionCashPosition(new OverrideAssumption(0.0, false, 0.0, null));
        baseInput.setOverrideAssumptionTaxRate(new OverrideAssumption(0.0, false, 0.0, null));

        baseInput.setOperatingMarginNextYear(22.0);
        baseInput.setTargetPreTaxOperatingMargin(20.0);
        baseInput.setConvergenceYearMargin(5.0);
        baseInput.setSalesToCapitalYears1To5(2.0);
        baseInput.setSalesToCapitalYears6To10(2.0);
        baseInput.setRiskFreeRate(400.0); // stored as hundredths (4.0%)
        baseInput.setInitialCostCapital(800.0); // 8.0%
        baseInput.setRevenueNextYear(5.0);
        baseInput.setCompoundAnnualGrowth2_5(8.0);
    }

    // =========================================================
    // calculateEbitMargin — branch coverage
    // =========================================================

    @Test
    void calculateEbitMargin_noLease_noCapitalize() {
        baseInput.setHasOperatingLease(false);
        baseInput.setIsExpensesCapitalize(false);

        LeaseResultDTO lease = new LeaseResultDTO(0.0, 0.0, 0.0, 0.0);
        RDResult rd = new RDResult(0.0, 0.0, 0.0, 0.0);

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateEbitMargin", baseInput, rd, lease, 4);

        assertNotNull(result);
        assertEquals(4, result.length);
        // base year margin = operatingIncome / revenue * 100
        assertEquals(20.0, result[0], 0.01);
    }

    @Test
    void calculateEbitMargin_hasLease_noCapitalize() {
        baseInput.setHasOperatingLease(true);
        baseInput.setIsExpensesCapitalize(false);

        LeaseResultDTO lease = new LeaseResultDTO(10.0, 5.0, 50.0, 0.0);
        RDResult rd = new RDResult(0.0, 0.0, 0.0, 0.0);

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateEbitMargin", baseInput, rd, lease, 4);

        assertNotNull(result);
        // base margin includes lease adjustment to operating income
        assertTrue(result[0] > 20.0); // lease adjustment increases operating income
    }

    @Test
    void calculateEbitMargin_hasLease_andCapitalize() {
        baseInput.setHasOperatingLease(true);
        baseInput.setIsExpensesCapitalize(true);

        LeaseResultDTO lease = new LeaseResultDTO(10.0, 5.0, 50.0, 0.0);
        RDResult rd = new RDResult(100.0, 20.0, 80.0, 16.8);

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateEbitMargin", baseInput, rd, lease, 4);

        assertNotNull(result);
        // Both lease and R&D adjustments applied
        assertTrue(result[0] > 20.0);
    }

    @Test
    void calculateEbitMargin_noLease_andCapitalize() {
        baseInput.setHasOperatingLease(false);
        baseInput.setIsExpensesCapitalize(true);

        LeaseResultDTO lease = new LeaseResultDTO(0.0, 0.0, 0.0, 0.0);
        RDResult rd = new RDResult(100.0, 20.0, 80.0, 16.8);

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateEbitMargin", baseInput, rd, lease, 4);

        assertNotNull(result);
        // R&D adjustment only (no lease)
        assertTrue(result[0] > 20.0);
    }

    @Test
    void calculateEbitMargin_yearExceedsConvergenceYear_takesTargetMargin() {
        // Convergence year = 1 → year 2 already past it
        baseInput.setConvergenceYearMargin(1.0);
        baseInput.setOperatingMarginNextYear(22.0);
        baseInput.setTargetPreTaxOperatingMargin(30.0);
        baseInput.setHasOperatingLease(false);
        baseInput.setIsExpensesCapitalize(false);

        LeaseResultDTO lease = new LeaseResultDTO(0.0, 0.0, 0.0, 0.0);
        RDResult rd = new RDResult(0.0, 0.0, 0.0, 0.0);

        // arrayLength=4 means projectionYears=2, year 2 > convergenceYear(1)
        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateEbitMargin", baseInput, rd, lease, 4);

        assertNotNull(result);
        // Year 2 should equal target margin
        assertEquals(30.0, result[2], 0.01);
    }

    @Test
    void calculateEbitMargin_yearOneUsesOperatingMarginNextYearAndThenConverges() {
        baseInput.setOperatingMarginNextYear(24.0);
        baseInput.setTargetPreTaxOperatingMargin(30.0);
        baseInput.setConvergenceYearMargin(5.0);
        baseInput.setHasOperatingLease(false);
        baseInput.setIsExpensesCapitalize(false);

        LeaseResultDTO lease = new LeaseResultDTO(0.0, 0.0, 0.0, 0.0);
        RDResult rd = new RDResult(0.0, 0.0, 0.0, 0.0);

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateEbitMargin", baseInput, rd, lease, 7);

        assertNotNull(result);
        assertEquals(24.0, result[1], 0.01);
        assertTrue(result[2] > result[1]);
        assertEquals(30.0, result[5], 0.01);
        assertEquals(result[5], result[6], 0.01);
    }

    // =========================================================
    // calculateNOL — branch coverage
    // =========================================================

    @Test
    void calculateNOL_noOverride_noNegativeIncome() {
        Double[] ebitIncome = { 100.0, 200.0, 300.0 };

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateNOL", ebitIncome, baseInput);

        assertNotNull(result);
        assertEquals(0.0, result[0]); // baseNol = 0
        assertEquals(0.0, result[1]); // NOL consumed
        assertEquals(0.0, result[2]);
    }

    @Test
    void calculateNOL_withOverride_baseNolSet() {
        baseInput.setOverrideAssumptionNOL(new OverrideAssumption(500.0, true, 0.0, null));
        Double[] ebitIncome = { 100.0, 300.0, 400.0 };

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateNOL", ebitIncome, baseInput);

        assertEquals(500.0, result[0]); // base NOL from override
        assertEquals(200.0, result[1]); // 500 - 300 = 200 remaining
        assertEquals(0.0, result[2]); // 200 - 400 → clamped to 0
    }

    @Test
    void calculateNOL_negativeEbitIncome_increasesNOL() {
        // ebitIncome[0] is base year (skipped by loop)
        // year=1: ebitIncome[1]=-30 < 0 → nol[1] = nol[0] - (-30) = 0 + 30 = 30
        // year=2: ebitIncome[2]=100 > nol[1]=30 → nol[2] = 0
        Double[] ebitIncome = { -50.0, -30.0, 100.0 };

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateNOL", ebitIncome, baseInput);

        assertEquals(0.0, result[0]); // base NOL
        assertEquals(30.0, result[1]); // nol[0] - ebitIncome[1] = 0 - (-30) = 30
        assertEquals(0.0, result[2]); // 30 - 100 → clamped to 0
    }

    @Test
    void calculateNOL_nolGreaterThanEbit_decreasesNOL() {
        baseInput.setOverrideAssumptionNOL(new OverrideAssumption(1000.0, true, 0.0, null));
        Double[] ebitIncome = { 0.0, 200.0, 300.0 };

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateNOL", ebitIncome, baseInput);

        assertEquals(1000.0, result[0]);
        assertEquals(800.0, result[1]); // 1000 - 200 = 800
        assertEquals(500.0, result[2]); // 800 - 300 = 500
    }

    // =========================================================
    // calculateProbabilityOfFailure — branch coverage
    // =========================================================

    @Test
    void calculateProbabilityOfFailure_withOverride() {
        baseInput.setOverrideAssumptionProbabilityOfFailure(new OverrideAssumption(5.0, true, 0.0, "V"));

        Double result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateProbablityOfFailure", baseInput);

        assertEquals(5.0, result);
    }

    @Test
    void calculateProbabilityOfFailure_noOverride_returnsZero() {
        // Already set to false in setUp()
        Double result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateProbablityOfFailure", baseInput);

        assertEquals(0.0, result);
    }

    // =========================================================
    // calculateProceedsIfCompanyFails — branch coverage
    // =========================================================

    @Test
    void calculateProceedsIfCompanyFails_bookValuePath() {
        baseInput.setOverrideAssumptionProbabilityOfFailure(new OverrideAssumption(10.0, true, 50.0, "B"));
        baseInput.getFinancialDataDTO().setBookValueEqualityTTM(400.0);
        baseInput.getFinancialDataDTO().setBookValueDebtTTM(200.0);

        Double result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateProceedsIfCompanyFails", baseInput, 1000.0);

        // fairValue = 50/100 = 0.5; proceeds = (400+200) * 0.5 = 300
        assertEquals(300.0, result, 0.01);
    }

    @Test
    void calculateProceedsIfCompanyFails_dcfValuePath() {
        baseInput.setOverrideAssumptionProbabilityOfFailure(new OverrideAssumption(10.0, true, 40.0, "V"));

        Double result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateProceedsIfCompanyFails", baseInput, 1000.0);

        // fairValue = 40/100 = 0.4; proceeds = 1000 * 0.4 = 400
        assertEquals(400.0, result, 0.01);
    }

    @Test
    void calculateProceedsIfCompanyFails_unknownRadioValue_returnsZero() {
        baseInput.setOverrideAssumptionProbabilityOfFailure(new OverrideAssumption(10.0, true, 50.0, "X"));

        Double result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateProceedsIfCompanyFails", baseInput, 1000.0);

        assertEquals(0.0, result);
    }

    // =========================================================
    // calculateCash — branch coverage
    // =========================================================

    @Test
    void calculateCash_withOverride() {
        baseInput.setOverrideAssumptionCashPosition(new OverrideAssumption(10.0, true, 5.0, null));
        baseInput.getFinancialDataDTO().setCashAndMarkablTTM(100.0);
        baseInput.getFinancialDataDTO().setMarginalTaxRate(25.0);

        Double result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateCash", baseInput);

        // 100 - 10 * (25 - 5) / 100 = 100 - 2.0 = 98
        assertEquals(98.0, result, 0.001);
    }

    @Test
    void calculateCash_noOverride_returnsCash() {
        // Uses default false override from setUp
        Double result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateCash", baseInput);

        assertEquals(50.0, result);
    }

    // =========================================================
    // calculateReinvestment — override lag branches
    // =========================================================

    private Double[] revenues() {
        return new Double[] { 1000.0, 1080.0, 1160.0, 1250.0 };
    }

    private Double[] stcRatio(int length) {
        Double[] stc = new Double[length];
        Arrays.fill(stc, 2.0);
        return stc;
    }

    private Double[] revenueGrowth(int length) {
        Double[] g = new Double[length];
        Arrays.fill(g, 5.0);
        return g;
    }

    private Double[] costOfCapital(int length) {
        Double[] c = new Double[length];
        Arrays.fill(c, 8.0);
        return c;
    }

    private Double[] ebitBeforeTax(int length) {
        Double[] e = new Double[length];
        Arrays.fill(e, 200.0);
        return e;
    }

    @Test
    void calculateReinvestment_noOverride_standardBehaviour() {
        Double[] rev = revenues();
        Double[] stc = stcRatio(rev.length);
        Double[] g = revenueGrowth(rev.length);
        Double[] coc = costOfCapital(rev.length);
        Double[] ebit = ebitBeforeTax(rev.length);

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateReinvestment",
                baseInput, rev, stc, g, coc, ebit, "AAPL");

        assertNotNull(result);
        assertEquals(rev.length, result.length);
        // Terminal year reinvestment: g/100 / terminalROIC/100 * ebit[terminal]
        assertNotNull(result[result.length - 1]);
    }

    @Test
    void calculateReinvestment_withLag0_usesCurrentToNext() {
        baseInput.setOverrideAssumptionReinvestmentLag(new OverrideAssumption(0.0, true, 0.0, null));
        Double[] rev = revenues();
        Double[] stc = stcRatio(rev.length);
        Double[] g = revenueGrowth(rev.length);
        Double[] coc = costOfCapital(rev.length);
        Double[] ebit = ebitBeforeTax(rev.length);

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateReinvestment",
                baseInput, rev, stc, g, coc, ebit, "AAPL");

        assertNotNull(result);
        // Year 1: (rev[1] - rev[0]) / stc[1] = (1080-1000)/2 = 40
        assertEquals(40.0, result[1], 0.01);
    }

    @Test
    void calculateReinvestment_withLag1_usesNextToNext() {
        baseInput.setOverrideAssumptionReinvestmentLag(new OverrideAssumption(1.0, true, 0.0, null));
        Double[] rev = revenues();
        Double[] stc = stcRatio(rev.length);
        Double[] g = revenueGrowth(rev.length);
        Double[] coc = costOfCapital(rev.length);
        Double[] ebit = ebitBeforeTax(rev.length);

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateReinvestment",
                baseInput, rev, stc, g, coc, ebit, "AAPL");

        assertNotNull(result);
        // Year 1: (rev[2] - rev[1]) / stc[1] = (1160-1080)/2 = 40
        assertEquals(40.0, result[1], 0.01);
    }

    @Test
    void calculateReinvestment_withLag2() {
        baseInput.setOverrideAssumptionReinvestmentLag(new OverrideAssumption(2.0, true, 0.0, null));
        // Need at least 5 elements for lag=2 to use year+2 safely
        Double[] rev = new Double[] { 1000.0, 1080.0, 1160.0, 1250.0, 1350.0, 0.0 };
        Double[] stc = stcRatio(rev.length);
        Double[] g = revenueGrowth(rev.length);
        Double[] coc = costOfCapital(rev.length);
        Double[] ebit = ebitBeforeTax(rev.length);

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateReinvestment",
                baseInput, rev, stc, g, coc, ebit, "AAPL");

        assertNotNull(result);
    }

    @Test
    void calculateReinvestment_withLag3() {
        baseInput.setOverrideAssumptionReinvestmentLag(new OverrideAssumption(3.0, true, 0.0, null));
        Double[] rev = new Double[] { 1000.0, 1080.0, 1160.0, 1250.0, 1350.0, 1460.0, 0.0 };
        Double[] stc = stcRatio(rev.length);
        Double[] g = revenueGrowth(rev.length);
        Double[] coc = costOfCapital(rev.length);
        Double[] ebit = ebitBeforeTax(rev.length);

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateReinvestment",
                baseInput, rev, stc, g, coc, ebit, "AAPL");

        assertNotNull(result);
    }

    @Test
    void calculateReinvestment_returnOnCapitalOverride() {
        baseInput.setOverrideAssumptionReturnOnCapital(new OverrideAssumption(15.0, true, 0.0, null));
        Double[] rev = revenues();
        Double[] stc = stcRatio(rev.length);
        Double[] g = revenueGrowth(rev.length);
        Double[] coc = costOfCapital(rev.length);
        Double[] ebit = ebitBeforeTax(rev.length);

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateReinvestment",
                baseInput, rev, stc, g, coc, ebit, "AAPL");

        assertNotNull(result);
        // Terminal: uses overridden ROIC of 15%
        assertNotNull(result[result.length - 1]);
    }

    // =========================================================
    // calculateRevenueGrowthRate — branch coverage
    // =========================================================

    @Test
    void calculateRevenueGrowthRate_terminalGrowthRateOverride_bypassesCap() {
        baseInput.setTerminalGrowthRate(6.0); // explicit override
        baseInput.setRiskFreeRate(400.0); // riskFreeRate in hundredths

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateRevenueGrowthRate", baseInput, 4);

        assertNotNull(result);
        // Terminal index = arrayLength - 1 = 3
        assertEquals(6.0, result[3], 0.01); // Override used directly
    }

    @Test
    void calculateRevenueGrowthRate_overrideGrowthRate_usedForTerminal() {
        baseInput.setOverrideAssumptionGrowthRate(new OverrideAssumption(3.5, true, 0.0, null));

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateRevenueGrowthRate", baseInput, 4);

        assertNotNull(result);
        assertEquals(3.5, result[3], 0.01);
    }

    @Test
    void calculateRevenueGrowthRate_overrideRiskFreeRate_forTerminal() {
        baseInput.setOverrideAssumptionRiskFreeRate(new OverrideAssumption(3.0, true, 0.0, null));

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateRevenueGrowthRate", baseInput, 4);

        assertNotNull(result);
        // Terminal uses overridden risk-free rate (capped)
        assertEquals(3.0, result[3], 0.01);
    }

    @Test
    void calculateRevenueGrowthRate_noOverride_defaultsBelowRiskFreeRate() {
        // riskFreeRate = 400.0 stored → divide by 100 → 4.0%
        // compound growth 8% → terminal should default below the risk-free cap.
        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateRevenueGrowthRate", baseInput, 12);

        assertNotNull(result);
        assertEquals(2.5, result[11], 0.01);
    }

    @Test
    void calculateRevenueGrowthRate_noOverride_respectsLowRiskFreeCap() {
        baseInput.setRiskFreeRate(150.0);

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateRevenueGrowthRate", baseInput, 12);

        assertNotNull(result);
        assertEquals(1.5, result[11], 0.01);
    }

    @Test
    void calculateRevenueGrowthRate_terminalRevenueSolvesImpliedGrowthPath() {
        baseInput.setTerminalRevenue(2_000.0);
        baseInput.setTerminalRevenueYear(10);

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateRevenueGrowthRate", baseInput, 12);

        assertNotNull(result);
        assertEquals(2.5, result[11], 0.01);
        double revenue = baseInput.getFinancialDataDTO().getRevenueTTM();
        for (int year = 1; year <= 10; year++) {
            revenue *= 1.0 + result[year] / 100.0;
        }
        assertEquals(2_000.0, revenue, 1.0);
    }

    @Test
    void calculateRevenueGrowthRate_terminalRevenueRejectsUnsupportedTargetYear() {
        baseInput.setTerminalRevenue(2_000.0);
        baseInput.setTerminalRevenueYear(11);

        assertThrows(IllegalArgumentException.class, () -> ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateRevenueGrowthRate", baseInput, 12));
    }

    // =========================================================
    // calculateRevenueGrowthRateMarkov — edge cases
    // =========================================================

    @Test
    void calculateRevenueGrowthRateMarkov_happyPath() {
        List<Double> history = List.of(0.05, 0.07, 0.06, 0.08, 0.04, 0.09);
        baseInput.setRiskFreeRate(4.0);
        baseInput.setRevenueNextYear(0.06);

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateRevenueGrowthRateMarkov",
                history, 5, 3, baseInput);

        assertNotNull(result);
        assertEquals(6, result.length);
        for (int i = 1; i <= 5; i++) {
            assertNotNull(result[i]);
        }
    }

    @Test
    void calculateRevenueGrowthRateMarkov_allHistoricalValuesEqual() {
        // Edge case: max == min → all states assigned to middle bin
        List<Double> history = List.of(0.05, 0.05, 0.05, 0.05);
        baseInput.setRiskFreeRate(4.0);
        baseInput.setRevenueNextYear(null); // no analyst estimate

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateRevenueGrowthRateMarkov",
                history, 3, 3, baseInput);

        assertNotNull(result);
        assertEquals(4, result.length);
    }

    @Test
    void calculateRevenueGrowthRateMarkov_insufficientHistory_throws() {
        List<Double> history = List.of(0.05); // only 1 row → < 2 required

        assertThrows(IllegalArgumentException.class, () -> ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateRevenueGrowthRateMarkov",
                history, 3, 3, baseInput));
    }

    @Test
    void calculateRevenueGrowthRateMarkov_nullHistory_throws() {
        assertThrows(IllegalArgumentException.class, () -> ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateRevenueGrowthRateMarkov",
                (List<Double>) null, 3, 3, baseInput));
    }

    // =========================================================
    // calculatePVFCFF — with null elements
    // =========================================================

    @Test
    void calculatePVFCFF_withNullElements_skipsNull() {
        Double[] fcff = { null, 100.0, null, 200.0 };
        Double[] discountFactor = { null, 0.9, null, 0.7 };

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculatePVFCFF", fcff, discountFactor);

        assertNotNull(result);
        assertNull(result[0]); // base year
        assertEquals(90.0, result[1], 0.001);
        assertNull(result[2]); // both null
        // terminal index [3] always 0.0 (not set for terminal)
    }

    // =========================================================
    // calculateEarningBeforeTaxAndIntrest — branch: ebit <0
    // =========================================================

    @Test
    void calculateEarningBeforeTax_negativeEbit_isReturnedAsIs() {
        Double[] ebit = { -100.0, -200.0, 300.0 };
        Double[] taxRate = { 21.0, 21.0, 21.0 };
        Double[] nol = { 0.0, 0.0, 200.0 };

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateEarningBeforeTaxAndIntrest", ebit, taxRate, nol);

        // base year negative → returned as-is
        assertEquals(-100.0, result[0], 0.001);
        // year 1 negative → returned as-is
        assertEquals(-200.0, result[1], 0.001);
        // terminal year: positive ebit * (1-t)
        assertNotNull(result[2]);
    }

    @Test
    void calculateEarningBeforeTax_ebitLessThanNOL_fullShield() {
        // ebit < nol → full NOL shield (ebit not reduced by tax)
        Double[] ebit = { 100.0, 50.0, 300.0 };
        Double[] taxRate = { 20.0, 20.0, 20.0 };
        Double[] nol = { 0.0, 100.0, 0.0 }; // nol[1]=100 > ebit[1]=50

        Double[] result = ReflectionTestUtils.invokeMethod(
                valuationOutputService, "calculateEarningBeforeTaxAndIntrest", ebit, taxRate, nol);

        // year 1: ebitIncome(50) < nol(100) → result is ebitIncome (no tax)
        assertEquals(50.0, result[1], 0.001);
    }

    // =========================================================
    // calculateCompanyData — probability of failure > 0
    // =========================================================

    @Test
    void calculateCompanyData_probabilityOfFailure_nonZero() {
        baseInput.setOverrideAssumptionProbabilityOfFailure(new OverrideAssumption(10.0, true, 20.0, "V"));
        baseInput.setHasOperatingLease(false);
        baseInput.setHasEmployeeOptions(false);

        FinancialDTO financialDTO = new FinancialDTO();
        financialDTO.setArrayLength(3);
        financialDTO.setPvFcff(new Double[] { null, 100.0, null });
        financialDTO.setComulatedDiscountedFactor(new Double[] { null, 0.9, 0.8 });
        financialDTO.setFcff(new Double[] { null, 100.0, 500.0 });
        financialDTO.setCostOfCapital(new Double[] { null, 8.0, 5.0 });
        financialDTO.setRevenueGrowthRate(new Double[] { null, 8.0, 3.0 });
        financialDTO.setRevenues(new Double[] { 1000.0, 1080.0, null });
        financialDTO.setRoic(new Double[] { null, 12.0, 10.0 });

        OptionValueResultDTO optionValue = new OptionValueResultDTO(0.0, 0.0);
        LeaseResultDTO lease = new LeaseResultDTO(0.0, 0.0, 0.0, 0.0);

        CompanyDTO result = valuationOutputService.calculateCompanyData(
                financialDTO, baseInput, optionValue, lease);

        assertNotNull(result);
        assertEquals(10.0, result.getProbabilityOfFailure(), 0.001);
        // proceeds = sumOfPV * 0.2
        assertNotNull(result.getProceedsIfFirmFails());
    }
}
