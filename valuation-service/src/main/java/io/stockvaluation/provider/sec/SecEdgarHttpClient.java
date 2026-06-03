package io.stockvaluation.provider.sec;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.RequestEntity;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.time.Instant;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.LongConsumer;
import java.util.function.LongSupplier;
import java.util.zip.GZIPInputStream;
import java.util.zip.InflaterInputStream;

@Component
public class SecEdgarHttpClient {

    private final RestTemplate restTemplate;
    private final SecEdgarProviderProperties properties;
    private final LongSupplier clockMillis;
    private final LongConsumer sleeperMillis;
    private final ObjectMapper objectMapper;
    private final Map<String, CachedResponse> cache = new ConcurrentHashMap<>();
    private long lastRequestMillis = -1L;

    @Autowired
    public SecEdgarHttpClient(RestTemplate restTemplate, SecEdgarProviderProperties properties) {
        this(restTemplate, properties, () -> Instant.now().toEpochMilli(), SecEdgarHttpClient::sleep, new ObjectMapper());
    }

    SecEdgarHttpClient(
            RestTemplate restTemplate,
            SecEdgarProviderProperties properties,
            LongSupplier clockMillis,
            LongConsumer sleeperMillis) {
        this(restTemplate, properties, clockMillis, sleeperMillis, new ObjectMapper());
    }

    SecEdgarHttpClient(
            RestTemplate restTemplate,
            SecEdgarProviderProperties properties,
            LongSupplier clockMillis,
            LongConsumer sleeperMillis,
            ObjectMapper objectMapper) {
        this.restTemplate = restTemplate;
        this.properties = properties;
        this.clockMillis = clockMillis;
        this.sleeperMillis = sleeperMillis;
        this.objectMapper = objectMapper;
    }

    public Map<String, Object> getJson(String url) {
        if (!properties.isEnabled()) {
            throw new SecEdgarException("sec_disabled", "SEC EDGAR provider is disabled by configuration.");
        }
        if (!properties.hasDeclaredUserAgent()) {
            throw new SecEdgarException(
                    "missing_user_agent",
                    "SEC EDGAR requests require provider.sec.user-agent.");
        }

        CachedResponse cached = cache.get(url);
        long now = clockMillis.getAsLong();
        if (cached != null && cached.expiresAtMillis() > now) {
            return cached.body();
        }

        throttle(now);
        RequestEntity<Void> request = RequestEntity.get(URI.create(url))
                .header(HttpHeaders.USER_AGENT, properties.getUserAgent().trim())
                .header(HttpHeaders.ACCEPT_ENCODING, "gzip, deflate")
                .accept(MediaType.APPLICATION_JSON)
                .build();
        try {
            ResponseEntity<byte[]> response = restTemplate.exchange(request, byte[].class);
            Map<String, Object> body = parseBody(response);
            long ttlMillis = Math.max(properties.getCacheTtlSeconds(), 0L) * 1_000L;
            if (ttlMillis > 0L) {
                cache.put(url, new CachedResponse(body, clockMillis.getAsLong() + ttlMillis));
            }
            return body;
        } catch (HttpStatusCodeException e) {
            if (e.getStatusCode().value() == 429) {
                throw new SecEdgarException("sec_rate_limited", "SEC EDGAR rate limit response.", e);
            }
            throw new SecEdgarException("sec_http_error", "SEC EDGAR HTTP response failed.", e);
        } catch (RestClientException e) {
            throw new SecEdgarException("sec_http_error", "SEC EDGAR request failed.", e);
        } catch (IOException e) {
            throw new SecEdgarException("sec_parse_error", "SEC EDGAR JSON response could not be parsed.", e);
        }
    }

    private Map<String, Object> parseBody(ResponseEntity<byte[]> response) throws IOException {
        byte[] body = response.getBody();
        if (body == null || body.length == 0) {
            return Map.of();
        }
        byte[] decoded = decodeBody(body, response.getHeaders().getFirst(HttpHeaders.CONTENT_ENCODING));
        return objectMapper.readValue(decoded, new TypeReference<>() {
        });
    }

    private static byte[] decodeBody(byte[] body, String contentEncoding) throws IOException {
        if (contentEncoding == null || contentEncoding.isBlank()) {
            return body;
        }
        String encoding = contentEncoding.toLowerCase(Locale.ROOT);
        InputStream decodedInput;
        if (encoding.contains("gzip")) {
            decodedInput = new GZIPInputStream(new ByteArrayInputStream(body));
        } else if (encoding.contains("deflate")) {
            decodedInput = new InflaterInputStream(new ByteArrayInputStream(body));
        } else {
            return body;
        }
        try (decodedInput) {
            return decodedInput.readAllBytes();
        }
    }

    private synchronized void throttle(long now) {
        int requestsPerSecond = Math.max(1, Math.min(properties.getRequestsPerSecond(), 9));
        long minIntervalMillis = Math.max(1L, (long) Math.ceil(1_000.0 / requestsPerSecond));
        if (lastRequestMillis >= 0L) {
            long elapsed = now - lastRequestMillis;
            long sleepMillis = minIntervalMillis - elapsed;
            if (sleepMillis > 0L) {
                sleeperMillis.accept(sleepMillis);
                now += sleepMillis;
            }
        }
        lastRequestMillis = now;
    }

    private static void sleep(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new SecEdgarException("sec_http_error", "Interrupted while rate limiting SEC EDGAR request.", e);
        }
    }

    private record CachedResponse(Map<String, Object> body, long expiresAtMillis) {
    }
}
