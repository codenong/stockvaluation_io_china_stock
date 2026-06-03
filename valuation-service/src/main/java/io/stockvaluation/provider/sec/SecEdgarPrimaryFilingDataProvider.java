package io.stockvaluation.provider.sec;

import io.stockvaluation.provider.BalanceSheetSnapshot;
import io.stockvaluation.provider.CashFlowSnapshot;
import io.stockvaluation.provider.IncomeStatementSnapshot;
import io.stockvaluation.provider.PrimaryFilingAvailability;
import io.stockvaluation.provider.PrimaryFilingDataProvider;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Component
@Primary
public class SecEdgarPrimaryFilingDataProvider implements PrimaryFilingDataProvider {

    private static final String PROVIDER_NAME = SecCompanyFactsMapper.PROVIDER_NAME;

    private final SecEdgarProviderProperties properties;
    private final SecTickerCikResolver resolver;
    private final SecEdgarHttpClient client;
    private final SecCompanyFactsMapper mapper;
    private final Map<String, SecMappedCompanyFacts> cache = new ConcurrentHashMap<>();

    public SecEdgarPrimaryFilingDataProvider(
            SecEdgarProviderProperties properties,
            SecTickerCikResolver resolver,
            SecEdgarHttpClient client,
            SecCompanyFactsMapper mapper) {
        this.properties = properties;
        this.resolver = resolver;
        this.client = client;
        this.mapper = mapper;
    }

    @Override
    public boolean hasPrimaryFinancials(String ticker) {
        return getPrimaryFinancialsAvailability(ticker).available();
    }

    @Override
    public PrimaryFilingAvailability getPrimaryFinancialsAvailability(String ticker) {
        return load(ticker).availability();
    }

    @Override
    public Map<String, IncomeStatementSnapshot> getIncomeStatementSnapshots(String ticker, String freq) {
        SecMappedCompanyFacts mapped = load(ticker);
        if (!mapped.availability().available()) {
            return Map.of();
        }
        return "quarterly".equalsIgnoreCase(freq) ? mapped.quarterlyIncome() : mapped.yearlyIncome();
    }

    @Override
    public Map<String, BalanceSheetSnapshot> getBalanceSheetSnapshots(String ticker, String freq) {
        SecMappedCompanyFacts mapped = load(ticker);
        if (!mapped.availability().available()) {
            return Map.of();
        }
        return "quarterly".equalsIgnoreCase(freq) ? mapped.quarterlyBalance() : mapped.yearlyBalance();
    }

    @Override
    public Map<String, CashFlowSnapshot> getCashFlowSnapshots(String ticker, String freq) {
        SecMappedCompanyFacts mapped = load(ticker);
        if (!mapped.availability().available()) {
            return Map.of();
        }
        return "quarterly".equalsIgnoreCase(freq) ? mapped.quarterlyCashFlow() : mapped.yearlyCashFlow();
    }

    @Override
    public String getProviderName() {
        return PROVIDER_NAME;
    }

    private SecMappedCompanyFacts load(String ticker) {
        String normalizedTicker = normalizeTicker(ticker);
        if (!properties.isEnabled()) {
            return unavailable("sec_disabled", "SEC EDGAR provider is disabled by configuration.");
        }
        if (!properties.hasDeclaredUserAgent()) {
            return unavailable("missing_user_agent", "SEC EDGAR provider requires SEC_USER_AGENT/provider.sec.user-agent.");
        }
        if (normalizedTicker.isBlank()) {
            return unavailable("unsupported_filer", "Ticker is not a supported US SEC common-stock ticker.");
        }
        return cache.computeIfAbsent(normalizedTicker, this::fetchAndMap);
    }

    private SecMappedCompanyFacts fetchAndMap(String ticker) {
        try {
            return resolver.resolveCik(ticker)
                    .map(cik -> {
                        Map<String, Object> submissions = client.getJson(dataUrl("/submissions/CIK" + cik + ".json"));
                        Map<String, Object> facts = client.getJson(dataUrl("/api/xbrl/companyfacts/CIK" + cik + ".json"));
                        return mapper.map(ticker, cik, facts, submissions);
                    })
                    .orElseGet(() -> unavailable("cik_not_found", "SEC ticker-to-CIK mapping did not include " + ticker + "."));
        } catch (SecEdgarException e) {
            return unavailable(e.getCategory(), e.getMessage());
        } catch (RuntimeException e) {
            return unavailable("parse_error", "SEC EDGAR response could not be parsed into primary financials.");
        }
    }

    private String dataUrl(String path) {
        return trimTrailingSlash(properties.getDataBaseUrl()) + path;
    }

    private SecMappedCompanyFacts unavailable(String status, String warning) {
        return SecMappedCompanyFacts.unavailable(status, PROVIDER_NAME, List.of(warning));
    }

    private static String normalizeTicker(String ticker) {
        return ticker == null ? "" : ticker.trim().toUpperCase(Locale.ROOT);
    }

    private static String trimTrailingSlash(String value) {
        if (value == null || value.isBlank()) {
            return "https://data.sec.gov";
        }
        return value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }
}
