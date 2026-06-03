package io.stockvaluation.provider.sec;

import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.RequestEntity;
import org.springframework.http.ResponseEntity;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.zip.GZIPOutputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

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
        verify(restTemplate, never()).exchange(any(RequestEntity.class), eq(byte[].class));
    }

    @Test
    void sendsDeclaredUserAgentAndCachesDeterministicResponses() {
        RestTemplate restTemplate = mock(RestTemplate.class);
        SecEdgarProviderProperties properties = configuredProperties();
        when(restTemplate.exchange(any(RequestEntity.class), eq(byte[].class)))
                .thenReturn(ResponseEntity.ok("{\"ok\":true}".getBytes(StandardCharsets.UTF_8)));

        SecEdgarHttpClient client = new SecEdgarHttpClient(restTemplate, properties);

        assertEquals(Map.of("ok", true), client.getJson("https://data.sec.gov/submissions/CIK0000789019.json"));
        assertEquals(Map.of("ok", true), client.getJson("https://data.sec.gov/submissions/CIK0000789019.json"));

        ArgumentCaptor<RequestEntity<Void>> captor = ArgumentCaptor.forClass(RequestEntity.class);
        verify(restTemplate, times(1)).exchange(captor.capture(), eq(byte[].class));
        RequestEntity<Void> request = captor.getValue();
        assertEquals(HttpMethod.GET, request.getMethod());
        assertEquals("StockValuation.io Dev contact@example.com", request.getHeaders().getFirst("User-Agent"));
        assertEquals("gzip, deflate", request.getHeaders().getFirst("Accept-Encoding"));
    }

    @Test
    void decodesGzippedSecJsonBeforeParsing() throws Exception {
        RestTemplate restTemplate = new RestTemplate();
        MockRestServiceServer server = MockRestServiceServer.bindTo(restTemplate).build();
        String url = "https://data.sec.gov/api/xbrl/companyfacts/CIK0001652044.json";
        server.expect(requestTo(url))
                .andExpect(header("User-Agent", "StockValuation.io Dev contact@example.com"))
                .andRespond(withSuccess(gzip("{\"ok\":true}"), MediaType.APPLICATION_JSON)
                        .header(HttpHeaders.CONTENT_ENCODING, "gzip"));
        SecEdgarHttpClient client = new SecEdgarHttpClient(restTemplate, configuredProperties());

        assertEquals(Map.of("ok", true), client.getJson(url));
        server.verify();
    }

    @Test
    void rateLimitsUncachedSecRequestsBelowPublishedMaximum() {
        RestTemplate restTemplate = mock(RestTemplate.class);
        SecEdgarProviderProperties properties = configuredProperties();
        properties.setRequestsPerSecond(5);
        when(restTemplate.exchange(any(RequestEntity.class), eq(byte[].class)))
                .thenReturn(ResponseEntity.ok("{\"ok\":true}".getBytes(StandardCharsets.UTF_8)));
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

    private static byte[] gzip(String value) throws Exception {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        try (GZIPOutputStream gzip = new GZIPOutputStream(output)) {
            gzip.write(value.getBytes(StandardCharsets.UTF_8));
        }
        return output.toByteArray();
    }
}
