package io.stockvaluation.service;

import io.stockvaluation.config.ValuationTemplateProperties;
import io.stockvaluation.dto.CompanyDataDTO;
import io.stockvaluation.dto.CompanyDriveDataDTO;
import io.stockvaluation.dto.FinancialDataDTO;
import io.stockvaluation.dto.GrowthDto;
import io.stockvaluation.dto.ValuationTemplate;
import io.stockvaluation.enums.CashflowType;
import io.stockvaluation.enums.EarningsLevel;
import io.stockvaluation.enums.GrowthPattern;
import io.stockvaluation.enums.ModelType;
import io.stockvaluation.form.FinancialDataInput;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

class ValuationTemplateServiceTest {

    private ValuationTemplateService service;

    @BeforeEach
    void setUp() {
        service = new ValuationTemplateService(new ValuationTemplateProperties());
    }

    @Test
    void determineTemplateBuildsStableFcffTemplate() {
        FinancialDataInput input = new FinancialDataInput();
        input.setRevenueNextYear(5.0);

        FinancialDataDTO financialData = new FinancialDataDTO();
        financialData.setOperatingIncomeTTM(120.0);

        CompanyDataDTO companyData = new CompanyDataDTO();
        companyData.setFinancialDataDTO(financialData);

        ValuationTemplate template = service.determineTemplate(input, companyData);

        assertEquals(ModelType.DISCOUNTED_CF, template.getModelType());
        assertEquals(GrowthPattern.STABLE, template.getGrowthPattern());
        assertEquals(EarningsLevel.CURRENT, template.getEarningsLevel());
        assertEquals(CashflowType.FCFF, template.getCashflowToDiscount());
        assertEquals(10, template.getProjectionYears());
        assertEquals(12, template.getArrayLength());
        assertFalse(template.useNormalizedEarnings());
    }

    @Test
    void extractFirmGrowthRateFallsBackAcrossAvailableSources() throws Exception {
        CompanyDataDTO companyData = new CompanyDataDTO();
        CompanyDriveDataDTO driveData = new CompanyDriveDataDTO();
        driveData.setRevenueNextYear(0.18);
        companyData.setCompanyDriveDataDTO(driveData);

        GrowthDto growthDto = new GrowthDto();
        growthDto.setRevenueMu(0.21);
        companyData.setGrowthDto(growthDto);

        FinancialDataInput input = new FinancialDataInput();
        input.setRevenueNextYear(12.5);

        assertEquals(0.125,
                invoke("extractFirmGrowthRate", new Class[]{CompanyDataDTO.class, FinancialDataInput.class}, companyData, input));

        input.setRevenueNextYear(null);
        assertEquals(0.18,
                invoke("extractFirmGrowthRate", new Class[]{CompanyDataDTO.class, FinancialDataInput.class}, companyData, input));

        companyData.setCompanyDriveDataDTO(null);
        assertEquals(0.21,
                invoke("extractFirmGrowthRate", new Class[]{CompanyDataDTO.class, FinancialDataInput.class}, companyData, input));

        companyData.setGrowthDto(null);
        assertEquals(0.10,
                invoke("extractFirmGrowthRate", new Class[]{CompanyDataDTO.class, FinancialDataInput.class}, companyData, input));
    }

    @Test
    void calculateNormalizedMarginUsesHistoryMeanThenMarginMuThenInputFallback() throws Exception {
        FinancialDataInput input = new FinancialDataInput();
        input.setOperatingMarginNextYear(14.0);

        CompanyDataDTO withHistory = new CompanyDataDTO();
        GrowthDto historyGrowth = new GrowthDto();
        historyGrowth.setMarginChanges(List.of(0.10, 0.20, 0.30, 0.40));
        withHistory.setGrowthDto(historyGrowth);
        assertEquals(25.0,
                invoke("calculateNormalizedMargin", new Class[]{FinancialDataInput.class, CompanyDataDTO.class}, input, withHistory));

        CompanyDataDTO withMarginMu = new CompanyDataDTO();
        GrowthDto marginMuGrowth = new GrowthDto();
        marginMuGrowth.setMarginMu(0.18);
        withMarginMu.setGrowthDto(marginMuGrowth);
        assertEquals(18.0,
                invoke("calculateNormalizedMargin", new Class[]{FinancialDataInput.class, CompanyDataDTO.class}, input, withMarginMu));

        CompanyDataDTO withInsufficientHistory = new CompanyDataDTO();
        GrowthDto limitedGrowth = new GrowthDto();
        limitedGrowth.setMarginChanges(List.of(0.10, 0.20));
        withInsufficientHistory.setGrowthDto(limitedGrowth);
        assertEquals(14.0,
                invoke("calculateNormalizedMargin", new Class[]{FinancialDataInput.class, CompanyDataDTO.class}, input, withInsufficientHistory));
    }

    @Test
    void determineEarningsPositivityHandlesNullPositiveAndNegativeOperatingIncome() throws Exception {
        CompanyDataDTO noFinancials = new CompanyDataDTO();
        assertEquals(true,
                invoke("determineEarningsPositivity", new Class[]{CompanyDataDTO.class}, noFinancials));

        CompanyDataDTO profitable = new CompanyDataDTO();
        FinancialDataDTO profitableData = new FinancialDataDTO();
        profitableData.setOperatingIncomeTTM(1.0);
        profitable.setFinancialDataDTO(profitableData);
        assertEquals(true,
                invoke("determineEarningsPositivity", new Class[]{CompanyDataDTO.class}, profitable));

        CompanyDataDTO lossMaking = new CompanyDataDTO();
        FinancialDataDTO lossData = new FinancialDataDTO();
        lossData.setOperatingIncomeTTM(-1.0);
        lossMaking.setFinancialDataDTO(lossData);
        assertEquals(false,
                invoke("determineEarningsPositivity", new Class[]{CompanyDataDTO.class}, lossMaking));
    }

    @Test
    void determineProjectionYearsUsesConfiguredDefaultsAndThreeStageLength() throws Exception {
        assertEquals(10, ((Integer) invoke("determineProjectionYears", new Class[]{GrowthPattern.class}, new Object[]{null})).intValue());
        assertEquals(10, ((Integer) invoke("determineProjectionYears", new Class[]{GrowthPattern.class}, GrowthPattern.STABLE)).intValue());
        assertEquals(15, ((Integer) invoke("determineProjectionYears", new Class[]{GrowthPattern.class}, GrowthPattern.THREE_STAGE)).intValue());
    }

    @SuppressWarnings("unchecked")
    private <T> T invoke(String methodName, Class<?>[] parameterTypes, Object... args) throws Exception {
        Method method = ValuationTemplateService.class.getDeclaredMethod(methodName, parameterTypes);
        method.setAccessible(true);
        return (T) method.invoke(service, args);
    }
}
