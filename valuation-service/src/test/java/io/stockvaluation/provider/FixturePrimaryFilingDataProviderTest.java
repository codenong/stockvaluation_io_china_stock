package io.stockvaluation.provider;

import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class FixturePrimaryFilingDataProviderTest {

    private final FixturePrimaryFilingDataProvider provider = new FixturePrimaryFilingDataProvider();

    @Test
    void fixtureProviderReturnsPrimaryFilingProvenanceForSupportedUsTicker() {
        assertTrue(provider.hasPrimaryFinancials("MSFT"));

        Map<String, IncomeStatementSnapshot> income = provider.getIncomeStatementSnapshots("MSFT", "yearly");
        Map<String, BalanceSheetSnapshot> balance = provider.getBalanceSheetSnapshots("MSFT", "yearly");

        assertFalse(income.isEmpty());
        assertFalse(balance.isEmpty());
        SourceProvenance incomeProvenance = income.values().iterator().next().sourceProvenance();
        SourceProvenance balanceProvenance = balance.values().iterator().next().sourceProvenance();
        assertEquals("primary_filing", incomeProvenance.getSourceClass());
        assertEquals("primary_filing", balanceProvenance.getSourceClass());
        assertEquals("primary_filing_used", incomeProvenance.getSourcePolicyStatus());
        assertEquals("sec-xbrl-fixture", incomeProvenance.getProvider());
        assertTrue(income.values().iterator().next().totalRevenue() > 1_000_000_000.0);
        assertTrue(balance.values().iterator().next().sharesOutstanding() > 1_000_000_000.0);
    }

    @Test
    void fixtureProviderReturnsUnavailableForUnsupportedTicker() {
        assertFalse(provider.hasPrimaryFinancials("SAP.DE"));
        assertTrue(provider.getIncomeStatementSnapshots("SAP.DE", "yearly").isEmpty());
        assertTrue(provider.getBalanceSheetSnapshots("SAP.DE", "yearly").isEmpty());
    }
}
