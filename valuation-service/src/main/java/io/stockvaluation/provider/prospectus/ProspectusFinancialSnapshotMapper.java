package io.stockvaluation.provider.prospectus;

import io.stockvaluation.provider.BalanceSheetSnapshot;
import io.stockvaluation.provider.CashFlowSnapshot;
import io.stockvaluation.provider.IncomeStatementSnapshot;
import io.stockvaluation.provider.SourceProvenance;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;

@Component
public class ProspectusFinancialSnapshotMapper {

    public ProspectusMappedSnapshots map(ProspectusFinancialPacket packet) {
        TreeMap<String, IncomeStatementBuilder> incomeBuilders = new TreeMap<>();
        TreeMap<String, BalanceSheetBuilder> balanceBuilders = new TreeMap<>();
        if (packet.getFinancials() != null) {
            for (ProspectusFact fact : packet.getFinancials().getIncomeStatement()) {
                if (fact.getNormalizedValue() == null) {
                    continue;
                }
                incomeBuilders.computeIfAbsent(periodKey(fact.getPeriodEnd()), ignored -> new IncomeStatementBuilder())
                        .apply(fact);
            }
            for (ProspectusFact fact : packet.getFinancials().getBalanceSheet()) {
                if (fact.getNormalizedValue() == null) {
                    continue;
                }
                balanceBuilders.computeIfAbsent(periodKey(fact.getPeriodEnd()), ignored -> new BalanceSheetBuilder())
                        .apply(fact);
            }
        }

        Double shares = clearShares(packet);
        if (shares != null && !balanceBuilders.isEmpty()) {
            balanceBuilders.get(balanceBuilders.keySet().stream().max(String::compareTo).orElseThrow()).sharesOutstanding = shares;
        }

        Map<String, IncomeStatementSnapshot> yearlyIncome = new LinkedHashMap<>();
        incomeBuilders.descendingMap()
                .forEach((period, builder) -> yearlyIncome.put(period, builder.build(packet.getSourceProvenance())));
        Map<String, BalanceSheetSnapshot> yearlyBalance = new LinkedHashMap<>();
        balanceBuilders.descendingMap()
                .forEach((period, builder) -> yearlyBalance.put(period, builder.build(packet.getSourceProvenance())));
        return new ProspectusMappedSnapshots(yearlyIncome, yearlyBalance, Map.of());
    }

    private static Double clearShares(ProspectusFinancialPacket packet) {
        if (packet.getOffering() != null
                && packet.getOffering().getPostOfferingShares() != null
                && packet.getOffering().getPostOfferingShares() > 0) {
            return packet.getOffering().getPostOfferingShares();
        }
        if (packet.getShareCounts() == null || packet.getShareCounts().isEmpty()) {
            return null;
        }
        return packet.getShareCounts().stream()
                .map(ProspectusShareCountFact::getNormalizedValue)
                .filter(Objects::nonNull)
                .findFirst()
                .orElse(null);
    }

    static String periodKey(String periodEnd) {
        String value = periodEnd == null || periodEnd.isBlank() ? "1970-01-01" : periodEnd;
        return String.valueOf(LocalDate.parse(value).atStartOfDay().toInstant(ZoneOffset.UTC).toEpochMilli());
    }

    private static class IncomeStatementBuilder {
        Double revenue;
        Double operatingIncome;
        Double rd;
        SourceProvenance provenance;

        void apply(ProspectusFact fact) {
            provenance = fact.getSourceProvenance();
            switch (fact.getCanonicalField()) {
                case "revenue", "prior_revenue" -> revenue = firstPresent(revenue, fact.getNormalizedValue());
                case "operating_income" -> operatingIncome = firstPresent(operatingIncome, fact.getNormalizedValue());
                case "research_and_development" -> rd = firstPresent(rd, fact.getNormalizedValue());
                default -> {
                }
            }
        }

        IncomeStatementSnapshot build(SourceProvenance fallbackProvenance) {
            return new IncomeStatementSnapshot(
                    revenue,
                    operatingIncome,
                    null,
                    null,
                    null,
                    null,
                    rd,
                    provenance != null ? provenance : fallbackProvenance);
        }
    }

    private static class BalanceSheetBuilder {
        Double bookEquity;
        Double debt;
        Double cash;
        Double sharesOutstanding;
        SourceProvenance provenance;

        void apply(ProspectusFact fact) {
            provenance = fact.getSourceProvenance();
            switch (fact.getCanonicalField()) {
                case "book_value_equity" -> bookEquity = firstPresent(bookEquity, fact.getNormalizedValue());
                case "total_debt" -> debt = firstPresent(debt, fact.getNormalizedValue());
                case "cash_and_short_term_investments" -> cash = firstPresent(cash, fact.getNormalizedValue());
                default -> {
                }
            }
        }

        BalanceSheetSnapshot build(SourceProvenance fallbackProvenance) {
            return new BalanceSheetSnapshot(
                    bookEquity,
                    debt,
                    cash,
                    sharesOutstanding,
                    null,
                    provenance != null ? provenance : fallbackProvenance);
        }
    }

    private static Double firstPresent(Double current, Double candidate) {
        return current == null ? candidate : current;
    }
}
