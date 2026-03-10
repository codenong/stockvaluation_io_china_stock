package io.stockvaluation.service;

import io.stockvaluation.dto.FinancialDataDTO;
import io.stockvaluation.provider.BalanceSheetSnapshot;
import io.stockvaluation.provider.DataProvider;
import io.stockvaluation.provider.IncomeStatementSnapshot;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDate;
import java.time.ZoneId;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CompanyFinancialIngestionServiceTest {

    @Mock
    private DataProvider dataProvider;

    @InjectMocks
    private CompanyFinancialIngestionService service;

    @Test
    void ingestAggregatesQuarterlyDataAndFallsBackToOlderRevenueLtmWhenNeeded() {
        int currentYear = LocalDate.now().getYear();

        when(dataProvider.getIncomeStatementSnapshots("AAPL", "quarterly")).thenReturn(Map.of(
                epoch(currentYear, 12, 31), income(270.0, 27.0, 0.0, 1.0, null, null, 5.0),
                epoch(currentYear, 9, 30), income(120.0, 12.0, -2.0, 1.0, null, null, 5.0),
                epoch(currentYear, 6, 30), income(110.0, 11.0, -1.0, 1.0, null, null, 5.0),
                epoch(currentYear, 3, 31), income(100.0, 10.0, null, 1.0, null, null, 5.0)));

        Map<String, IncomeStatementSnapshot> yearlyIncome = new LinkedHashMap<>();
        yearlyIncome.put(epoch(currentYear - 1, 12, 31), income(600.0, 50.0, -5.0, 6.0, 10.0, 40.0, 15.0));
        yearlyIncome.put(epoch(currentYear - 2, 12, 31), income(550.0, 45.0, -4.0, 5.0, 9.0, 36.0, 14.0));
        yearlyIncome.put(epoch(currentYear - 3, 12, 31), income(500.0, 40.0, -3.0, 4.0, 8.0, 32.0, 13.0));
        yearlyIncome.put(epoch(currentYear - 4, 12, 31), income(450.0, 35.0, -2.0, 3.0, 7.0, 28.0, 12.0));
        when(dataProvider.getIncomeStatementSnapshots("AAPL", "yearly")).thenReturn(yearlyIncome);

        when(dataProvider.getBalanceSheetSnapshots("AAPL", "quarterly")).thenReturn(Map.of(
                epoch(currentYear, 12, 31), new BalanceSheetSnapshot(0.0, 0.0, 0.0, null, 1.0)));
        when(dataProvider.getBalanceSheetSnapshots("AAPL", "yearly")).thenReturn(Map.of(
                epoch(currentYear - 1, 12, 31), new BalanceSheetSnapshot(100.0, 200.0, 300.0, 400.0, 25.0)));

        Map<String, Object> basicInfo = Map.of(
                "dayHigh", 182.0,
                "previousClose", 175.0,
                "dayLow", 170.0,
                "currentPrice", 180.0);

        CompanyFinancialIngestionService.FinancialIngestionData result = service.ingest("AAPL", basicInfo);
        FinancialDataDTO financialData = result.financialDataDTO();

        assertEquals(600.0, financialData.getRevenueTTM());
        assertEquals(550.0, financialData.getRevenueLTM());
        assertEquals(63.0, financialData.getOperatingIncomeTTM());
        assertEquals(55.0, financialData.getOperatingIncomeLTM());
        assertEquals(4.0, financialData.getInterestExpenseTTM());
        assertEquals(6.0, financialData.getInterestExpenseLTM());
        assertEquals(100.0, financialData.getBookValueEqualityTTM());
        assertEquals(200.0, financialData.getBookValueDebtTTM());
        assertEquals(300.0, financialData.getCashAndMarkablTTM());
        assertEquals(400.0, financialData.getNoOfShareOutstanding());
        assertEquals(25.0, financialData.getMinorityInterestTTM());
        assertEquals(182.0, financialData.getHighestStockPrice());
        assertEquals(175.0, financialData.getPreviousDayStockPrice());
        assertEquals(170.0, financialData.getLowestStockPrice());
        assertEquals(180.0, financialData.getStockPrice());
        assertEquals(List.of(450.0, 500.0, 550.0, 600.0), result.historicalRevenue());
        assertEquals(10.0, result.taxProvision());
        assertEquals(40.0, result.preTaxIncome());
        assertEquals(15.0, financialData.getResearchAndDevelopmentMap().get("currentR&D-1"));
        assertEquals(20.0, financialData.getResearchAndDevelopmentMap().get("currentR&D-0"));
    }

    @Test
    void ingestFallsBackToYearlyDataAndHandlesMissingNumerics() {
        int currentYear = LocalDate.now().getYear();

        when(dataProvider.getIncomeStatementSnapshots("MSFT", "quarterly")).thenReturn(Map.of());
        when(dataProvider.getIncomeStatementSnapshots("MSFT", "yearly")).thenReturn(Map.of(
                epoch(currentYear - 1, 12, 31), income(200.0, 20.0, null, 2.0, 5.0, 15.0, 9.0)));
        when(dataProvider.getBalanceSheetSnapshots("MSFT", "quarterly")).thenReturn(Map.of());
        when(dataProvider.getBalanceSheetSnapshots("MSFT", "yearly")).thenReturn(Map.of());

        Map<String, Object> basicInfo = Map.of(
                "dayHigh", "not-a-number",
                "previousClose", "not-a-number",
                "dayLow", "not-a-number",
                "currentPrice", "not-a-number");

        CompanyFinancialIngestionService.FinancialIngestionData result = service.ingest("MSFT", basicInfo);
        FinancialDataDTO financialData = result.financialDataDTO();

        assertEquals(200.0, financialData.getRevenueTTM());
        assertEquals(200.0, financialData.getRevenueLTM());
        assertEquals(20.0, financialData.getOperatingIncomeTTM());
        assertEquals(20.0, financialData.getOperatingIncomeLTM());
        assertEquals(2.0, financialData.getInterestExpenseTTM());
        assertEquals(2.0, financialData.getInterestExpenseLTM());
        assertEquals(0.0, financialData.getBookValueEqualityTTM());
        assertEquals(0.0, financialData.getBookValueDebtTTM());
        assertEquals(0.0, financialData.getCashAndMarkablTTM());
        assertNull(financialData.getStockPrice());
        assertEquals(List.of(), result.historicalRevenue());
        assertEquals(List.of(), result.historicalMargins());
        assertEquals(9.0, financialData.getResearchAndDevelopmentMap().get("currentR&D-1"));
        assertEquals(0.0, financialData.getResearchAndDevelopmentMap().get("currentR&D-0"));
    }

    private static IncomeStatementSnapshot income(
            Double revenue,
            Double operatingIncome,
            Double specialIncomeCharges,
            Double interestExpense,
            Double taxProvision,
            Double pretaxIncome,
            Double researchAndDevelopment) {
        return new IncomeStatementSnapshot(
                revenue,
                operatingIncome,
                specialIncomeCharges,
                interestExpense,
                taxProvision,
                pretaxIncome,
                researchAndDevelopment);
    }

    private static String epoch(int year, int month, int dayOfMonth) {
        return String.valueOf(LocalDate.of(year, month, dayOfMonth)
                .atStartOfDay(ZoneId.systemDefault())
                .toInstant()
                .toEpochMilli());
    }
}
