package io.stockvaluation.provider.prospectus;

import io.stockvaluation.provider.sec.SecEdgarException;
import io.stockvaluation.provider.sec.SecEdgarProviderProperties;
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
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.LongConsumer;
import java.util.function.LongSupplier;
import java.util.zip.GZIPInputStream;
import java.util.zip.InflaterInputStream;

@Component
public class SecProspectusDocumentClient implements ProspectusDocumentClient {

    private final RestTemplate restTemplate;
    private final SecEdgarProviderProperties properties;
    private final LongSupplier clockMillis;
    private final LongConsumer sleeperMillis;
    private final Map<String, CachedDocument> cache = new ConcurrentHashMap<>();
    private long lastRequestMillis = -1L;

    @Autowired
    public SecProspectusDocumentClient(RestTemplate restTemplate, SecEdgarProviderProperties properties) {
        this(restTemplate, properties, () -> Instant.now().toEpochMilli(), SecProspectusDocumentClient::sleep);
    }

    SecProspectusDocumentClient(
            RestTemplate restTemplate,
            SecEdgarProviderProperties properties,
            LongSupplier clockMillis,
            LongConsumer sleeperMillis) {
        this.restTemplate = restTemplate;
        this.properties = properties;
        this.clockMillis = clockMillis;
        this.sleeperMillis = sleeperMillis;
    }

    @Override
    public ProspectusDocument fetch(String filingUrl) {
        URI uri = validateSecArchiveUrl(filingUrl);
        if (!properties.isEnabled()) {
            throw new SecEdgarException("sec_disabled", "SEC EDGAR provider is disabled by configuration.");
        }
        if (!properties.hasDeclaredUserAgent()) {
            throw new SecEdgarException("missing_user_agent", "SEC prospectus requests require provider.sec.user-agent.");
        }
        long now = clockMillis.getAsLong();
        CachedDocument cached = cache.get(uri.toString());
        if (cached != null && cached.expiresAtMillis() > now) {
            return new ProspectusDocument(uri.toString(), cached.html());
        }
        throttle(now);
        RequestEntity<Void> request = RequestEntity.get(uri)
                .header(HttpHeaders.USER_AGENT, properties.getUserAgent().trim())
                .header(HttpHeaders.ACCEPT_ENCODING, "gzip, deflate")
                .accept(MediaType.TEXT_HTML, MediaType.APPLICATION_XHTML_XML, MediaType.TEXT_PLAIN)
                .build();
        try {
            ResponseEntity<byte[]> response = restTemplate.exchange(request, byte[].class);
            String body = parseBody(response);
            if (body == null || body.isBlank()) {
                throw new SecEdgarException("sec_parse_error", "SEC prospectus document was empty.");
            }
            long ttlMillis = Math.max(properties.getCacheTtlSeconds(), 0L) * 1_000L;
            if (ttlMillis > 0L) {
                cache.put(uri.toString(), new CachedDocument(body, clockMillis.getAsLong() + ttlMillis));
            }
            return new ProspectusDocument(uri.toString(), body);
        } catch (HttpStatusCodeException e) {
            if (e.getStatusCode().value() == 429) {
                throw new SecEdgarException("sec_rate_limited", "SEC prospectus request received a rate-limit response.", e);
            }
            throw new SecEdgarException("sec_http_error", "SEC prospectus request failed.", e);
        } catch (RestClientException e) {
            throw new SecEdgarException("sec_http_error", "SEC prospectus request failed.", e);
        } catch (IOException e) {
            throw new SecEdgarException("sec_parse_error", "SEC prospectus document could not be decoded.", e);
        }
    }

    private static String parseBody(ResponseEntity<byte[]> response) throws IOException {
        byte[] body = response.getBody();
        if (body == null || body.length == 0) {
            return "";
        }
        byte[] decoded = decodeBody(body, response.getHeaders().getFirst(HttpHeaders.CONTENT_ENCODING));
        return new String(decoded, StandardCharsets.UTF_8);
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

    private static URI validateSecArchiveUrl(String filingUrl) {
        if (filingUrl == null || filingUrl.isBlank()) {
            throw new IllegalArgumentException("filing_url is required.");
        }
        URI uri = URI.create(filingUrl.trim());
        String scheme = uri.getScheme();
        String host = uri.getHost();
        String path = uri.getPath();
        if (!"https".equalsIgnoreCase(scheme)
                || host == null
                || !host.equalsIgnoreCase("www.sec.gov")
                || path == null
                || !path.startsWith("/Archives/edgar/data/")
                || !(path.toLowerCase(Locale.ROOT).endsWith(".htm")
                        || path.toLowerCase(Locale.ROOT).endsWith(".html"))) {
            throw new IllegalArgumentException("unsupported_prospectus_url");
        }
        return uri;
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
            throw new SecEdgarException("sec_http_error", "Interrupted while rate limiting SEC prospectus request.", e);
        }
    }

    private record CachedDocument(String html, long expiresAtMillis) {
    }
}
