package io.stockvaluation.provider;

import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Component
public class FixturePrimaryFilingDataProvider implements PrimaryFilingDataProvider {

    private static final String PROVIDER_NAME = "sec-xbrl-fixture";
    private static final double MILLIONS = 1_000_000.0;
    private static final Map<String, FilingFixture> FIXTURES = Map.of(
            "MSFT", fixture(
                    "2025-06-30",
                    List.of(
                            income("2025-06-30", 281724.0, 128528.0, 0.0, 0.0, 19651.0, 108877.0, 32747.0),
                            income("2024-06-30", 245122.0, 109433.0, 0.0, 0.0, 19651.0, 89782.0, 29510.0),
                            income("2023-06-30", 211915.0, 88523.0, 0.0, 0.0, 16950.0, 71573.0, 27195.0),
                            income("2022-06-30", 198270.0, 83383.0, 0.0, 0.0, 10978.0, 72405.0, 24512.0)),
                    List.of(balance("2025-06-30", 335420.0, 67127.0, 95972.0, 7430.0, 0.0))),
            "AAPL", fixture(
                    "2025-09-30",
                    List.of(
                            income("2025-09-30", 407000.0, 132000.0, 0.0, 0.0, 18000.0, 114000.0, 32000.0),
                            income("2024-09-30", 391035.0, 123216.0, 0.0, 0.0, 29749.0, 93736.0, 31370.0),
                            income("2023-09-30", 383285.0, 114301.0, 0.0, 0.0, 16741.0, 113736.0, 29915.0),
                            income("2022-09-30", 394328.0, 119437.0, 0.0, 0.0, 19300.0, 99803.0, 26251.0)),
                    List.of(balance("2025-09-30", 67000.0, 96000.0, 64000.0, 15000.0, 0.0))));

    @Override
    public boolean hasPrimaryFinancials(String ticker) {
        return FIXTURES.containsKey(normalizeTicker(ticker));
    }

    @Override
    public Map<String, IncomeStatementSnapshot> getIncomeStatementSnapshots(String ticker, String freq) {
        FilingFixture fixture = FIXTURES.get(normalizeTicker(ticker));
        if (fixture == null || "quarterly".equalsIgnoreCase(freq)) {
            return Map.of();
        }
        return fixture.incomeSnapshots();
    }

    @Override
    public Map<String, BalanceSheetSnapshot> getBalanceSheetSnapshots(String ticker, String freq) {
        FilingFixture fixture = FIXTURES.get(normalizeTicker(ticker));
        if (fixture == null || "quarterly".equalsIgnoreCase(freq)) {
            return Map.of();
        }
        return fixture.balanceSnapshots();
    }

    @Override
    public String getProviderName() {
        return PROVIDER_NAME;
    }

    private static FilingFixture fixture(
            String latestPeriod,
            List<IncomeStatementSnapshot> incomeSnapshots,
            List<BalanceSheetSnapshot> balanceSnapshots) {
        return new FilingFixture(
                mapByPeriod(incomeSnapshots, latestPeriod),
                mapByPeriod(balanceSnapshots, latestPeriod));
    }

    private static IncomeStatementSnapshot income(
            String periodEnd,
            Double revenue,
            Double operatingIncome,
            Double specialCharges,
            Double interestExpense,
            Double taxProvision,
            Double pretaxIncome,
            Double researchAndDevelopment) {
        return new IncomeStatementSnapshot(
                scaleMillions(revenue),
                scaleMillions(operatingIncome),
                scaleMillions(specialCharges),
                scaleMillions(interestExpense),
                scaleMillions(taxProvision),
                scaleMillions(pretaxIncome),
                scaleMillions(researchAndDevelopment),
                SourceProvenance.primaryFiling(PROVIDER_NAME, periodEnd));
    }

    private static BalanceSheetSnapshot balance(
            String periodEnd,
            Double equity,
            Double debt,
            Double cash,
            Double shares,
            Double minorityInterest) {
        return new BalanceSheetSnapshot(
                scaleMillions(equity),
                scaleMillions(debt),
                scaleMillions(cash),
                scaleMillions(shares),
                scaleMillions(minorityInterest),
                SourceProvenance.primaryFiling(PROVIDER_NAME, periodEnd));
    }

    private static Double scaleMillions(Double value) {
        return value == null ? null : value * MILLIONS;
    }

    private static <T> Map<String, T> mapByPeriod(List<T> snapshots, String latestPeriod) {
        java.util.LinkedHashMap<String, T> mapped = new java.util.LinkedHashMap<>();
        int year = LocalDate.parse(latestPeriod).getYear();
        for (T snapshot : snapshots) {
            String periodEnd;
            if (snapshot instanceof IncomeStatementSnapshot income) {
                periodEnd = income.sourceProvenance().getPeriodEnd();
            } else if (snapshot instanceof BalanceSheetSnapshot balance) {
                periodEnd = balance.sourceProvenance().getPeriodEnd();
            } else {
                periodEnd = year + "-12-31";
            }
            mapped.put(epochMillis(periodEnd), snapshot);
            year--;
        }
        return mapped;
    }

    private static String epochMillis(String periodEnd) {
        return String.valueOf(LocalDate.parse(periodEnd)
                .atStartOfDay()
                .toInstant(ZoneOffset.UTC)
                .toEpochMilli());
    }

    private static String normalizeTicker(String ticker) {
        return ticker == null ? "" : ticker.trim().toUpperCase(Locale.ROOT);
    }

    private record FilingFixture(
            Map<String, IncomeStatementSnapshot> incomeSnapshots,
            Map<String, BalanceSheetSnapshot> balanceSnapshots) {
    }
}
