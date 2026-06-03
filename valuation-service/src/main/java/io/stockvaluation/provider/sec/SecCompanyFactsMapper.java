package io.stockvaluation.provider.sec;

import io.stockvaluation.provider.BalanceSheetSnapshot;
import io.stockvaluation.provider.CashFlowSnapshot;
import io.stockvaluation.provider.IncomeStatementSnapshot;
import io.stockvaluation.provider.PrimaryFilingAvailability;
import io.stockvaluation.provider.SourceProvenance;
import io.stockvaluation.provider.field.FinancialFieldDefinitionCatalog;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

@Component
public class SecCompanyFactsMapper {

    static final String PROVIDER_NAME = "sec-edgar-companyfacts";
    private static final FinancialFieldDefinitionCatalog FIELD_DEFINITIONS =
            FinancialFieldDefinitionCatalog.loadDefault();

    private static final List<String> REVENUE_TAGS = secConcepts("revenue");
    private static final List<String> OPERATING_INCOME_TAGS = secConcepts("operating_income");
    private static final List<String> INTEREST_EXPENSE_TAGS = secConcepts("interest_expense");
    private static final List<String> TAX_PROVISION_TAGS = secConcepts("tax_provision");
    private static final List<String> PRETAX_INCOME_TAGS = secConcepts("pretax_income");
    private static final List<String> RD_TAGS = secConcepts("research_and_development");
    private static final List<String> BASIC_SHARES_TAGS = secConcepts("basic_shares");
    private static final List<String> DILUTED_SHARES_TAGS = secConcepts("diluted_shares");
    private static final List<String> EQUITY_TAGS = secConcepts("book_equity");
    private static final List<String> TOTAL_DEBT_TAGS = List.of("DebtCurrentAndNoncurrent");
    private static final List<String> DEBT_CURRENT_TAGS = List.of(
            "LongTermDebtAndFinanceLeaseObligationsCurrent",
            "LongTermDebtCurrent",
            "ShortTermBorrowings",
            "ShortTermDebt");
    private static final List<String> DEBT_NONCURRENT_TAGS = List.of(
            "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
            "LongTermDebtNoncurrent",
            "LongTermDebt");
    private static final List<String> CASH_TAGS = List.of("CashCashEquivalentsAndShortTermInvestments");
    private static final List<String> CASH_ONLY_TAGS = List.of("CashAndCashEquivalentsAtCarryingValue");
    private static final List<String> SHORT_INVESTMENT_TAGS = List.of("ShortTermInvestments");
    private static final List<String> SHARES_OUTSTANDING_TAGS = secConcepts("shares_outstanding");
    private static final List<String> MINORITY_INTEREST_TAGS = secConcepts("minority_interest");
    private static final List<String> SBC_TAGS = secConcepts("stock_based_compensation");

    public SecMappedCompanyFacts map(
            String ticker,
            String cik,
            Map<String, Object> companyFacts,
            Map<String, Object> submissions) {
        Object factsObject = companyFacts.get("facts");
        if (!(factsObject instanceof Map<?, ?> facts)) {
            return insufficientFacts("SEC companyfacts payload did not include a facts object.");
        }
        SecSubmissionsMetadata metadata = SecSubmissionsMetadata.from(submissions);
        if (!metadata.hasUsPeriodicFiling()) {
            if (facts.containsKey("ifrs-full")) {
                return unsupportedTaxonomy(ticker);
            }
            return SecMappedCompanyFacts.unavailable(
                    "unsupported_filer",
                    PROVIDER_NAME,
                    List.of("SEC submissions did not include recent 10-K or 10-Q filings for " + ticker + "."));
        }
        Object usGaapObject = facts.get("us-gaap");
        if (!(usGaapObject instanceof Map<?, ?> usGaap)) {
            if (facts.containsKey("ifrs-full")) {
                return unsupportedTaxonomy(ticker);
            }
            return SecMappedCompanyFacts.unavailable(
                    "unsupported_filer",
                    PROVIDER_NAME,
                    List.of("SEC companyfacts payload did not include us-gaap facts for " + ticker + "."));
        }
        Map<String, Object> usGaapFacts = stringKeyMap(usGaap);
        Map<String, Object> deiFacts = facts.get("dei") instanceof Map<?, ?> dei ? stringKeyMap(dei) : Map.of();

        Map<String, IncomeStatementSnapshot> yearlyIncome = incomeSnapshots(usGaapFacts, PeriodKind.ANNUAL);
        Map<String, IncomeStatementSnapshot> quarterlyIncome = incomeSnapshots(usGaapFacts, PeriodKind.QUARTERLY);
        Map<String, BalanceSheetSnapshot> yearlyBalance = balanceSnapshots(usGaapFacts, deiFacts, PeriodKind.ANNUAL);
        Map<String, BalanceSheetSnapshot> quarterlyBalance = balanceSnapshots(usGaapFacts, deiFacts, PeriodKind.QUARTERLY);
        Map<String, CashFlowSnapshot> yearlyCashFlow = cashFlowSnapshots(usGaapFacts, PeriodKind.ANNUAL);
        Map<String, CashFlowSnapshot> quarterlyCashFlow = cashFlowSnapshots(usGaapFacts, PeriodKind.QUARTERLY);

        if (yearlyIncome.isEmpty() || yearlyBalance.isEmpty()) {
            return insufficientFacts("SEC companyfacts did not include required SEC companyfacts for revenue, operating income, equity, and cash.");
        }

        return new SecMappedCompanyFacts(
                yearlyIncome,
                quarterlyIncome,
                yearlyBalance,
                quarterlyBalance,
                yearlyCashFlow,
                quarterlyCashFlow,
                PrimaryFilingAvailability.available(PROVIDER_NAME));
    }

    private static SecMappedCompanyFacts insufficientFacts(String warning) {
        return SecMappedCompanyFacts.unavailable("insufficient_facts", PROVIDER_NAME, List.of(warning));
    }

    private static SecMappedCompanyFacts unsupportedTaxonomy(String ticker) {
        return SecMappedCompanyFacts.unavailable(
                "unsupported_taxonomy",
                PROVIDER_NAME,
                List.of("SEC companyfacts for " + ticker
                        + " used ifrs-full taxonomy; the local mapper currently supports us-gaap facts only."));
    }

    private static List<String> secConcepts(String fieldName) {
        return FIELD_DEFINITIONS.secConcepts(fieldName).stream()
                .map(SecCompanyFactsMapper::stripTaxonomyPrefix)
                .toList();
    }

    private static String stripTaxonomyPrefix(String concept) {
        int separator = concept.indexOf(':');
        return separator >= 0 ? concept.substring(separator + 1) : concept;
    }

    private static Map<String, IncomeStatementSnapshot> incomeSnapshots(
            Map<String, Object> facts,
            PeriodKind kind) {
        List<SecFact> anchors = factsForTags(facts, REVENUE_TAGS, List.of("USD")).stream()
                .filter(fact -> matchesPeriod(fact, kind, false))
                .sorted(SecFact.BY_END_DESC)
                .toList();
        Map<String, IncomeStatementSnapshot> snapshots = new LinkedHashMap<>();
        for (SecFact anchor : uniquePeriods(anchors, 4)) {
            FactChoice revenue = chooseFact(facts, REVENUE_TAGS, List.of("USD"), anchor.end(), kind, false);
            FactChoice operatingIncome = chooseFact(facts, OPERATING_INCOME_TAGS, List.of("USD"), anchor.end(), kind, false);
            if (revenue.value() == null || operatingIncome.value() == null) {
                continue;
            }
            FactChoice interestExpense = chooseFact(facts, INTEREST_EXPENSE_TAGS, List.of("USD"), anchor.end(), kind, false);
            FactChoice taxProvision = chooseFact(facts, TAX_PROVISION_TAGS, List.of("USD"), anchor.end(), kind, false);
            FactChoice pretaxIncome = chooseFact(facts, PRETAX_INCOME_TAGS, List.of("USD"), anchor.end(), kind, false);
            FactChoice researchDevelopment = chooseFact(facts, RD_TAGS, List.of("USD"), anchor.end(), kind, false);
            FactChoice basicShares = chooseFact(facts, BASIC_SHARES_TAGS, List.of("shares"), anchor.end(), kind, false);
            FactChoice dilutedShares = chooseFact(facts, DILUTED_SHARES_TAGS, List.of("shares"), anchor.end(), kind, false);
            List<String> warnings = warnings(
                    revenue,
                    operatingIncome,
                    interestExpense,
                    taxProvision,
                    pretaxIncome,
                    researchDevelopment,
                    basicShares,
                    dilutedShares);
            SourceProvenance provenance = provenance(sourceDate(anchor, revenue, operatingIncome), anchor.end(), warnings);
            snapshots.put(epochMillis(anchor.end()), new IncomeStatementSnapshot(
                    revenue.value(),
                    operatingIncome.value(),
                    null,
                    interestExpense.value(),
                    taxProvision.value(),
                    pretaxIncome.value(),
                    researchDevelopment.value(),
                    basicShares.value(),
                    dilutedShares.value(),
                    provenance));
        }
        return snapshots;
    }

    private static Map<String, BalanceSheetSnapshot> balanceSnapshots(
            Map<String, Object> usGaapFacts,
            Map<String, Object> deiFacts,
            PeriodKind kind) {
        List<SecFact> anchors = factsForTags(usGaapFacts, EQUITY_TAGS, List.of("USD")).stream()
                .filter(fact -> matchesPeriod(fact, kind, true))
                .sorted(SecFact.BY_END_DESC)
                .toList();
        Map<String, BalanceSheetSnapshot> snapshots = new LinkedHashMap<>();
        for (SecFact anchor : uniquePeriods(anchors, 4)) {
            FactChoice equity = chooseFact(usGaapFacts, EQUITY_TAGS, List.of("USD"), anchor.end(), kind, true);
            FactChoice cash = chooseCash(usGaapFacts, anchor.end(), kind);
            if (equity.value() == null || cash.value() == null) {
                continue;
            }
            FactChoice debt = chooseDebt(usGaapFacts, anchor.end(), kind);
            FactChoice shares = chooseFact(deiFacts, SHARES_OUTSTANDING_TAGS, List.of("shares"), anchor.end(), kind, true);
            FactChoice minorityInterest = chooseFact(
                    usGaapFacts,
                    MINORITY_INTEREST_TAGS,
                    List.of("USD"),
                    anchor.end(),
                    kind,
                    true);
            List<String> warnings = warnings(equity, cash, debt, shares, minorityInterest);
            SourceProvenance provenance = provenance(sourceDate(anchor, equity, cash, debt, shares), anchor.end(), warnings);
            snapshots.put(epochMillis(anchor.end()), new BalanceSheetSnapshot(
                    equity.value(),
                    debt.value(),
                    cash.value(),
                    shares.value(),
                    minorityInterest.value(),
                    provenance));
        }
        return snapshots;
    }

    private static Map<String, CashFlowSnapshot> cashFlowSnapshots(
            Map<String, Object> facts,
            PeriodKind kind) {
        List<SecFact> anchors = factsForTags(facts, SBC_TAGS, List.of("USD")).stream()
                .filter(fact -> matchesPeriod(fact, kind, false))
                .sorted(SecFact.BY_END_DESC)
                .toList();
        Map<String, CashFlowSnapshot> snapshots = new LinkedHashMap<>();
        for (SecFact anchor : uniquePeriods(anchors, 4)) {
            SourceProvenance provenance = provenance(anchor.filed(), anchor.end(), List.of());
            snapshots.put(epochMillis(anchor.end()), new CashFlowSnapshot(anchor.value(), provenance));
        }
        return snapshots;
    }

    private static FactChoice chooseDebt(Map<String, Object> facts, LocalDate end, PeriodKind kind) {
        FactChoice total = chooseFact(facts, TOTAL_DEBT_TAGS, List.of("USD"), end, kind, true);
        if (total.value() != null) {
            return total;
        }
        FactChoice current = chooseFact(facts, DEBT_CURRENT_TAGS, List.of("USD"), end, kind, true);
        FactChoice noncurrent = chooseFact(facts, DEBT_NONCURRENT_TAGS, List.of("USD"), end, kind, true);
        if (current.value() == null && noncurrent.value() == null) {
            return FactChoice.empty();
        }
        List<String> warnings = new ArrayList<>(warnings(current, noncurrent));
        warnings.add("SEC debt used current plus noncurrent debt tags because a total debt tag was unavailable.");
        return new FactChoice(
                valueOrZero(current.value()) + valueOrZero(noncurrent.value()),
                latestDate(current.sourceDate(), noncurrent.sourceDate()),
                warnings);
    }

    private static FactChoice chooseCash(Map<String, Object> facts, LocalDate end, PeriodKind kind) {
        FactChoice cash = chooseFact(facts, CASH_TAGS, List.of("USD"), end, kind, true);
        if (cash.value() != null) {
            return cash;
        }
        FactChoice cashOnly = chooseFact(facts, CASH_ONLY_TAGS, List.of("USD"), end, kind, true);
        FactChoice shortInvestments = chooseFact(facts, SHORT_INVESTMENT_TAGS, List.of("USD"), end, kind, true);
        if (cashOnly.value() == null && shortInvestments.value() == null) {
            return FactChoice.empty();
        }
        List<String> warnings = new ArrayList<>(warnings(cashOnly, shortInvestments));
        warnings.add("SEC cash used cash plus short-term investment tags because the combined cash tag was unavailable.");
        return new FactChoice(
                valueOrZero(cashOnly.value()) + valueOrZero(shortInvestments.value()),
                latestDate(cashOnly.sourceDate(), shortInvestments.sourceDate()),
                warnings);
    }

    private static FactChoice chooseFact(
            Map<String, Object> facts,
            List<String> tags,
            List<String> units,
            LocalDate end,
            PeriodKind kind,
            boolean instant) {
        for (int i = 0; i < tags.size(); i++) {
            String tag = tags.get(i);
            Optional<SecFact> fact = factsForTag(facts, tag, units).stream()
                    .filter(candidate -> Objects.equals(candidate.end(), end))
                    .filter(candidate -> matchesPeriod(candidate, kind, instant))
                    .max(SecFact.BY_FILED_ASC);
            if (fact.isPresent()) {
                List<String> warnings = i == 0
                        ? List.of()
                        : List.of("SEC companyfacts used fallback tag us-gaap:" + tag + ".");
                return new FactChoice(fact.get().value(), fact.get().filed(), warnings);
            }
        }
        return FactChoice.empty();
    }

    private static List<SecFact> factsForTags(Map<String, Object> facts, List<String> tags, List<String> units) {
        return tags.stream()
                .flatMap(tag -> factsForTag(facts, tag, units).stream())
                .toList();
    }

    private static List<SecFact> factsForTag(Map<String, Object> facts, String tag, List<String> preferredUnits) {
        Object tagObject = facts.get(tag);
        if (!(tagObject instanceof Map<?, ?> tagMap)) {
            return List.of();
        }
        Object unitsObject = tagMap.get("units");
        if (!(unitsObject instanceof Map<?, ?> unitsMap)) {
            return List.of();
        }
        List<SecFact> parsed = new ArrayList<>();
        for (String unit : preferredUnits) {
            Object unitFactsObject = unitsMap.get(unit);
            if (!(unitFactsObject instanceof List<?> unitFacts)) {
                continue;
            }
            for (Object factObject : unitFacts) {
                if (factObject instanceof Map<?, ?> factMap) {
                    SecFact.from(tag, unit, stringKeyMap(factMap)).ifPresent(parsed::add);
                }
            }
            if (!parsed.isEmpty()) {
                return parsed;
            }
        }
        return parsed;
    }

    private static boolean matchesPeriod(SecFact fact, PeriodKind kind, boolean instant) {
        if (fact.end() == null) {
            return false;
        }
        String form = fact.form().toUpperCase(Locale.ROOT);
        String fp = fact.fp().toUpperCase(Locale.ROOT);
        String frame = fact.frame().toUpperCase(Locale.ROOT);
        if (kind == PeriodKind.ANNUAL) {
            if (instant) {
                return "10-K".equals(form) || "FY".equals(fp);
            }
            return ("10-K".equals(form) || "FY".equals(fp)) && durationDays(fact) >= 330 && durationDays(fact) <= 390;
        }
        if (instant) {
            return frame.endsWith("I") || "10-Q".equals(form) || fp.startsWith("Q");
        }
        return frame.matches("CY\\d{4}Q[1-4]")
                || ("10-Q".equals(form) && fp.startsWith("Q") && durationDays(fact) >= 70 && durationDays(fact) <= 110);
    }

    private static long durationDays(SecFact fact) {
        if (fact.start() == null || fact.end() == null) {
            return 0L;
        }
        return ChronoUnit.DAYS.between(fact.start(), fact.end()) + 1L;
    }

    private static List<SecFact> uniquePeriods(List<SecFact> facts, int limit) {
        List<SecFact> unique = new ArrayList<>();
        List<LocalDate> seen = new ArrayList<>();
        for (SecFact fact : facts) {
            if (seen.contains(fact.end())) {
                continue;
            }
            seen.add(fact.end());
            unique.add(fact);
            if (unique.size() == limit) {
                break;
            }
        }
        return unique;
    }

    private static SourceProvenance provenance(String sourceDate, LocalDate periodEnd, List<String> warnings) {
        SourceProvenance provenance = SourceProvenance.primaryFiling(
                PROVIDER_NAME,
                sourceDate,
                periodEnd == null ? null : periodEnd.toString());
        provenance.setWarnings(warnings);
        return provenance;
    }

    private static String sourceDate(SecFact anchor, FactChoice... choices) {
        String latest = anchor.filed();
        for (FactChoice choice : choices) {
            latest = latestDate(latest, choice.sourceDate());
        }
        return latest;
    }

    private static List<String> warnings(FactChoice... choices) {
        List<String> warnings = new ArrayList<>();
        for (FactChoice choice : choices) {
            warnings.addAll(choice.warnings());
        }
        return warnings.stream().filter(value -> !value.isBlank()).distinct().toList();
    }

    private static String latestDate(String left, String right) {
        if (left == null || left.isBlank()) {
            return right;
        }
        if (right == null || right.isBlank()) {
            return left;
        }
        return left.compareTo(right) >= 0 ? left : right;
    }

    private static double valueOrZero(Double value) {
        return value == null ? 0.0 : value;
    }

    private static String epochMillis(LocalDate date) {
        return String.valueOf(date.atStartOfDay().toInstant(ZoneOffset.UTC).toEpochMilli());
    }

    private static Map<String, Object> stringKeyMap(Map<?, ?> map) {
        Map<String, Object> typed = new LinkedHashMap<>();
        for (Map.Entry<?, ?> entry : map.entrySet()) {
            typed.put(String.valueOf(entry.getKey()), entry.getValue());
        }
        return typed;
    }

    private enum PeriodKind {
        ANNUAL,
        QUARTERLY
    }

    private record FactChoice(Double value, String sourceDate, List<String> warnings) {
        static FactChoice empty() {
            return new FactChoice(null, null, List.of());
        }
    }

    private record SecFact(
            String tag,
            String unit,
            Double value,
            LocalDate start,
            LocalDate end,
            String filed,
            String form,
            String fp,
            String frame) {

        static final Comparator<SecFact> BY_END_DESC =
                Comparator.comparing(SecFact::end, Comparator.nullsLast(Comparator.naturalOrder())).reversed()
                        .thenComparing(SecFact::filed, Comparator.nullsLast(Comparator.reverseOrder()));
        static final Comparator<SecFact> BY_FILED_ASC =
                Comparator.comparing(SecFact::filed, Comparator.nullsLast(Comparator.naturalOrder()));

        static Optional<SecFact> from(String tag, String unit, Map<String, Object> payload) {
            Double value = number(payload.get("val"));
            LocalDate end = date(payload.get("end"));
            if (value == null || end == null) {
                return Optional.empty();
            }
            return Optional.of(new SecFact(
                    tag,
                    unit,
                    value,
                    date(payload.get("start")),
                    end,
                    string(payload.get("filed")),
                    string(payload.get("form")),
                    string(payload.get("fp")),
                    string(payload.get("frame"))));
        }
    }

    private static Double number(Object value) {
        return value instanceof Number number ? number.doubleValue() : null;
    }

    private static LocalDate date(Object value) {
        try {
            String raw = string(value);
            return raw.isBlank() ? null : LocalDate.parse(raw);
        } catch (RuntimeException e) {
            return null;
        }
    }

    private static String string(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }
}
