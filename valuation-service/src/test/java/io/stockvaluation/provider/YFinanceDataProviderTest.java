package io.stockvaluation.provider;

import io.stockvaluation.config.YFinanceProviderProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class YFinanceDataProviderTest {

    @Mock
    private RestTemplate restTemplate;

    @Mock
    private YFinanceProviderProperties properties;

    private YFinanceDataProvider provider;

    @BeforeEach
    void setUp() {
        provider = new YFinanceDataProvider(restTemplate, properties);
    }

    @Test
    void getCompanyDataIsExplicitlyUnsupported() {
        DataProviderException exception = assertThrows(DataProviderException.class, () -> provider.getCompanyData("AAPL"));

        assertEquals("yfinance-http", exception.getProviderName());
        assertEquals("AAPL", exception.getTicker());
    }

    @Test
    void getCompanyInfoReturnsEmptyMapWhenBodyIsNull() {
        when(properties.getBaseUrl()).thenReturn("http://localhost:5000");
        when(restTemplate.exchange(anyString(), eq(HttpMethod.GET), eq(null), any(ParameterizedTypeReference.class)))
                .thenReturn(ResponseEntity.ok(null));

        assertEquals(Map.of(), provider.getCompanyInfo("AAPL"));
    }

    @Test
    void getIncomeStatementNormalizesFrequencyAndConvertsNestedPayloads() {
        when(properties.getBaseUrl()).thenReturn("http://localhost:5000");
        when(restTemplate.exchange(anyString(), eq(HttpMethod.GET), eq(null), any(ParameterizedTypeReference.class)))
                .thenReturn(ResponseEntity.ok(Map.of(
                        "1704067200000", Map.of("totalRevenue", 100.0),
                        "ignored", "value")));

        Map<String, Map<String, Object>> result = provider.getIncomeStatement("AAPL", " Quarterly ");

        ArgumentCaptor<String> urlCaptor = ArgumentCaptor.forClass(String.class);
        verify(restTemplate).exchange(urlCaptor.capture(), eq(HttpMethod.GET), eq(null), any(ParameterizedTypeReference.class));
        assertEquals("http://localhost:5000/income-stmt?ticker=AAPL&freq=quarterly", urlCaptor.getValue());
        assertEquals(1, result.size());
        assertEquals(100.0, result.get("1704067200000").get("totalRevenue"));
    }

    @Test
    void getIncomeStatementSnapshotsCarryYahooNormalizedProvenance() {
        when(properties.getBaseUrl()).thenReturn("http://localhost:5000");
        when(restTemplate.exchange(anyString(), eq(HttpMethod.GET), eq(null), any(ParameterizedTypeReference.class)))
                .thenReturn(ResponseEntity.ok(Map.of(
                        "1704067200000", Map.of("totalRevenue", 100.0))));

        IncomeStatementSnapshot snapshot = provider.getIncomeStatementSnapshots("AAPL", "yearly")
                .get("1704067200000");

        assertEquals(100.0, snapshot.totalRevenue());
        assertEquals("yahoo_normalized", snapshot.sourceProvenance().getSourceClass());
        assertEquals("yfinance-http", snapshot.sourceProvenance().getProvider());
        assertEquals("2024-01-01", snapshot.sourceProvenance().getPeriodEnd());
        assertEquals("retrieved", snapshot.sourceProvenance().getRetrievalStatus());
        assertEquals("not_checked_by_service", snapshot.sourceProvenance().getCrossCheckStatus());
    }

    @Test
    void getDividendHistoryFlattensNestedHistoryMap() {
        when(properties.getBaseUrl()).thenReturn("http://localhost:5000");
        when(restTemplate.exchange(anyString(), eq(HttpMethod.GET), eq(null), any(ParameterizedTypeReference.class)))
                .thenReturn(ResponseEntity.ok(Map.of(
                        "dividendHistory", Map.of("2024-01-01", 1.0, "2024-04-01", 1.1))));

        assertEquals(2, provider.getDividendHistory("KO").size());
    }

    @Test
    void providerWrapsRestTemplateFailures() {
        when(properties.getBaseUrl()).thenReturn("http://localhost:5000");
        doThrow(new IllegalStateException("downstream unavailable"))
                .when(restTemplate).exchange(anyString(), eq(HttpMethod.GET), eq(null), any(ParameterizedTypeReference.class));

        DataProviderException exception = assertThrows(DataProviderException.class, () -> provider.getRevenueEstimate("AAPL"));

        assertEquals("yfinance-http", exception.getProviderName());
        assertEquals("AAPL", exception.getTicker());
    }
}
