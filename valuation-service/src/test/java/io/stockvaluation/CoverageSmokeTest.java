package io.stockvaluation;

import io.stockvaluation.config.CurrencyProviderProperties;
import io.stockvaluation.config.SyntheticRatingProperties;
import io.stockvaluation.config.ValuationTemplateProperties;
import io.stockvaluation.config.YFinanceProviderProperties;
import io.stockvaluation.dto.CompanyDataDTO;
import io.stockvaluation.dto.CompanyDriveDataDTO;
import io.stockvaluation.dto.DividendDataDTO;
import io.stockvaluation.dto.FinancialDataDTO;
import io.stockvaluation.dto.FieldErrorDTO;
import io.stockvaluation.dto.InfoDTO;
import io.stockvaluation.dto.OverrideAssumption;
import io.stockvaluation.dto.ResponseDTO;
import io.stockvaluation.dto.SyntheticResultDTO;
import io.stockvaluation.dto.ValuationOutputDTO;
import io.stockvaluation.dto.ValuationTemplate;
import io.stockvaluation.dto.valuationoutput.CompanyDTO;
import io.stockvaluation.enums.CashflowType;
import io.stockvaluation.enums.EarningsLevel;
import io.stockvaluation.enums.GrowthPattern;
import io.stockvaluation.enums.ModelType;
import io.stockvaluation.form.FinancialDataInput;
import io.stockvaluation.provider.BalanceSheetSnapshot;
import io.stockvaluation.provider.DataProviderException;
import io.stockvaluation.provider.IncomeStatementSnapshot;
import io.stockvaluation.service.ValuationOutputService;
import io.stockvaluation.service.ValuationWorkflowServiceImpl;
import org.junit.jupiter.api.Test;
import org.springframework.http.client.BufferingClientHttpRequestFactory;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.client.RestTemplate;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class CoverageSmokeTest {

    @Test
    void applicationRestTemplateUsesBufferingFactoryAndAllowsNaN() throws Exception {
        RestTemplate restTemplate = new StockValuationBackendApplication().restTemplate();

        assertTrue(restTemplate.getRequestFactory() instanceof BufferingClientHttpRequestFactory);
        MappingJackson2HttpMessageConverter converter = restTemplate.getMessageConverters().stream()
                .filter(MappingJackson2HttpMessageConverter.class::isInstance)
                .map(MappingJackson2HttpMessageConverter.class::cast)
                .findFirst()
                .orElseThrow();
        Map<?, ?> parsed = converter.getObjectMapper().readValue("{\"value\":NaN}", Map.class);
        assertTrue(Double.isNaN((Double) parsed.get("value")));
    }

    @Test
    void enumsReturnExpectedDefaultsAndLegacyMappings() {
        assertEquals(GrowthPattern.STABLE, GrowthPattern.fromString("stable growth"));
        assertEquals(GrowthPattern.THREE_STAGE, GrowthPattern.fromString("three stage"));
        assertEquals(GrowthPattern.N_STAGE, GrowthPattern.fromString("n-stage model"));
        assertEquals(17, GrowthPattern.THREE_STAGE.getArrayLength());
        assertEquals(EarningsLevel.NORMALIZED, EarningsLevel.fromString("Normalized"));
        assertEquals(EarningsLevel.CURRENT, EarningsLevel.fromString(null));
        assertEquals(ModelType.OPTION_PRICING, ModelType.fromString("Option Pricing Model"));
        assertEquals(ModelType.DISCOUNTED_CF, ModelType.fromString("unknown"));
        assertEquals(CashflowType.FCFF, CashflowType.fromString("anything"));
        assertFalse(CashflowType.FCFF.isEquityValuation());
    }

    @Test
    void valuationTemplateAndDividendDtoConvenienceMethodsBehaveAsExpected() {
        ValuationTemplate template = new ValuationTemplate();
        template.setProjectionYears(10);
        template.setArrayLength(12);
        template.setGrowthPattern(GrowthPattern.TWO_STAGE);
        template.setEarningsLevel(EarningsLevel.NORMALIZED);
        template.setCashflowToDiscount(CashflowType.FCFF);
        template.setModelType(ModelType.DISCOUNTED_CF);
        template.setNormalizedOperatingMargin(18.5);
        template.getMetadata().put("legacyCashflowSuggestion", "FCFF");

        assertEquals(11, template.getTerminalYearIndex());
        assertEquals(10, template.getLastProjectionYearIndex());
        assertTrue(template.isFCFFModel());
        assertTrue(template.useNormalizedEarnings());
        assertTrue(template.toString().contains("Two-stage Growth"));

        DividendDataDTO dividendData = DividendDataDTO.builder()
                .dividendRate(2.5)
                .trailingAnnualDividendRate(2.2)
                .payoutRatio(0.5)
                .dividendYield(0.025)
                .dividendHistory(Map.of("2024", 2.4, "2023", 2.2, "2022", 2.0, "2021", 1.8))
                .dividendGrowthRate(0.20)
                .build();

        assertTrue(dividendData.isDividendPaying());
        assertTrue(dividendData.hasSufficientHistory());
        assertTrue(dividendData.isSuitableForDDM());
        assertEquals(2.5, dividendData.getCurrentDividend());
        assertEquals(0.15, dividendData.getEstimatedGrowthRate(0.20));

        dividendData.setDividendRate(null);
        dividendData.setDividendGrowthRate(null);
        assertEquals(2.2, dividendData.getCurrentDividend());
        assertEquals(0.10, dividendData.getEstimatedGrowthRate(0.20));
    }

    @Test
    void dtoCopiesPropertiesAndDelegateToDividendData() {
        DividendDataDTO dividendData = DividendDataDTO.builder().dividendRate(1.0).dividendYield(0.02).payoutRatio(0.5).build();

        CompanyDriveDataDTO driveData = new CompanyDriveDataDTO();
        driveData.setRevenueNextYear(0.12);
        driveData.setRiskFreeRate(4.0);

        FinancialDataDTO financialData = new FinancialDataDTO();
        financialData.setRevenueTTM(100.0);

        CompanyDataDTO companyData = new CompanyDataDTO();
        companyData.setCompanyDriveDataDTO(driveData);
        companyData.setFinancialDataDTO(financialData);
        companyData.setDividendDataDTO(dividendData);

        CompanyDataDTO copy = new CompanyDataDTO(companyData);
        assertSame(driveData, copy.getCompanyDriveDataDTO());
        assertTrue(copy.isDividendPaying());
        assertTrue(copy.isSuitableForDDM());
        assertTrue(companyData.toString().contains("dividendDataDTO"));
        assertTrue(driveData.toString().contains("riskFreeRate"));
        assertTrue(financialData.toString().contains("revenueTTM"));

        CompanyDTO companyDTO = new CompanyDTO();
        companyDTO.setEstimatedValuePerShare(123.45);

        ValuationOutputDTO output = new ValuationOutputDTO();
        output.setCompanyName("Example");
        output.setCompanyDTO(companyDTO);
        output.setPrimaryModel(CashflowType.FCFF);
        output.setValuationId("valuation-1");
        output.setUserValuationId("user-1");

        ValuationOutputDTO outputCopy = new ValuationOutputDTO(output);
        assertEquals(123.45, output.getRecommendedIntrinsicValue());
        assertSame(companyDTO, outputCopy.getCompanyDTO());
        assertEquals("valuation-1", outputCopy.getValuationId());
        assertEquals("user-1", outputCopy.getUserValuationId());

        SyntheticResultDTO syntheticResult = new SyntheticResultDTO("10.0", "A", "1.5", "1.2", "6.7");
        assertEquals("A", syntheticResult.getEstimatedBondRating());

        InfoDTO info = new InfoDTO();
        info.setCompanyName("Example");
        info.setTicker("EXMP");
        info.setWebsite("https://example.com");
        info.setDateOfValuation(java.time.LocalDate.of(2026, 3, 10));
        info.setCountryOfIncorporation("Sweden");
        info.setIndustryUs("software");
        info.setIndustryGlobal("technology");
        info.setNoOfShareOutstanding(10.0);
        info.setStockPrice(100.0);
        info.setLowestStockPrice(90.0);
        info.setHighestStockPrice(110.0);
        info.setPriceChangeFromLastStock(5.0);
        info.setPercentageChangeFromLastStock(5.0);
        info.setPriceChangeCurrentStock(10.0);
        info.setPercentageChangeCurrentStock(9.09);
        assertEquals("Example", info.getCompanyName());
        assertEquals(9.09, info.getPercentageChangeCurrentStock());

        ResponseDTO<String> ok = new ResponseDTO<>("payload");
        ResponseDTO<String> withStatus = new ResponseDTO<>("payload", 202);
        ResponseDTO<String> full = new ResponseDTO<>("payload", "done", true, 200, "OK");
        ResponseDTO<String> custom = new ResponseDTO<>("payload", "message", true, 201);
        ResponseDTO<String> errors = new ResponseDTO<>(java.util.List.of(new FieldErrorDTO("field", "message", null)));
        assertTrue(ok.isSuccess());
        assertEquals(202, withStatus.getHttpStatus());
        assertEquals("OK", full.getErrorCode());
        assertEquals("message", custom.getMessage());
        assertFalse(errors.isSuccess());
    }

    @Test
    void configPropertiesSnapshotsAndExceptionsBehaveAsExpected() {
        ValuationTemplateProperties templateProperties = new ValuationTemplateProperties();
        assertEquals(0.03, templateProperties.getExpectedInflation());
        templateProperties.setDefaultProjectionYears(12);
        assertEquals(12, templateProperties.getDefaultProjectionYears());

        SyntheticRatingProperties syntheticRatingProperties = new SyntheticRatingProperties();
        syntheticRatingProperties.setDefaultCountry("Sweden");
        assertEquals("Sweden", syntheticRatingProperties.getDefaultCountry());

        CurrencyProviderProperties currencyProviderProperties = new CurrencyProviderProperties();
        currencyProviderProperties.setBaseUrl("https://example.com");
        assertEquals("https://example.com", currencyProviderProperties.getBaseUrl());

        YFinanceProviderProperties providerProperties = new YFinanceProviderProperties();
        providerProperties.setBaseUrl("https://yfinance.example.com");
        assertEquals("https://yfinance.example.com", providerProperties.getBaseUrl());

        DataProviderException exception = new DataProviderException("stub", "AAPL", "failed");
        assertEquals("[stub] Failed for ticker 'AAPL': failed", exception.getMessage());

        assertNull(BalanceSheetSnapshot.empty().bookValueEquity());
        assertNull(IncomeStatementSnapshot.empty().totalRevenue());
    }

    @Test
    void userRefinedScenarioKeepsNearTermAndTargetMarginsIndependent() throws Exception {
        ValuationWorkflowServiceImpl workflow = new ValuationWorkflowServiceImpl(null, null, null, null, null, null);
        Method applyUserOverrides = ValuationWorkflowServiceImpl.class.getDeclaredMethod(
                "applyUserOverrides",
                FinancialDataInput.class,
                FinancialDataInput.class);
        applyUserOverrides.setAccessible(true);

        FinancialDataInput baseline = new FinancialDataInput();
        baseline.setRiskFreeRate(4.0);
        baseline.setOperatingMarginNextYear(20.0);
        baseline.setTargetPreTaxOperatingMargin(35.0);

        FinancialDataInput overrides = new FinancialDataInput();
        overrides.setRequestPolicyMode("user_refined_scenario");
        overrides.setOperatingMarginNextYear(27.5);
        overrides.setConvergenceYearMargin(7.0);

        @SuppressWarnings("unchecked")
        java.util.List<String> adjusted = (java.util.List<String>) applyUserOverrides.invoke(workflow, baseline,
                overrides);

        assertEquals("user_refined_scenario", baseline.getRequestPolicyMode());
        assertEquals(27.5, baseline.getOperatingMarginNextYear());
        assertEquals(35.0, baseline.getTargetPreTaxOperatingMargin());
        assertEquals(7.0, baseline.getConvergenceYearMargin());
        assertTrue(adjusted.contains("operatingMarginNextYear"));
        assertTrue(adjusted.contains("convergenceYearMargin"));
        assertFalse(adjusted.contains("targetPreTaxOperatingMargin"));
    }

    @Test
    void userRefinedScenarioAcceptsTerminalRevenueButRejectsTerminalRoic() throws Exception {
        ValuationWorkflowServiceImpl workflow = new ValuationWorkflowServiceImpl(null, null, null, null, null, null);
        Method applyUserOverrides = ValuationWorkflowServiceImpl.class.getDeclaredMethod(
                "applyUserOverrides",
                FinancialDataInput.class,
                FinancialDataInput.class);
        applyUserOverrides.setAccessible(true);

        FinancialDataInput baseline = new FinancialDataInput();
        baseline.setRiskFreeRate(4.0);

        FinancialDataInput overrides = new FinancialDataInput();
        overrides.setRequestPolicyMode("user_refined_scenario");
        overrides.setTerminalRevenue(2_000.0);
        overrides.setTerminalRevenueYear(10);

        @SuppressWarnings("unchecked")
        java.util.List<String> adjusted = (java.util.List<String>) applyUserOverrides.invoke(workflow, baseline,
                overrides);

        assertEquals(2_000.0, baseline.getTerminalRevenue());
        assertEquals(10, baseline.getTerminalRevenueYear());
        assertTrue(adjusted.contains("terminalRevenue"));

        FinancialDataInput terminalRoicOverride = new FinancialDataInput();
        terminalRoicOverride.setRequestPolicyMode("user_refined_scenario");
        terminalRoicOverride.setOverrideAssumptionReturnOnCapital(new OverrideAssumption(14.0, true, 0.0, null));

        InvocationTargetException exception = assertThrows(
                InvocationTargetException.class,
                () -> applyUserOverrides.invoke(workflow, baseline, terminalRoicOverride));
        assertTrue(exception.getCause() instanceof ResponseStatusException);
        assertTrue(exception.getCause().getMessage().contains("overrideAssumptionReturnOnCapital"));
    }

    @Test
    void explicitScenarioAcceptsTerminalRoicOverride() throws Exception {
        ValuationWorkflowServiceImpl workflow = new ValuationWorkflowServiceImpl(null, null, null, null, null, null);
        Method applyUserOverrides = ValuationWorkflowServiceImpl.class.getDeclaredMethod(
                "applyUserOverrides",
                FinancialDataInput.class,
                FinancialDataInput.class);
        applyUserOverrides.setAccessible(true);

        FinancialDataInput baseline = new FinancialDataInput();
        baseline.setRiskFreeRate(4.0);

        FinancialDataInput overrides = new FinancialDataInput();
        overrides.setRequestPolicyMode("explicit_scenario");
        overrides.setOverrideAssumptionReturnOnCapital(new OverrideAssumption(14.0, true, 0.0, null));

        @SuppressWarnings("unchecked")
        java.util.List<String> adjusted = (java.util.List<String>) applyUserOverrides.invoke(workflow, baseline,
                overrides);

        assertTrue(baseline.getOverrideAssumptionReturnOnCapital().getIsOverride());
        assertEquals(14.0, baseline.getOverrideAssumptionReturnOnCapital().getOverrideCost());
        assertTrue(adjusted.contains("overrideAssumptionReturnOnCapital"));
    }

    @Test
    void invalidTerminalGrowthOverrideIsRejectedWithAgentReadableError() throws Exception {
        ValuationWorkflowServiceImpl workflow = new ValuationWorkflowServiceImpl(null, null, null, null, null, null);
        Method applyUserOverrides = ValuationWorkflowServiceImpl.class.getDeclaredMethod(
                "applyUserOverrides",
                FinancialDataInput.class,
                FinancialDataInput.class);
        applyUserOverrides.setAccessible(true);

        FinancialDataInput baseline = new FinancialDataInput();
        baseline.setRiskFreeRate(4.0);

        FinancialDataInput overrides = new FinancialDataInput();
        overrides.setRequestPolicyMode("explicit_scenario");
        overrides.setTerminalGrowthRate(5.0);

        InvocationTargetException exception = assertThrows(
                InvocationTargetException.class,
                () -> applyUserOverrides.invoke(workflow, baseline, overrides));
        assertTrue(exception.getCause() instanceof ResponseStatusException);
        assertTrue(exception.getCause().getMessage().contains("TERMINAL_GROWTH_UNSAFE"));
    }

    @Test
    void userRefinedScenarioRejectsExplicitScenarioOnlyServiceFields() throws Exception {
        ValuationWorkflowServiceImpl workflow = new ValuationWorkflowServiceImpl(null, null, null, null, null, null);
        Method applyUserOverrides = ValuationWorkflowServiceImpl.class.getDeclaredMethod(
                "applyUserOverrides",
                FinancialDataInput.class,
                FinancialDataInput.class);
        applyUserOverrides.setAccessible(true);

        FinancialDataInput baseline = new FinancialDataInput();
        baseline.setRiskFreeRate(4.0);

        FinancialDataInput overrides = new FinancialDataInput();
        overrides.setRequestPolicyMode("user_refined_scenario");
        overrides.setGrowthPatternOverride(GrowthPattern.THREE_STAGE);
        overrides.setInitialCostCapital(8.5);
        overrides.setTerminalGrowthRate(3.0);

        InvocationTargetException exception = assertThrows(
                InvocationTargetException.class,
                () -> applyUserOverrides.invoke(workflow, baseline, overrides));
        assertTrue(exception.getCause() instanceof ResponseStatusException);
        assertTrue(exception.getCause().getMessage().contains("USER_REFINED_SCENARIO_EXPLICIT_ONLY_FIELDS"));
        assertTrue(exception.getCause().getMessage().contains("growthPatternOverride"));
        assertTrue(exception.getCause().getMessage().contains("initialCostCapital"));
        assertTrue(exception.getCause().getMessage().contains("terminalGrowthRate"));
    }

    @Test
    void userRefinedSalesToCapitalInputsBypassMechanicalGuard() throws Exception {
        ValuationWorkflowServiceImpl workflow = new ValuationWorkflowServiceImpl(null, null, null, null, null, null);
        Method adjustSalesToCapital = ValuationWorkflowServiceImpl.class.getDeclaredMethod(
                "adjustSalesToCapitalRatio",
                FinancialDataInput.class,
                java.util.List.class);
        adjustSalesToCapital.setAccessible(true);

        FinancialDataInput input = new FinancialDataInput();
        input.setRequestPolicyMode("user_refined_scenario");
        input.setSalesToCapitalYears1To5(0.75);
        input.setSalesToCapitalYears6To10(1.10);

        adjustSalesToCapital.invoke(workflow, input,
                java.util.List.of("salesToCapitalYears1To5", "salesToCapitalYears6To10"));

        assertEquals(0.75, input.getSalesToCapitalYears1To5());
        assertEquals(1.10, input.getSalesToCapitalYears6To10());
    }

    @Test
    void userRefinedScenarioRejectsOutOfBoundsDirectInputs() throws Exception {
        ValuationWorkflowServiceImpl workflow = new ValuationWorkflowServiceImpl(null, null, null, null, null, null);
        Method applyUserOverrides = ValuationWorkflowServiceImpl.class.getDeclaredMethod(
                "applyUserOverrides",
                FinancialDataInput.class,
                FinancialDataInput.class);
        applyUserOverrides.setAccessible(true);

        FinancialDataInput baseline = new FinancialDataInput();
        baseline.setRiskFreeRate(4.0);

        FinancialDataInput convergenceOverride = new FinancialDataInput();
        convergenceOverride.setRequestPolicyMode("user_refined_scenario");
        convergenceOverride.setConvergenceYearMargin(11.0);

        InvocationTargetException convergenceException = assertThrows(
                InvocationTargetException.class,
                () -> applyUserOverrides.invoke(workflow, baseline, convergenceOverride));
        assertTrue(convergenceException.getCause() instanceof ResponseStatusException);
        assertTrue(convergenceException.getCause().getMessage().contains("SCENARIO_INPUT_OUT_OF_BOUNDS"));
        assertTrue(convergenceException.getCause().getMessage().contains("convergenceYearMargin"));

        FinancialDataInput salesToCapitalOverride = new FinancialDataInput();
        salesToCapitalOverride.setRequestPolicyMode("user_refined_scenario");
        salesToCapitalOverride.setSalesToCapitalYears1To5(-2.0);

        InvocationTargetException salesToCapitalException = assertThrows(
                InvocationTargetException.class,
                () -> applyUserOverrides.invoke(workflow, new FinancialDataInput(), salesToCapitalOverride));
        assertTrue(salesToCapitalException.getCause() instanceof ResponseStatusException);
        assertTrue(salesToCapitalException.getCause().getMessage().contains("SCENARIO_INPUT_OUT_OF_BOUNDS"));
        assertTrue(salesToCapitalException.getCause().getMessage().contains("salesToCapitalYears1To5"));
    }

    @Test
    void userRefinedScenarioDoesNotForceThreeStageFromPriceValueGap() throws Exception {
        ValuationWorkflowServiceImpl workflow = new ValuationWorkflowServiceImpl(null, null, null, null, null, null);
        Method shouldForce = ValuationWorkflowServiceImpl.class.getDeclaredMethod(
                "shouldForceThreeStageTemplate",
                ValuationTemplate.class,
                FinancialDataInput.class,
                ValuationOutputDTO.class);
        shouldForce.setAccessible(true);

        ValuationTemplate template = new ValuationTemplate();
        template.setGrowthPattern(GrowthPattern.STABLE);
        ValuationOutputDTO output = new ValuationOutputDTO();
        CompanyDTO company = new CompanyDTO();
        company.setPrice(300.0);
        company.setEstimatedValuePerShare(100.0);
        output.setCompanyDTO(company);

        FinancialDataInput overrides = new FinancialDataInput();
        overrides.setRequestPolicyMode("user_refined_scenario");

        assertFalse((Boolean) shouldForce.invoke(workflow, template, overrides, output));
    }

    @Test
    void negativeValueCalibrationDoesNotOverwriteExplicitUserRefinedAssumptions() throws Exception {
        ValuationOutputService outputService = mock(ValuationOutputService.class);
        ValuationWorkflowServiceImpl workflow = new ValuationWorkflowServiceImpl(null, null, outputService, null, null,
                null);
        Method applyCalibration = ValuationWorkflowServiceImpl.class.getDeclaredMethod(
                "applyCalibrationAndMLAdjustments",
                String.class,
                FinancialDataInput.class,
                CompanyDataDTO.class,
                ValuationOutputDTO.class,
                boolean.class,
                ValuationTemplate.class,
                boolean.class,
                java.util.List.class);
        applyCalibration.setAccessible(true);

        FinancialDataInput input = new FinancialDataInput();
        input.setRequestPolicyMode("user_refined_scenario");
        input.setCompoundAnnualGrowth2_5(12.0);
        input.setTargetPreTaxOperatingMargin(33.0);

        ValuationOutputDTO negativeCheck = new ValuationOutputDTO();
        CompanyDTO negativeCompany = new CompanyDTO();
        negativeCompany.setEstimatedValuePerShare(-1.0);
        negativeCompany.setPrice(10.0);
        negativeCheck.setCompanyDTO(negativeCompany);

        ValuationOutputDTO preservedOutput = new ValuationOutputDTO();
        when(outputService.getValuationOutput("TST", input, null)).thenReturn(preservedOutput);

        Object result = applyCalibration.invoke(
                workflow,
                "TST",
                input,
                new CompanyDataDTO(),
                negativeCheck,
                false,
                null,
                false,
                new java.util.ArrayList<>(
                        java.util.List.of("compoundAnnualGrowth2_5", "targetPreTaxOperatingMargin")));

        assertSame(preservedOutput, result);
        assertEquals(12.0, input.getCompoundAnnualGrowth2_5());
        assertEquals(33.0, input.getTargetPreTaxOperatingMargin());
    }

    @Test
    void terminalGrowthOverrideCannotBypassRiskFreeRateCapInOutputService() {
        ValuationOutputService outputService = new ValuationOutputService(null, null, null, null, null, null, null);
        FinancialDataInput input = new FinancialDataInput();
        input.setRevenueNextYear(5.0);
        input.setCompoundAnnualGrowth2_5(8.0);
        input.setRiskFreeRate(4.0);
        input.setTerminalGrowthRate(4.5);
        input.setOverrideAssumptionGrowthRate(new OverrideAssumption(0D, false, 0D, null));
        input.setOverrideAssumptionRiskFreeRate(new OverrideAssumption(0D, false, 0D, null));

        IllegalArgumentException exception = assertThrows(
                IllegalArgumentException.class,
                () -> outputService.calculateRevenueGrowthRate(input, 12));
        assertTrue(exception.getMessage().contains("TERMINAL_GROWTH_UNSAFE"));
    }
}
