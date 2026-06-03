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
    private static final List<String> DEBT_CURRENT_MATURITY_TAGS = List.of(
            "LongTermDebtAndFinanceLeaseObligationsCurrent",
            "LongTermDebtCurrent",
            "DebtCurrent");
    private static final List<String> SHORT_TERM_BORROWING_TAGS = List.of(
            "ShortTermBorrowings",
            "ShortTermDebt",
            "OtherShortTermBorrowings",
            "CommercialPaper");
    private static final List<String> DEBT_NONCURRENT_TAGS = List.of(
            "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
            "LongTermDebtNoncurrent",
            "LongTermDebt");
    private static final List<String> OPERATING_LEASE_TOTAL_TAGS = List.of("OperatingLeaseLiability");
    private static final List<String> OPERATING_LEASE_CURRENT_TAGS = List.of("OperatingLeaseLiabilityCurrent");
    private static final List<String> OPERATING_LEASE_NONCURRENT_TAGS = List.of("OperatingLeaseLiabilityNoncurrent");
    private static final List<String> FINANCE_LEASE_TOTAL_TAGS = List.of("FinanceLeaseLiability");
    private static final List<String> FINANCE_LEASE_CURRENT_TAGS = List.of("FinanceLeaseLiabilityCurrent");
    private static final List<String> FINANCE_LEASE_NONCURRENT_TAGS = List.of("FinanceLeaseLiabilityNoncurrent");
    private static final List<String> CASH_TAGS = List.of("CashCashEquivalentsAndShortTermInvestments");
    private static final List<String> CASH_ONLY_TAGS = List.of("CashAndCashEquivalentsAtCarryingValue");
    private static final List<String> SHORT_INVESTMENT_TAGS = List.of(
            "ShortTermInvestments",
            "MarketableSecuritiesCurrent",
            "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
            "DebtSecuritiesAvailableForSaleExcludingAccruedInterestCurrent");
    private static final List<String> NONCURRENT_MARKETABLE_SECURITY_TAGS = List.of(
            "MarketableSecuritiesNoncurrent",
            "AvailableForSaleSecuritiesDebtSecuritiesNoncurrent");
    private static final List<String> INTEREST_INCOME_TAGS = List.of(
            "InvestmentIncomeInterest",
            "InterestIncomeOperating");
    private static final List<String> NET_INTEREST_INCOME_EXPENSE_TAGS = List.of("InterestIncomeExpenseNonoperatingNet");
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
        int anchorLimit = kind == PeriodKind.QUARTERLY ? 8 : 4;
        for (SecFact anchor : uniquePeriods(anchors, anchorLimit)) {
            FactChoice revenue = chooseFact(facts, REVENUE_TAGS, List.of("USD"), anchor.end(), kind, false);
            FactChoice operatingIncome = chooseFact(facts, OPERATING_INCOME_TAGS, List.of("USD"), anchor.end(), kind, false);
            if (revenue.value() == null || operatingIncome.value() == null) {
                continue;
            }
            FactChoice interestExpense = chooseInterestExpense(facts, anchor.end(), kind);
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
        if (kind == PeriodKind.QUARTERLY) {
            synthesizeFourthQuarterIncomeSnapshots(facts, snapshots);
        }
        return latestPeriods(snapshots, 4);
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
            FactChoice shares = chooseSharesOutstanding(usGaapFacts, deiFacts, anchor.end(), kind);
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
        int anchorLimit = kind == PeriodKind.QUARTERLY ? 8 : 4;
        for (SecFact anchor : uniquePeriods(anchors, anchorLimit)) {
            SourceProvenance provenance = provenance(anchor.filed(), anchor.end(), List.of());
            snapshots.put(epochMillis(anchor.end()), new CashFlowSnapshot(anchor.value(), provenance));
        }
        if (kind == PeriodKind.QUARTERLY) {
            synthesizeFourthQuarterCashFlowSnapshots(facts, snapshots);
        }
        return latestPeriods(snapshots, 4);
    }

    private static FactChoice chooseDebt(Map<String, Object> facts, LocalDate end, PeriodKind kind) {
        FactChoice total = chooseFact(facts, TOTAL_DEBT_TAGS, List.of("USD"), end, kind, true);
        FactChoice currentMaturity = chooseFact(facts, DEBT_CURRENT_MATURITY_TAGS, List.of("USD"), end, kind, true);
        FactChoice shortTermBorrowing = chooseFact(facts, SHORT_TERM_BORROWING_TAGS, List.of("USD"), end, kind, true);
        FactChoice noncurrent = chooseFact(facts, DEBT_NONCURRENT_TAGS, List.of("USD"), end, kind, true);
        FactChoice debtBase = total.value() != null
                ? total
                : combineFacts(
                        "SEC debt used current, short-term borrowing, and noncurrent debt tags because a total debt tag was unavailable.",
                        currentMaturity,
                        shortTermBorrowing,
                        noncurrent);
        FactChoice operatingLease = chooseLeaseLiability(
                facts,
                OPERATING_LEASE_TOTAL_TAGS,
                OPERATING_LEASE_CURRENT_TAGS,
                OPERATING_LEASE_NONCURRENT_TAGS,
                end,
                kind,
                "SEC operating lease liability used current plus noncurrent lease tags because a total operating lease liability tag was unavailable.");
        FactChoice financeLease = chooseLeaseLiability(
                facts,
                FINANCE_LEASE_TOTAL_TAGS,
                FINANCE_LEASE_CURRENT_TAGS,
                FINANCE_LEASE_NONCURRENT_TAGS,
                end,
                kind,
                "SEC finance lease liability used current plus noncurrent lease tags because a total finance lease liability tag was unavailable.");
        if (debtBase.value() == null && operatingLease.value() == null && financeLease.value() == null) {
            return FactChoice.empty();
        }
        double financeLeaseValue = includesFinanceLease(debtBase, currentMaturity, noncurrent)
                ? 0.0
                : valueOrZero(financeLease.value());
        List<String> warnings = new ArrayList<>(warnings(debtBase, operatingLease, financeLease));
        if (operatingLease.value() != null || financeLeaseValue != 0.0) {
            warnings.add("SEC debt included recognized lease liability tags because recognized lease liabilities are treated as debt.");
        }
        return new FactChoice(
                valueOrZero(debtBase.value()) + valueOrZero(operatingLease.value()) + financeLeaseValue,
                latestDate(
                        latestDate(debtBase.sourceDate(), operatingLease.sourceDate()),
                        financeLease.sourceDate()),
                warnings,
                debtBase.tag());
    }

    private static FactChoice chooseLeaseLiability(
            Map<String, Object> facts,
            List<String> totalTags,
            List<String> currentTags,
            List<String> noncurrentTags,
            LocalDate end,
            PeriodKind kind,
            String synthesisWarning) {
        FactChoice total = chooseFact(facts, totalTags, List.of("USD"), end, kind, true);
        if (total.value() != null) {
            return total;
        }
        FactChoice current = chooseFact(facts, currentTags, List.of("USD"), end, kind, true);
        FactChoice noncurrent = chooseFact(facts, noncurrentTags, List.of("USD"), end, kind, true);
        return combineFacts(synthesisWarning, current, noncurrent);
    }

    private static FactChoice chooseCash(Map<String, Object> facts, LocalDate end, PeriodKind kind) {
        FactChoice combinedCashAndCurrentInvestments = chooseFact(facts, CASH_TAGS, List.of("USD"), end, kind, true);
        FactChoice noncurrentMarketableSecurities = chooseFact(
                facts,
                NONCURRENT_MARKETABLE_SECURITY_TAGS,
                List.of("USD"),
                end,
                kind,
                true);
        if (combinedCashAndCurrentInvestments.value() != null && noncurrentMarketableSecurities.value() != null) {
            List<String> warnings = new ArrayList<>(warnings(
                    combinedCashAndCurrentInvestments,
                    noncurrentMarketableSecurities));
            warnings.add("SEC cash and marketable securities included noncurrent marketable securities because Damodaran-style cash is a total cash/securities bridge.");
            return new FactChoice(
                    combinedCashAndCurrentInvestments.value() + noncurrentMarketableSecurities.value(),
                    latestDate(
                            combinedCashAndCurrentInvestments.sourceDate(),
                            noncurrentMarketableSecurities.sourceDate()),
                    warnings,
                    null);
        }
        if (combinedCashAndCurrentInvestments.value() != null) {
            return combinedCashAndCurrentInvestments;
        }
        FactChoice cashOnly = chooseFact(facts, CASH_ONLY_TAGS, List.of("USD"), end, kind, true);
        FactChoice currentInvestments = chooseFact(facts, SHORT_INVESTMENT_TAGS, List.of("USD"), end, kind, true);
        return combineFacts(
                "SEC cash and marketable securities used cash plus current and noncurrent marketable security tags because the combined cash/securities tag was unavailable.",
                cashOnly,
                currentInvestments,
                noncurrentMarketableSecurities);
    }

    private static FactChoice chooseSharesOutstanding(
            Map<String, Object> usGaapFacts,
            Map<String, Object> deiFacts,
            LocalDate end,
            PeriodKind kind) {
        FactChoice deiShares = chooseFact(deiFacts, SHARES_OUTSTANDING_TAGS, List.of("shares"), end, kind, true);
        if (deiShares.value() != null) {
            return deiShares;
        }
        FactChoice usGaapShares = chooseFact(usGaapFacts, SHARES_OUTSTANDING_TAGS, List.of("shares"), end, kind, true);
        if (usGaapShares.value() != null) {
            return usGaapShares;
        }
        FactChoice basicAverageShares = chooseFact(usGaapFacts, BASIC_SHARES_TAGS, List.of("shares"), end, kind, false);
        if (basicAverageShares.value() == null) {
            return FactChoice.empty();
        }
        List<String> warnings = new ArrayList<>(basicAverageShares.warnings());
        warnings.add("SEC shares outstanding used basic average shares because point-in-time shares were unavailable.");
        return new FactChoice(
                basicAverageShares.value(),
                basicAverageShares.sourceDate(),
                warnings,
                basicAverageShares.tag());
    }

    private static FactChoice chooseInterestExpense(Map<String, Object> facts, LocalDate end, PeriodKind kind) {
        FactChoice directInterestExpense = chooseFact(facts, INTEREST_EXPENSE_TAGS, List.of("USD"), end, kind, false);
        if (directInterestExpense.value() != null) {
            return directInterestExpense;
        }
        FactChoice interestIncome = chooseFact(facts, INTEREST_INCOME_TAGS, List.of("USD"), end, kind, false);
        FactChoice netInterestIncomeExpense = chooseFact(
                facts,
                NET_INTEREST_INCOME_EXPENSE_TAGS,
                List.of("USD"),
                end,
                kind,
                false);
        Double synthesized = null;
        if (interestIncome.value() != null && netInterestIncomeExpense.value() != null) {
            synthesized = interestIncome.value() - netInterestIncomeExpense.value();
        } else if (netInterestIncomeExpense.value() != null && netInterestIncomeExpense.value() < 0.0) {
            synthesized = -netInterestIncomeExpense.value();
        }
        if (synthesized == null || synthesized < 0.0) {
            return FactChoice.empty();
        }
        List<String> warnings = new ArrayList<>(warnings(interestIncome, netInterestIncomeExpense));
        warnings.add("SEC interest expense synthesized from interest income and net nonoperating interest because a direct interest expense tag was unavailable.");
        return new FactChoice(
                synthesized,
                latestDate(interestIncome.sourceDate(), netInterestIncomeExpense.sourceDate()),
                warnings,
                null);
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
                return new FactChoice(fact.get().value(), fact.get().filed(), warnings, tag);
            }
        }
        return FactChoice.empty();
    }

    private static void synthesizeFourthQuarterIncomeSnapshots(
            Map<String, Object> facts,
            Map<String, IncomeStatementSnapshot> snapshots) {
        List<SecFact> annualAnchors = factsForTags(facts, REVENUE_TAGS, List.of("USD")).stream()
                .filter(fact -> matchesPeriod(fact, PeriodKind.ANNUAL, false))
                .sorted(SecFact.BY_END_DESC)
                .toList();
        for (SecFact annualAnchor : uniquePeriods(annualAnchors, 4)) {
            String key = epochMillis(annualAnchor.end());
            if (snapshots.containsKey(key)) {
                continue;
            }
            FactChoice revenue = chooseAnnualLessQ3YtdFact(facts, REVENUE_TAGS, List.of("USD"), annualAnchor.end());
            FactChoice operatingIncome = chooseAnnualLessQ3YtdFact(
                    facts,
                    OPERATING_INCOME_TAGS,
                    List.of("USD"),
                    annualAnchor.end());
            if (revenue.value() == null || operatingIncome.value() == null) {
                continue;
            }
            FactChoice interestExpense = chooseAnnualLessQ3YtdInterestExpense(facts, annualAnchor.end());
            FactChoice taxProvision = chooseAnnualLessQ3YtdFact(
                    facts,
                    TAX_PROVISION_TAGS,
                    List.of("USD"),
                    annualAnchor.end());
            FactChoice pretaxIncome = chooseAnnualLessQ3YtdFact(
                    facts,
                    PRETAX_INCOME_TAGS,
                    List.of("USD"),
                    annualAnchor.end());
            FactChoice researchDevelopment = chooseAnnualLessQ3YtdFact(
                    facts,
                    RD_TAGS,
                    List.of("USD"),
                    annualAnchor.end());
            List<String> warnings = new ArrayList<>(warnings(
                    revenue,
                    operatingIncome,
                    interestExpense,
                    taxProvision,
                    pretaxIncome,
                    researchDevelopment));
            warnings.add("SEC companyfacts synthesized fourth-quarter duration values from annual FY less Q3 year-to-date facts because standalone Q4 facts were unavailable.");
            SourceProvenance provenance = provenance(
                    sourceDate(annualAnchor, revenue, operatingIncome, interestExpense, taxProvision, pretaxIncome),
                    annualAnchor.end(),
                    warnings);
            snapshots.put(key, new IncomeStatementSnapshot(
                    revenue.value(),
                    operatingIncome.value(),
                    null,
                    interestExpense.value(),
                    taxProvision.value(),
                    pretaxIncome.value(),
                    researchDevelopment.value(),
                    null,
                    null,
                    provenance));
        }
    }

    private static void synthesizeFourthQuarterCashFlowSnapshots(
            Map<String, Object> facts,
            Map<String, CashFlowSnapshot> snapshots) {
        List<SecFact> annualAnchors = factsForTags(facts, SBC_TAGS, List.of("USD")).stream()
                .filter(fact -> matchesPeriod(fact, PeriodKind.ANNUAL, false))
                .sorted(SecFact.BY_END_DESC)
                .toList();
        for (SecFact annualAnchor : uniquePeriods(annualAnchors, 4)) {
            String key = epochMillis(annualAnchor.end());
            if (snapshots.containsKey(key)) {
                continue;
            }
            FactChoice stockBasedCompensation = chooseAnnualLessQ3YtdFact(
                    facts,
                    SBC_TAGS,
                    List.of("USD"),
                    annualAnchor.end());
            if (stockBasedCompensation.value() == null) {
                continue;
            }
            List<String> warnings = new ArrayList<>(warnings(stockBasedCompensation));
            warnings.add("SEC companyfacts synthesized fourth-quarter stock-based compensation from annual FY less Q3 year-to-date facts because standalone Q4 facts were unavailable.");
            SourceProvenance provenance = provenance(
                    stockBasedCompensation.sourceDate(),
                    annualAnchor.end(),
                    warnings);
            snapshots.put(key, new CashFlowSnapshot(stockBasedCompensation.value(), provenance));
        }
    }

    private static FactChoice chooseAnnualLessQ3YtdFact(
            Map<String, Object> facts,
            List<String> tags,
            List<String> units,
            LocalDate annualEnd) {
        for (int i = 0; i < tags.size(); i++) {
            String tag = tags.get(i);
            List<SecFact> tagFacts = factsForTag(facts, tag, units);
            Optional<SecFact> annual = tagFacts.stream()
                    .filter(candidate -> Objects.equals(candidate.end(), annualEnd))
                    .filter(candidate -> matchesPeriod(candidate, PeriodKind.ANNUAL, false))
                    .max(SecFact.BY_FILED_ASC);
            if (annual.isEmpty()) {
                continue;
            }
            Optional<SecFact> q3Ytd = tagFacts.stream()
                    .filter(candidate -> candidate.start() != null && annual.get().start() != null)
                    .filter(candidate -> Objects.equals(candidate.start(), annual.get().start()))
                    .filter(candidate -> candidate.end() != null && candidate.end().isBefore(annualEnd))
                    .filter(SecCompanyFactsMapper::isQ3YearToDate)
                    .max(Comparator.comparing(SecFact::end, Comparator.nullsLast(Comparator.naturalOrder()))
                            .thenComparing(SecFact::filed, Comparator.nullsLast(Comparator.naturalOrder())));
            if (q3Ytd.isEmpty()) {
                continue;
            }
            List<String> warnings = i == 0
                    ? List.of()
                    : List.of("SEC companyfacts used fallback tag us-gaap:" + tag + ".");
            return new FactChoice(
                    annual.get().value() - q3Ytd.get().value(),
                    latestDate(annual.get().filed(), q3Ytd.get().filed()),
                    warnings,
                    tag);
        }
        return FactChoice.empty();
    }

    private static FactChoice chooseAnnualLessQ3YtdInterestExpense(
            Map<String, Object> facts,
            LocalDate annualEnd) {
        FactChoice directInterestExpense = chooseAnnualLessQ3YtdFact(
                facts,
                INTEREST_EXPENSE_TAGS,
                List.of("USD"),
                annualEnd);
        if (directInterestExpense.value() != null) {
            return directInterestExpense;
        }
        FactChoice interestIncome = chooseAnnualLessQ3YtdFact(
                facts,
                INTEREST_INCOME_TAGS,
                List.of("USD"),
                annualEnd);
        FactChoice netInterestIncomeExpense = chooseAnnualLessQ3YtdFact(
                facts,
                NET_INTEREST_INCOME_EXPENSE_TAGS,
                List.of("USD"),
                annualEnd);
        Double synthesized = null;
        if (interestIncome.value() != null && netInterestIncomeExpense.value() != null) {
            synthesized = interestIncome.value() - netInterestIncomeExpense.value();
        } else if (netInterestIncomeExpense.value() != null && netInterestIncomeExpense.value() < 0.0) {
            synthesized = -netInterestIncomeExpense.value();
        }
        if (synthesized == null || synthesized < 0.0) {
            return FactChoice.empty();
        }
        List<String> warnings = new ArrayList<>(warnings(interestIncome, netInterestIncomeExpense));
        warnings.add("SEC interest expense synthesized from interest income and net nonoperating interest because a direct interest expense tag was unavailable.");
        return new FactChoice(
                synthesized,
                latestDate(interestIncome.sourceDate(), netInterestIncomeExpense.sourceDate()),
                warnings,
                null);
    }

    private static FactChoice combineFacts(String synthesisWarning, FactChoice... choices) {
        double total = 0.0;
        String sourceDate = null;
        boolean hasValue = false;
        List<String> warnings = new ArrayList<>();
        for (FactChoice choice : choices) {
            if (choice.value() == null) {
                continue;
            }
            hasValue = true;
            total += choice.value();
            sourceDate = latestDate(sourceDate, choice.sourceDate());
            warnings.addAll(choice.warnings());
        }
        if (!hasValue) {
            return FactChoice.empty();
        }
        warnings.add(synthesisWarning);
        return new FactChoice(total, sourceDate, warnings.stream().distinct().toList(), null);
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

    private static boolean isQ3YearToDate(SecFact fact) {
        String form = fact.form().toUpperCase(Locale.ROOT);
        String fp = fact.fp().toUpperCase(Locale.ROOT);
        return "10-Q".equals(form)
                && "Q3".equals(fp)
                && durationDays(fact) >= 240
                && durationDays(fact) <= 300;
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

    private static <T> Map<String, T> latestPeriods(Map<String, T> snapshots, int limit) {
        List<Map.Entry<String, T>> entries = snapshots.entrySet().stream()
                .sorted(Map.Entry.<String, T>comparingByKey().reversed())
                .toList();
        Map<String, T> latest = new LinkedHashMap<>();
        for (Map.Entry<String, T> entry : entries) {
            latest.put(entry.getKey(), entry.getValue());
            if (latest.size() == limit) {
                break;
            }
        }
        return latest;
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

    private static boolean includesFinanceLease(FactChoice... choices) {
        for (FactChoice choice : choices) {
            if (choice.tag() != null && choice.tag().toLowerCase(Locale.ROOT).contains("financelease")) {
                return true;
            }
        }
        return false;
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

    private record FactChoice(Double value, String sourceDate, List<String> warnings, String tag) {
        static FactChoice empty() {
            return new FactChoice(null, null, List.of(), null);
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
