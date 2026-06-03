package io.stockvaluation.provider.sec;

import io.stockvaluation.provider.BalanceSheetSnapshot;
import io.stockvaluation.provider.CashFlowSnapshot;
import io.stockvaluation.provider.IncomeStatementSnapshot;
import io.stockvaluation.provider.SourceProvenance;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SecCompanyFactsMapperTest {

    @Test
    void mapsCompanyFactsIntoPrimaryFilingSnapshotsWithSourceDatesAndPeriodEnds() {
        SecCompanyFactsMapper mapper = new SecCompanyFactsMapper();

        SecMappedCompanyFacts mapped = mapper.map(
                "MSFT",
                "0000789019",
                SecTestFixtures.json("msft_companyfacts.json"),
                SecTestFixtures.json("msft_submissions.json"));

        assertTrue(mapped.availability().available());
        assertEquals("available", mapped.availability().status());

        IncomeStatementSnapshot income = mapped.yearlyIncome().values().iterator().next();
        SourceProvenance incomeProvenance = income.sourceProvenance();
        assertEquals(281724000000.0, income.totalRevenue());
        assertEquals(128528000000.0, income.operatingIncome());
        assertEquals(1000000000.0, income.interestExpense());
        assertEquals(19651000000.0, income.taxProvision());
        assertEquals(108877000000.0, income.pretaxIncome());
        assertEquals(32747000000.0, income.researchAndDevelopment());
        assertEquals(7420000000.0, income.basicAverageShares());
        assertEquals(7460000000.0, income.dilutedAverageShares());
        assertEquals(SourceProvenance.PRIMARY_FILING, incomeProvenance.getSourceClass());
        assertEquals("sec-edgar-companyfacts", incomeProvenance.getProvider());
        assertEquals("2026-07-30", incomeProvenance.getSourceDate());
        assertEquals("2026-06-30", incomeProvenance.getPeriodEnd());
        assertEquals("primary_filing_used", incomeProvenance.getSourcePolicyStatus());

        BalanceSheetSnapshot balance = mapped.yearlyBalance().values().iterator().next();
        assertEquals(335420000000.0, balance.bookValueEquity());
        assertEquals(67127000000.0, balance.totalDebt());
        assertEquals(95972000000.0, balance.cashAndShortTermInvestments());
        assertEquals(7430000000.0, balance.sharesOutstanding());

        CashFlowSnapshot cashFlow = mapped.yearlyCashFlow().values().iterator().next();
        assertEquals(12000000000.0, cashFlow.stockBasedCompensation());
        assertEquals("2026-07-30", cashFlow.sourceProvenance().getSourceDate());
    }

    @Test
    void selectsRecentComparableQuarterlyPeriodsWhenFramesAreAvailable() {
        SecCompanyFactsMapper mapper = new SecCompanyFactsMapper();

        SecMappedCompanyFacts mapped = mapper.map(
                "MSFT",
                "0000789019",
                SecTestFixtures.json("msft_companyfacts.json"),
                SecTestFixtures.json("msft_submissions.json"));

        assertEquals(4, mapped.quarterlyIncome().size());
        IncomeStatementSnapshot latestQuarter = mapped.quarterlyIncome().values().iterator().next();
        assertEquals(70000000000.0, latestQuarter.totalRevenue());
        assertEquals("2026-03-31", latestQuarter.sourceProvenance().getPeriodEnd());
        assertFalse(mapped.quarterlyBalance().isEmpty());
        BalanceSheetSnapshot latestQuarterBalance = mapped.quarterlyBalance().values().iterator().next();
        assertEquals(335420000000.0, latestQuarterBalance.bookValueEquity());
        assertEquals("2026-06-30", latestQuarterBalance.sourceProvenance().getPeriodEnd());
    }

    @Test
    void mapsDamodaranStyleInputsWhenCompanyFactsOmitsStandaloneFourthQuarter() {
        SecCompanyFactsMapper mapper = new SecCompanyFactsMapper();

        SecMappedCompanyFacts mapped = mapper.map(
                "AMZN",
                "0001018724",
                amznLikeCompanyFacts(),
                submissionsWithUsPeriodicFilings());

        assertTrue(mapped.availability().available());
        assertEquals(4, mapped.quarterlyIncome().size());

        double revenueTtm = mapped.quarterlyIncome().values().stream()
                .map(IncomeStatementSnapshot::totalRevenue)
                .mapToDouble(Double::doubleValue)
                .sum();
        double operatingIncomeTtm = mapped.quarterlyIncome().values().stream()
                .map(IncomeStatementSnapshot::operatingIncome)
                .mapToDouble(Double::doubleValue)
                .sum();
        double interestExpenseTtm = mapped.quarterlyIncome().values().stream()
                .map(IncomeStatementSnapshot::interestExpense)
                .mapToDouble(Double::doubleValue)
                .sum();

        assertEquals(742776.0, revenueTtm);
        assertEquals(85422.0, operatingIncomeTtm);
        assertEquals(2533.0, interestExpenseTtm);
        assertTrue(mapped.quarterlyIncome().values().stream()
                .anyMatch(snapshot -> snapshot.totalRevenue() == 213386.0
                        && snapshot.sourceProvenance().getWarnings().stream()
                                .anyMatch(warning -> warning.contains("synthesized fourth-quarter"))));

        IncomeStatementSnapshot yearlyIncome = mapped.yearlyIncome().values().iterator().next();
        assertEquals(97311.0, yearlyIncome.pretaxIncome());

        BalanceSheetSnapshot latestBalance = mapped.quarterlyBalance().values().iterator().next();
        assertEquals(441914.0, latestBalance.bookValueEquity());
        assertEquals(209888.0, latestBalance.totalDebt());
        assertEquals(143089.0, latestBalance.cashAndShortTermInvestments());
        assertEquals(10754.0, latestBalance.sharesOutstanding());
        assertTrue(latestBalance.sourceProvenance().getWarnings().stream()
                .anyMatch(warning -> warning.contains("recognized lease liabilities are treated as debt")));
        assertTrue(latestBalance.sourceProvenance().getWarnings().stream()
                .anyMatch(warning -> warning.contains("MarketableSecuritiesCurrent")));

        double stockBasedCompensationTtm = mapped.quarterlyCashFlow().values().stream()
                .map(CashFlowSnapshot::stockBasedCompensation)
                .mapToDouble(Double::doubleValue)
                .sum();
        assertEquals(19810.0, stockBasedCompensationTtm);
    }

    @Test
    void mapsDamodaranStyleClaimsAcrossIssuerSpecificPresentations() {
        SecCompanyFactsMapper mapper = new SecCompanyFactsMapper();

        SecMappedCompanyFacts appleLike = mapper.map(
                "AAPL",
                "0000320193",
                appleLikeCompanyFacts(),
                submissionsWithUsPeriodicFilings());
        BalanceSheetSnapshot appleBalance = appleLike.yearlyBalance().values().iterator().next();
        assertEquals(172575.0, appleBalance.cashAndShortTermInvestments());
        assertEquals(108040.0, appleBalance.totalDebt());
        assertTrue(appleBalance.sourceProvenance().getWarnings().stream()
                .anyMatch(warning -> warning.contains("noncurrent marketable security")));
        assertTrue(appleBalance.sourceProvenance().getWarnings().stream()
                .anyMatch(warning -> warning.contains("CommercialPaper")));

        SecMappedCompanyFacts leaseAndAverageShareIssuer = mapper.map(
                "NKE",
                "0000320187",
                leaseAndAverageShareCompanyFacts(),
                submissionsWithUsPeriodicFilings());
        IncomeStatementSnapshot income = leaseAndAverageShareIssuer.yearlyIncome().values().iterator().next();
        assertEquals(269.0, income.interestExpense());
        assertTrue(income.sourceProvenance().getWarnings().stream()
                .anyMatch(warning -> warning.contains("synthesized from interest income")));

        BalanceSheetSnapshot balance = leaseAndAverageShareIssuer.yearlyBalance().values().iterator().next();
        assertEquals(11582.0, balance.cashAndShortTermInvestments());
        assertEquals(11952.0, balance.totalDebt());
        assertEquals(1517.6, balance.sharesOutstanding());
        assertTrue(balance.sourceProvenance().getWarnings().stream()
                .anyMatch(warning -> warning.contains("DebtSecuritiesAvailableForSaleExcludingAccruedInterestCurrent")));
        assertTrue(balance.sourceProvenance().getWarnings().stream()
                .anyMatch(warning -> warning.contains("recognized lease liabilities are treated as debt")));
        assertTrue(balance.sourceProvenance().getWarnings().stream()
                .anyMatch(warning -> warning.contains("basic average shares")));
    }

    @Test
    void recordsWarningWhenFallbackRevenueTaxonomyTagIsUsed() {
        SecCompanyFactsMapper mapper = new SecCompanyFactsMapper();
        Map<String, Object> companyFacts = SecTestFixtures.json("msft_companyfacts.json");
        @SuppressWarnings("unchecked")
        Map<String, Object> facts = (Map<String, Object>) companyFacts.get("facts");
        @SuppressWarnings("unchecked")
        Map<String, Object> usGaap = (Map<String, Object>) facts.get("us-gaap");
        Object preferredRevenueFacts = usGaap.remove("RevenueFromContractWithCustomerExcludingAssessedTax");
        usGaap.put("Revenues", preferredRevenueFacts);

        SecMappedCompanyFacts mapped = mapper.map(
                "MSFT",
                "0000789019",
                companyFacts,
                SecTestFixtures.json("msft_submissions.json"));

        IncomeStatementSnapshot income = mapped.yearlyIncome().values().iterator().next();
        assertEquals(281724000000.0, income.totalRevenue());
        assertTrue(income.sourceProvenance().getWarnings().stream()
                .anyMatch(warning -> warning.contains("fallback tag us-gaap:Revenues")));
    }

    @Test
    void mapsUsGaapCommonStockSharesOutstandingWhenDeiShareConceptIsAbsent() {
        SecCompanyFactsMapper mapper = new SecCompanyFactsMapper();
        Map<String, Object> companyFacts = SecTestFixtures.json("msft_companyfacts.json");
        @SuppressWarnings("unchecked")
        Map<String, Object> facts = (Map<String, Object>) companyFacts.get("facts");
        @SuppressWarnings("unchecked")
        Map<String, Object> dei = (Map<String, Object>) facts.get("dei");
        @SuppressWarnings("unchecked")
        Map<String, Object> usGaap = (Map<String, Object>) facts.get("us-gaap");
        Object shares = dei.remove("EntityCommonStockSharesOutstanding");
        usGaap.put("CommonStockSharesOutstanding", shares);

        SecMappedCompanyFacts mapped = mapper.map(
                "MSFT",
                "0000789019",
                companyFacts,
                SecTestFixtures.json("msft_submissions.json"));

        BalanceSheetSnapshot balance = mapped.yearlyBalance().values().iterator().next();
        assertEquals(7430000000.0, balance.sharesOutstanding());
        assertTrue(balance.sourceProvenance().getWarnings().stream()
                .anyMatch(warning -> warning.contains("fallback tag us-gaap:CommonStockSharesOutstanding")));
    }

    @Test
    void returnsInsufficientFactsWhenRequiredCoreTagsAreMissing() {
        SecCompanyFactsMapper mapper = new SecCompanyFactsMapper();
        Map<String, Object> incomplete = Map.of(
                "facts",
                Map.of("us-gaap", Map.of()));

        SecMappedCompanyFacts mapped = mapper.map(
                "MSFT",
                "0000789019",
                incomplete,
                SecTestFixtures.json("msft_submissions.json"));

        assertFalse(mapped.availability().available());
        assertEquals("insufficient_facts", mapped.availability().status());
        assertTrue(mapped.availability().warnings().stream()
                .anyMatch(warning -> warning.contains("required SEC companyfacts")));
    }

    @Test
    void returnsUnsupportedTaxonomyForIfrsCompanyFactsInsteadOfGenericUnsupportedFiler() {
        SecCompanyFactsMapper mapper = new SecCompanyFactsMapper();
        Map<String, Object> ifrsCompanyFacts = Map.of(
                "facts",
                Map.of("ifrs-full", Map.of("Revenue", Map.of())));
        Map<String, Object> twentyFSubmissions = Map.of(
                "filings",
                Map.of("recent", Map.of(
                        "form", List.of("20-F"),
                        "filingDate", List.of("2026-03-15"))));

        SecMappedCompanyFacts mapped = mapper.map(
                "ASML",
                "0000000000",
                ifrsCompanyFacts,
                twentyFSubmissions);

        assertFalse(mapped.availability().available());
        assertEquals("unsupported_taxonomy", mapped.availability().status());
        assertTrue(mapped.availability().warnings().stream()
                .anyMatch(warning -> warning.contains("ifrs-full")));
    }

    private static Map<String, Object> amznLikeCompanyFacts() {
        Map<String, Object> usGaap = new LinkedHashMap<>();
        usGaap.put("RevenueFromContractWithCustomerExcludingAssessedTax", usd(
                duration(181519.0, "2026-01-01", "2026-03-31", "10-Q", "Q1", "CY2026Q1", "2026-04-30"),
                duration(716924.0, "2025-01-01", "2025-12-31", "10-K", "FY", "CY2025", "2026-02-06"),
                duration(503538.0, "2025-01-01", "2025-09-30", "10-Q", "Q3", null, "2025-10-31"),
                duration(180169.0, "2025-07-01", "2025-09-30", "10-Q", "Q3", "CY2025Q3", "2025-10-31"),
                duration(167702.0, "2025-04-01", "2025-06-30", "10-Q", "Q2", "CY2025Q2", "2025-08-01"),
                duration(155667.0, "2025-01-01", "2025-03-31", "10-Q", "Q1", "CY2025Q1", "2025-05-02")));
        usGaap.put("OperatingIncomeLoss", usd(
                duration(23852.0, "2026-01-01", "2026-03-31", "10-Q", "Q1", "CY2026Q1", "2026-04-30"),
                duration(79975.0, "2025-01-01", "2025-12-31", "10-K", "FY", "CY2025", "2026-02-06"),
                duration(54998.0, "2025-01-01", "2025-09-30", "10-Q", "Q3", null, "2025-10-31"),
                duration(17422.0, "2025-07-01", "2025-09-30", "10-Q", "Q3", "CY2025Q3", "2025-10-31"),
                duration(19171.0, "2025-04-01", "2025-06-30", "10-Q", "Q2", "CY2025Q2", "2025-08-01"),
                duration(18405.0, "2025-01-01", "2025-03-31", "10-Q", "Q1", "CY2025Q1", "2025-05-02")));
        usGaap.put("InterestExpenseNonoperating", usd(
                duration(800.0, "2026-01-01", "2026-03-31", "10-Q", "Q1", "CY2026Q1", "2026-04-30"),
                duration(2274.0, "2025-01-01", "2025-12-31", "10-K", "FY", "CY2025", "2026-02-06"),
                duration(1595.0, "2025-01-01", "2025-09-30", "10-Q", "Q3", null, "2025-10-31"),
                duration(538.0, "2025-07-01", "2025-09-30", "10-Q", "Q3", "CY2025Q3", "2025-10-31"),
                duration(516.0, "2025-04-01", "2025-06-30", "10-Q", "Q2", "CY2025Q2", "2025-08-01"),
                duration(541.0, "2025-01-01", "2025-03-31", "10-Q", "Q1", "CY2025Q1", "2025-05-02")));
        usGaap.put("IncomeTaxExpenseBenefit", usd(
                duration(19087.0, "2025-01-01", "2025-12-31", "10-K", "FY", "CY2025", "2026-02-06")));
        usGaap.put("IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments", usd(
                duration(97311.0, "2025-01-01", "2025-12-31", "10-K", "FY", "CY2025", "2026-02-06")));
        usGaap.put("WeightedAverageNumberOfSharesOutstandingBasic", shares(
                duration(10656.0, "2025-01-01", "2025-12-31", "10-K", "FY", "CY2025", "2026-02-06")));
        usGaap.put("WeightedAverageNumberOfDilutedSharesOutstanding", shares(
                duration(10827.0, "2025-01-01", "2025-12-31", "10-K", "FY", "CY2025", "2026-02-06")));
        usGaap.put("StockholdersEquity", usd(
                instant(441914.0, "2026-03-31", "10-Q", "Q1", "CY2026Q1I", "2026-04-30"),
                instant(411065.0, "2025-12-31", "10-K", "FY", "CY2025Q4I", "2026-02-06")));
        usGaap.put("CashAndCashEquivalentsAtCarryingValue", usd(
                instant(101816.0, "2026-03-31", "10-Q", "Q1", "CY2026Q1I", "2026-04-30"),
                instant(86810.0, "2025-12-31", "10-K", "FY", "CY2025Q4I", "2026-02-06")));
        usGaap.put("MarketableSecuritiesCurrent", usd(
                instant(41273.0, "2026-03-31", "10-Q", "Q1", "CY2026Q1I", "2026-04-30"),
                instant(36219.0, "2025-12-31", "10-K", "FY", "CY2025Q4I", "2026-02-06")));
        usGaap.put("LongTermDebtNoncurrent", usd(
                instant(119074.0, "2026-03-31", "10-Q", "Q1", "CY2026Q1I", "2026-04-30"),
                instant(65648.0, "2025-12-31", "10-K", "FY", "CY2025Q4I", "2026-02-06")));
        usGaap.put("OperatingLeaseLiabilityNoncurrent", usd(
                instant(79067.0, "2026-03-31", "10-Q", "Q1", "CY2026Q1I", "2026-04-30"),
                instant(76597.0, "2025-12-31", "10-K", "FY", "CY2025Q4I", "2026-02-06")));
        usGaap.put("FinanceLeaseLiabilityNoncurrent", usd(
                instant(11747.0, "2026-03-31", "10-Q", "Q1", "CY2026Q1I", "2026-04-30"),
                instant(10742.0, "2025-12-31", "10-K", "FY", "CY2025Q4I", "2026-02-06")));
        usGaap.put("CommonStockSharesOutstanding", shares(
                instant(10754.0, "2026-03-31", "10-Q", "Q1", "CY2026Q1I", "2026-04-30"),
                instant(10731.0, "2025-12-31", "10-K", "FY", "CY2025Q4I", "2026-02-06")));
        usGaap.put("ShareBasedCompensation", usd(
                duration(4032.0, "2026-01-01", "2026-03-31", "10-Q", "Q1", "CY2026Q1", "2026-04-30"),
                duration(19467.0, "2025-01-01", "2025-12-31", "10-K", "FY", "CY2025", "2026-02-06"),
                duration(15070.0, "2025-01-01", "2025-09-30", "10-Q", "Q3", null, "2025-10-31"),
                duration(4847.0, "2025-07-01", "2025-09-30", "10-Q", "Q3", "CY2025Q3", "2025-10-31"),
                duration(6534.0, "2025-04-01", "2025-06-30", "10-Q", "Q2", "CY2025Q2", "2025-08-01"),
                duration(3689.0, "2025-01-01", "2025-03-31", "10-Q", "Q1", "CY2025Q1", "2025-05-02")));

        return Map.of("facts", Map.of("us-gaap", usGaap, "dei", Map.of()));
    }

    private static Map<String, Object> appleLikeCompanyFacts() {
        Map<String, Object> usGaap = new LinkedHashMap<>();
        usGaap.put("RevenueFromContractWithCustomerExcludingAssessedTax", usd(
                duration(385706.0, "2023-01-01", "2023-12-31", "10-K", "FY", "CY2023", "2024-02-02")));
        usGaap.put("OperatingIncomeLoss", usd(
                duration(118658.0, "2023-01-01", "2023-12-31", "10-K", "FY", "CY2023", "2024-02-02")));
        usGaap.put("StockholdersEquity", usd(
                instant(74110.0, "2023-12-31", "10-K", "FY", "CY2023Q4I", "2024-02-02")));
        usGaap.put("CashAndCashEquivalentsAtCarryingValue", usd(
                instant(40760.0, "2023-12-31", "10-K", "FY", "CY2023Q4I", "2024-02-02")));
        usGaap.put("MarketableSecuritiesCurrent", usd(
                instant(32340.0, "2023-12-31", "10-K", "FY", "CY2023Q4I", "2024-02-02")));
        usGaap.put("MarketableSecuritiesNoncurrent", usd(
                instant(99475.0, "2023-12-31", "10-K", "FY", "CY2023Q4I", "2024-02-02")));
        usGaap.put("CommercialPaper", usd(
                instant(1998.0, "2023-12-31", "10-K", "FY", "CY2023Q4I", "2024-02-02")));
        usGaap.put("LongTermDebtCurrent", usd(
                instant(10954.0, "2023-12-31", "10-K", "FY", "CY2023Q4I", "2024-02-02")));
        usGaap.put("LongTermDebtNoncurrent", usd(
                instant(95088.0, "2023-12-31", "10-K", "FY", "CY2023Q4I", "2024-02-02")));
        usGaap.put("CommonStockSharesOutstanding", shares(
                instant(15460.223, "2023-12-31", "10-K", "FY", "CY2023Q4I", "2024-02-02")));
        return Map.of("facts", Map.of("us-gaap", usGaap, "dei", Map.of()));
    }

    private static Map<String, Object> leaseAndAverageShareCompanyFacts() {
        Map<String, Object> usGaap = new LinkedHashMap<>();
        usGaap.put("RevenueFromContractWithCustomerExcludingAssessedTax", usd(
                duration(51362.0, "2023-06-01", "2024-05-31", "10-K", "FY", "CY2023", "2024-07-25")));
        usGaap.put("OperatingIncomeLoss", usd(
                duration(6754.0, "2023-06-01", "2024-05-31", "10-K", "FY", "CY2023", "2024-07-25")));
        usGaap.put("InvestmentIncomeInterest", usd(
                duration(430.0, "2023-06-01", "2024-05-31", "10-K", "FY", "CY2023", "2024-07-25")));
        usGaap.put("InterestIncomeExpenseNonoperatingNet", usd(
                duration(161.0, "2023-06-01", "2024-05-31", "10-K", "FY", "CY2023", "2024-07-25")));
        usGaap.put("WeightedAverageNumberOfSharesOutstandingBasic", shares(
                duration(1517.6, "2023-06-01", "2024-05-31", "10-K", "FY", "CY2023", "2024-07-25")));
        usGaap.put("StockholdersEquity", usd(
                instant(14430.0, "2024-05-31", "10-K", "FY", "CY2024Q2I", "2024-07-25")));
        usGaap.put("CashAndCashEquivalentsAtCarryingValue", usd(
                instant(9860.0, "2024-05-31", "10-K", "FY", "CY2024Q2I", "2024-07-25")));
        usGaap.put("DebtSecuritiesAvailableForSaleExcludingAccruedInterestCurrent", usd(
                instant(1722.0, "2024-05-31", "10-K", "FY", "CY2024Q2I", "2024-07-25")));
        usGaap.put("LongTermDebtCurrent", usd(
                instant(1000.0, "2024-05-31", "10-K", "FY", "CY2024Q2I", "2024-07-25")));
        usGaap.put("ShortTermBorrowings", usd(
                instant(6.0, "2024-05-31", "10-K", "FY", "CY2024Q2I", "2024-07-25")));
        usGaap.put("LongTermDebtNoncurrent", usd(
                instant(7903.0, "2024-05-31", "10-K", "FY", "CY2024Q2I", "2024-07-25")));
        usGaap.put("OperatingLeaseLiability", usd(
                instant(3043.0, "2024-05-31", "10-K", "FY", "CY2024Q2I", "2024-07-25")));
        return Map.of("facts", Map.of("us-gaap", usGaap, "dei", Map.of()));
    }

    private static Map<String, Object> submissionsWithUsPeriodicFilings() {
        return Map.of(
                "filings",
                Map.of("recent", Map.of(
                        "form", List.of("10-Q", "10-K"),
                        "filingDate", List.of("2026-04-30", "2026-02-06"))));
    }

    @SafeVarargs
    private static Map<String, Object> usd(Map<String, Object>... facts) {
        return Map.of("units", Map.of("USD", List.of(facts)));
    }

    @SafeVarargs
    private static Map<String, Object> shares(Map<String, Object>... facts) {
        return Map.of("units", Map.of("shares", List.of(facts)));
    }

    private static Map<String, Object> duration(
            double value,
            String start,
            String end,
            String form,
            String fp,
            String frame,
            String filed) {
        Map<String, Object> fact = instant(value, end, form, fp, frame, filed);
        fact.put("start", start);
        return fact;
    }

    private static Map<String, Object> instant(
            double value,
            String end,
            String form,
            String fp,
            String frame,
            String filed) {
        Map<String, Object> fact = new LinkedHashMap<>();
        fact.put("end", end);
        fact.put("val", value);
        fact.put("form", form);
        fact.put("fp", fp);
        fact.put("filed", filed);
        if (frame != null) {
            fact.put("frame", frame);
        }
        return fact;
    }
}
