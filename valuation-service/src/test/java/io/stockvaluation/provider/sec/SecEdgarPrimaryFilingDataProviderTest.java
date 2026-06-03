package io.stockvaluation.provider.sec;

import io.stockvaluation.provider.IncomeStatementSnapshot;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class SecEdgarPrimaryFilingDataProviderTest {

    @Test
    void liveProviderReturnsPrimaryFilingSnapshotsFromMockedSecResponses() {
        SecEdgarHttpClient client = mock(SecEdgarHttpClient.class);
        SecTickerCikResolver resolver = mock(SecTickerCikResolver.class);
        SecEdgarProviderProperties properties = configuredProperties();
        when(resolver.resolveCik("MSFT")).thenReturn(Optional.of("0000789019"));
        when(client.getJson("https://data.sec.gov/submissions/CIK0000789019.json"))
                .thenReturn(SecTestFixtures.json("msft_submissions.json"));
        when(client.getJson("https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json"))
                .thenReturn(SecTestFixtures.json("msft_companyfacts.json"));

        SecEdgarPrimaryFilingDataProvider provider = new SecEdgarPrimaryFilingDataProvider(
                properties,
                resolver,
                client,
                new SecCompanyFactsMapper());

        assertTrue(provider.hasPrimaryFinancials("MSFT"));
        Map<String, IncomeStatementSnapshot> income = provider.getIncomeStatementSnapshots("MSFT", "yearly");

        assertFalse(income.isEmpty());
        IncomeStatementSnapshot snapshot = income.values().iterator().next();
        assertEquals("primary_filing", snapshot.sourceProvenance().getSourceClass());
        assertEquals("sec-edgar-companyfacts", snapshot.sourceProvenance().getProvider());
        assertEquals("2026-07-30", snapshot.sourceProvenance().getSourceDate());
        assertEquals("2026-06-30", snapshot.sourceProvenance().getPeriodEnd());
    }

    @Test
    void missingUserAgentDisablesLiveProviderAndLeavesFallbackAvailableToCaller() {
        SecEdgarHttpClient client = mock(SecEdgarHttpClient.class);
        SecTickerCikResolver resolver = mock(SecTickerCikResolver.class);
        SecEdgarProviderProperties properties = configuredProperties();
        properties.setUserAgent("");

        SecEdgarPrimaryFilingDataProvider provider = new SecEdgarPrimaryFilingDataProvider(
                properties,
                resolver,
                client,
                new SecCompanyFactsMapper());

        assertFalse(provider.hasPrimaryFinancials("MSFT"));
        assertEquals("missing_user_agent", provider.getPrimaryFinancialsAvailability("MSFT").status());
        assertTrue(provider.getIncomeStatementSnapshots("MSFT", "yearly").isEmpty());
        verify(resolver, never()).resolveCik("MSFT");
    }

    private static SecEdgarProviderProperties configuredProperties() {
        SecEdgarProviderProperties properties = new SecEdgarProviderProperties();
        properties.setEnabled(true);
        properties.setUserAgent("StockValuation.io Dev contact@example.com");
        properties.setDataBaseUrl("https://data.sec.gov");
        return properties;
    }
}
