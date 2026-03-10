package io.stockvaluation.service;

import io.stockvaluation.dto.LeaseResultDTO;
import io.stockvaluation.dto.OptionValueResultDTO;
import io.stockvaluation.dto.OverrideAssumption;
import io.stockvaluation.dto.valuationoutput.CompanyDTO;
import io.stockvaluation.dto.valuationoutput.FinancialDTO;
import io.stockvaluation.form.FinancialDataInput;
import io.stockvaluation.repository.IndustryAveragesGlobalRepository;
import io.stockvaluation.repository.InputStatRepository;
import io.stockvaluation.repository.SectorMappingRepository;
import io.stockvaluation.dto.FinancialDataDTO;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.*;

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
    void testCalculatePVCFOverNextYear() {
        Double[] pvFcff = new Double[] { 10.0, 20.0, 30.0 };
        Double result = ReflectionTestUtils.invokeMethod(valuationOutputService, "calculatePVCFOverNextYear",
                (Object) pvFcff);
        assertEquals(60.0, result);
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
}
