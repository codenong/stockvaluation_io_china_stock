package io.stockvaluation.provider.sec;

import io.stockvaluation.provider.BalanceSheetSnapshot;
import io.stockvaluation.provider.CashFlowSnapshot;
import io.stockvaluation.provider.IncomeStatementSnapshot;
import io.stockvaluation.provider.SourceProvenance;
import org.junit.jupiter.api.Test;

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
}
