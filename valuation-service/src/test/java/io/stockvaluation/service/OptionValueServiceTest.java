package io.stockvaluation.service;

import io.stockvaluation.dto.CompanyDataDTO;
import io.stockvaluation.dto.CompanyDriveDataDTO;
import io.stockvaluation.dto.FinancialDataDTO;
import io.stockvaluation.dto.OptionValueResultDTO;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class OptionValueServiceTest {

    @Mock
    private CommonService commonService;

    @Test
    void calculateOptionValueUsesProviderDataAndUppercasesTicker() {
        OptionValueService service = new OptionValueService(commonService);
        when(commonService.getCompanyDataFromProvider("MSFT")).thenReturn(companyData(100.0, 5.0));

        OptionValueResultDTO result = service.calculateOptionValue("msft", 100.0, 1.0, 10.0, 20.0);

        assertTrue(result.getValuePerOption() > 0);
        assertEquals(result.getValuePerOption() * 10.0, result.getValueOfAllOptionsOutstanding(), 1e-9);
        verify(commonService).getCompanyDataFromProvider("MSFT");
    }

    @Test
    void calculateOptionValueThrowsWhenCompanyDataIsMissing() {
        OptionValueService service = new OptionValueService(commonService);
        when(commonService.getCompanyDataFromProvider("AAPL")).thenReturn(null);

        assertThrows(RuntimeException.class, () -> service.calculateOptionValue("AAPL", 100.0, 1.0, 5.0, 20.0));
    }

    @Test
    void blackScholesHelperMethodsReturnExpectedValues() {
        OptionValueService service = new OptionValueService(commonService);

        double d1 = OptionValueService.calculateD1(100.0, 90.0, 5.0, 20.0, 1.0);
        double d2 = OptionValueService.calculateD2(d1, 20.0, 1.0);

        assertEquals(d1 - 0.2, d2, 1e-9);
        assertEquals(0.5, service.calculateNd1(0.0), 1e-9);
        assertEquals(0.5, OptionValueService.calculateNd2(0.0), 1e-9);
        assertEquals(
                10.450583572185565,
                OptionValueService.calculateValuePerOption(100.0, 100.0, 1.0, 0.6368306511756191, 0.5596176923702425, 0.05, 0.0),
                1e-9);
    }

    private static CompanyDataDTO companyData(double stockPrice, double riskFreeRate) {
        FinancialDataDTO financialData = new FinancialDataDTO();
        financialData.setStockPrice(stockPrice);

        CompanyDriveDataDTO driveData = new CompanyDriveDataDTO();
        driveData.setRiskFreeRate(riskFreeRate);

        CompanyDataDTO companyData = new CompanyDataDTO();
        companyData.setFinancialDataDTO(financialData);
        companyData.setCompanyDriveDataDTO(driveData);
        return companyData;
    }
}
