package io.stockvaluation.provider.sec;

import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;

@Component
public class SecTickerCikResolver {

    private final SecEdgarHttpClient client;
    private final SecEdgarProviderProperties properties;
    private volatile Map<String, String> cachedMapping;

    public SecTickerCikResolver(SecEdgarHttpClient client, SecEdgarProviderProperties properties) {
        this.client = client;
        this.properties = properties;
    }

    public Optional<String> resolveCik(String ticker) {
        String normalized = normalizeTicker(ticker);
        if (normalized.isBlank()) {
            return Optional.empty();
        }
        return Optional.ofNullable(loadMapping().get(normalized));
    }

    private Map<String, String> loadMapping() {
        Map<String, String> existing = cachedMapping;
        if (existing != null) {
            return existing;
        }
        synchronized (this) {
            if (cachedMapping == null) {
                cachedMapping = parseMapping(client.getJson(secUrl("/files/company_tickers_exchange.json")));
            }
            return cachedMapping;
        }
    }

    private String secUrl(String path) {
        return trimTrailingSlash(properties.getSecBaseUrl()) + path;
    }

    private static Map<String, String> parseMapping(Map<String, Object> payload) {
        Map<String, String> mapping = new HashMap<>();
        Object fieldsObject = payload.get("fields");
        Object dataObject = payload.get("data");
        if (fieldsObject instanceof List<?> fields && dataObject instanceof List<?> rows) {
            int cikIndex = indexOf(fields, "cik");
            int tickerIndex = indexOf(fields, "ticker");
            if (cikIndex < 0 || tickerIndex < 0) {
                return mapping;
            }
            for (Object rowObject : rows) {
                if (!(rowObject instanceof List<?> row)
                        || row.size() <= Math.max(cikIndex, tickerIndex)) {
                    continue;
                }
                String ticker = normalizeTicker(String.valueOf(row.get(tickerIndex)));
                String cik = normalizeCik(row.get(cikIndex));
                if (!ticker.isBlank() && !cik.isBlank()) {
                    mapping.put(ticker, cik);
                }
            }
        }
        return mapping;
    }

    private static int indexOf(List<?> values, String expected) {
        for (int i = 0; i < values.size(); i++) {
            if (expected.equalsIgnoreCase(String.valueOf(values.get(i)))) {
                return i;
            }
        }
        return -1;
    }

    static String normalizeTicker(String ticker) {
        return ticker == null
                ? ""
                : ticker.trim().toUpperCase(Locale.ROOT).replace('.', '-');
    }

    static String normalizeCik(Object value) {
        if (value == null) {
            return "";
        }
        String raw = String.valueOf(value).replaceAll("\\D", "");
        if (raw.isBlank()) {
            return "";
        }
        return String.format("%010d", Long.parseLong(raw));
    }

    private static String trimTrailingSlash(String value) {
        if (value == null || value.isBlank()) {
            return "https://www.sec.gov";
        }
        return value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }
}
