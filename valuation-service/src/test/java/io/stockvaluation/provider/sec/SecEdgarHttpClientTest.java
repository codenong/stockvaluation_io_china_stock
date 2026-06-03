package io.stockvaluation.provider.sec;

import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpMethod;
import org.springframework.http.RequestEntity;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class SecEdgarHttpClientTest {

    @Test
    void missingUserAgentBlocksSecRequestsBeforeHttpCall() {
        RestTemplate restTemplate = mock(RestTemplate.class);
        SecEdgarProviderProperties properties = new SecEdgarProviderProperties();
        properties.setUserAgent("");

        SecEdgarHttpClient client = new SecEdgarHttpClient(restTemplate, properties);

        SecEdgarException exception = assertThrows(
                SecEdgarException.class,
                () -> client.getJson("https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json"));
        assertEquals("missing_user_agent", exception.getCategory());
        verify(restTemplate, never()).exchange(any(RequestEntity.class), any(ParameterizedTypeReference.class));
    }

    @Test
    void sendsDeclaredUserAgentAndCachesDeterministicResponses() {
        RestTemplate restTemplate = mock(RestTemplate.class);
        SecEdgarProviderProperties properties = configuredProperties();
        when(restTemplate.exchange(any(RequestEntity.class), any(ParameterizedTypeReference.class)))
                .thenReturn(ResponseEntity.ok(Map.of("ok", true)));

        SecEdgarHttpClient client = new SecEdgarHttpClient(restTemplate, properties);

        assertEquals(Map.of("ok", true), client.getJson("https://data.sec.gov/submissions/CIK0000789019.json"));
        assertEquals(Map.of("ok", true), client.getJson("https://data.sec.gov/submissions/CIK0000789019.json"));

        ArgumentCaptor<RequestEntity<Void>> captor = ArgumentCaptor.forClass(RequestEntity.class);
        verify(restTemplate, times(1)).exchange(captor.capture(), any(ParameterizedTypeReference.class));
        RequestEntity<Void> request = captor.getValue();
        assertEquals(HttpMethod.GET, request.getMethod());
        assertEquals("StockValuation.io Dev contact@example.com", request.getHeaders().getFirst("User-Agent"));
        assertEquals("gzip, deflate", request.getHeaders().getFirst("Accept-Encoding"));
    }

    @Test
    void rateLimitsUncachedSecRequestsBelowPublishedMaximum() {
        RestTemplate restTemplate = mock(RestTemplate.class);
        SecEdgarProviderProperties properties = configuredProperties();
        properties.setRequestsPerSecond(5);
        when(restTemplate.exchange(any(RequestEntity.class), any(ParameterizedTypeReference.class)))
                .thenReturn(ResponseEntity.ok(Map.of("ok", true)));
        List<Long> sleeps = new ArrayList<>();

        SecEdgarHttpClient client = new SecEdgarHttpClient(
                restTemplate,
                properties,
                () -> 1_000L,
                sleeps::add);

        client.getJson("https://data.sec.gov/submissions/CIK0000789019.json");
        client.getJson("https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json");

        assertEquals(List.of(200L), sleeps);
    }

    private static SecEdgarProviderProperties configuredProperties() {
        SecEdgarProviderProperties properties = new SecEdgarProviderProperties();
        properties.setEnabled(true);
        properties.setUserAgent("StockValuation.io Dev contact@example.com");
        properties.setCacheTtlSeconds(60);
        return properties;
    }
}
