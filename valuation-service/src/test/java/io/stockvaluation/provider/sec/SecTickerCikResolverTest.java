package io.stockvaluation.provider.sec;

import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class SecTickerCikResolverTest {

    @Test
    void resolvesTickerToZeroPaddedCikFromOfficialSecTickerExchangeMapping() {
        SecEdgarHttpClient client = mock(SecEdgarHttpClient.class);
        SecEdgarProviderProperties properties = new SecEdgarProviderProperties();
        properties.setSecBaseUrl("https://www.sec.gov");
        when(client.getJson("https://www.sec.gov/files/company_tickers_exchange.json"))
                .thenReturn(SecTestFixtures.json("company_tickers_exchange.json"));

        SecTickerCikResolver resolver = new SecTickerCikResolver(client, properties);

        assertEquals(Optional.of("0000789019"), resolver.resolveCik(" msft "));
        assertEquals(Optional.of("0001067983"), resolver.resolveCik("BRK.B"));
    }

    @Test
    void returnsEmptyWhenTickerIsNotInSecMapping() {
        SecEdgarHttpClient client = mock(SecEdgarHttpClient.class);
        SecEdgarProviderProperties properties = new SecEdgarProviderProperties();
        properties.setSecBaseUrl("https://www.sec.gov");
        when(client.getJson("https://www.sec.gov/files/company_tickers_exchange.json"))
                .thenReturn(SecTestFixtures.json("company_tickers_exchange.json"));

        SecTickerCikResolver resolver = new SecTickerCikResolver(client, properties);

        assertTrue(resolver.resolveCik("SAP.DE").isEmpty());
    }
}
