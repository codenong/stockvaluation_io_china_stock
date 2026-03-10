package io.stockvaluation.provider;

import io.stockvaluation.dto.CompanyDataDTO;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DataProviderTest {

    @Test
    void defaultMethodsMapSnapshotsAndExposeFallbackHelpers() {
        StubProvider provider = new StubProvider(
                Map.of("1704067200000", Map.of(
                        "TotalRevenue", 100.0,
                        "EBIT", 20.0,
                        "SpecialIncomeCharges", -5.0,
                        "InterestExpense", 3.0,
                        "IncomeTaxExpense", 4.0,
                        "IncomeBeforeTax", 16.0,
                        "ResearchAndDevelopmentExpense", 2.0)),
                Map.of("1704067200000", Map.of(
                        "CommonStockEquity", 50.0,
                        "TotalDebt", 25.0,
                        "CashCashEquivalentsAndShortTermInvestments", 10.0,
                        "OrdinarySharesNumber", 5.0,
                        "MinorityInterests", 1.0)),
                Map.of("nextYearRevenue", 0.12),
                List.of(Map.of("date", "2024-01-01", "amount", 1.5)));

        IncomeStatementSnapshot income = provider.getIncomeStatementSnapshots("AAPL").get("1704067200000");
        BalanceSheetSnapshot balance = provider.getBalanceSheetSnapshots("AAPL").get("1704067200000");

        assertSame(provider.getIncomeStatement("AAPL"), provider.getIncomeStatement("AAPL", "quarterly"));
        assertSame(provider.getBalanceSheet("AAPL"), provider.getBalanceSheet("AAPL", "quarterly"));
        assertSame(provider.getRevenueEstimate("AAPL"), provider.getRevenueEstimate("AAPL", "quarterly"));
        assertEquals(100.0, income.totalRevenue());
        assertEquals(20.0, income.operatingIncome());
        assertEquals(-5.0, income.specialIncomeCharges());
        assertEquals(3.0, income.interestExpense());
        assertEquals(4.0, income.taxProvision());
        assertEquals(16.0, income.pretaxIncome());
        assertEquals(2.0, income.researchAndDevelopment());
        assertEquals(50.0, balance.bookValueEquity());
        assertEquals(25.0, balance.totalDebt());
        assertEquals(10.0, balance.cashAndShortTermInvestments());
        assertEquals(5.0, balance.sharesOutstanding());
        assertEquals(1.0, balance.minorityInterest());
        assertEquals(50.0, provider.extractBookValueEquity(provider.getBalanceSheet("AAPL").get("1704067200000")));
        assertEquals(25.0, provider.extractTotalDebt(provider.getBalanceSheet("AAPL").get("1704067200000")));
        assertEquals(10.0, provider.extractCashAndShortTermInvestments(provider.getBalanceSheet("AAPL").get("1704067200000")));
        assertEquals(5.0, provider.extractSharesOutstanding(provider.getBalanceSheet("AAPL").get("1704067200000")));
        assertEquals(List.of(Map.of("date", "2024-01-01", "amount", 1.5)),
                provider.getDividendData("AAPL").get("dividendHistory"));
        assertTrue(provider.isHealthy());
        assertEquals("stub", provider.getProviderName());
    }

    @Test
    void defaultMethodsHandleEmptyPayloadsAndExceptionsExposeMetadata() {
        StubProvider provider = new StubProvider(Map.of(), Map.of(), Map.of(), List.of());

        assertTrue(provider.getIncomeStatementSnapshots("AAPL").isEmpty());
        assertTrue(provider.getBalanceSheetSnapshots("AAPL").isEmpty());
        assertNull(provider.extractBookValueEquity(Map.of()));
        assertNull(provider.extractTotalDebt(Map.of()));
        assertNull(provider.extractCashAndShortTermInvestments(Map.of()));
        assertNull(provider.extractSharesOutstanding(Map.of()));
        assertEquals(0, provider.getDividendHistory("AAPL").size());

        RuntimeException cause = new RuntimeException("boom");
        DataProviderException exception = new DataProviderException("stub", "AAPL", "failed", cause);
        assertEquals("stub", exception.getProviderName());
        assertEquals("AAPL", exception.getTicker());
        assertEquals("[stub] Failed for ticker 'AAPL': failed", exception.getMessage());
        assertSame(cause, exception.getCause());
    }

    private record StubProvider(
            Map<String, Map<String, Object>> incomeStatement,
            Map<String, Map<String, Object>> balanceSheet,
            Map<String, Object> revenueEstimate,
            List<Map<String, Object>> dividendHistory) implements DataProvider {

        @Override
        public CompanyDataDTO getCompanyData(String ticker) {
            return null;
        }

        @Override
        public Map<String, Object> getCompanyInfo(String ticker) {
            return Map.of("ticker", ticker);
        }

        @Override
        public Map<String, Map<String, Object>> getIncomeStatement(String ticker) {
            return incomeStatement;
        }

        @Override
        public Map<String, Map<String, Object>> getBalanceSheet(String ticker) {
            return balanceSheet;
        }

        @Override
        public Map<String, Object> getRevenueEstimate(String ticker) {
            return revenueEstimate;
        }

        @Override
        public List<Map<String, Object>> getDividendHistory(String ticker) {
            return dividendHistory;
        }

        @Override
        public String getProviderName() {
            return "stub";
        }
    }
}
