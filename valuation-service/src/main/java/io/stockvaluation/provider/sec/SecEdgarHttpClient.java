package io.stockvaluation.provider.sec;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.RequestEntity;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.net.URI;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.LongConsumer;
import java.util.function.LongSupplier;

@Component
public class SecEdgarHttpClient {

    private final RestTemplate restTemplate;
    private final SecEdgarProviderProperties properties;
    private final LongSupplier clockMillis;
    private final LongConsumer sleeperMillis;
    private final Map<String, CachedResponse> cache = new ConcurrentHashMap<>();
    private long lastRequestMillis = -1L;

    @Autowired
    public SecEdgarHttpClient(RestTemplate restTemplate, SecEdgarProviderProperties properties) {
        this(restTemplate, properties, () -> Instant.now().toEpochMilli(), SecEdgarHttpClient::sleep);
    }

    SecEdgarHttpClient(
            RestTemplate restTemplate,
            SecEdgarProviderProperties properties,
            LongSupplier clockMillis,
            LongConsumer sleeperMillis) {
        this.restTemplate = restTemplate;
        this.properties = properties;
        this.clockMillis = clockMillis;
        this.sleeperMillis = sleeperMillis;
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
            ResponseEntity<Map<String, Object>> response = restTemplate.exchange(
                    request,
                    new ParameterizedTypeReference<>() {
                    });
            Map<String, Object> body = response.getBody() == null ? Map.of() : response.getBody();
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
