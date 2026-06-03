package io.stockvaluation.provider.field;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class FinancialFieldDefinitionCatalogTest {

    @Test
    void loadsCanonicalDefinitionsForMinimumValuationFields() {
        FinancialFieldDefinitionCatalog catalog = FinancialFieldDefinitionCatalog.loadDefault();

        assertTrue(catalog.hasField("revenue"));
        assertTrue(catalog.hasField("operating_income"));
        assertTrue(catalog.hasField("interest_expense"));
        assertTrue(catalog.hasField("tax_provision"));
        assertTrue(catalog.hasField("pretax_income"));
        assertTrue(catalog.hasField("research_and_development"));
        assertTrue(catalog.hasField("basic_shares"));
        assertTrue(catalog.hasField("diluted_shares"));
        assertTrue(catalog.hasField("shares_outstanding"));
        assertTrue(catalog.hasField("book_equity"));
        assertTrue(catalog.hasField("total_debt"));
        assertTrue(catalog.hasField("cash_and_short_term_investments"));
        assertTrue(catalog.hasField("minority_interest"));
        assertTrue(catalog.hasField("stock_based_compensation"));
    }

    @Test
    void everyDefinitionCarriesMappingPolicyAndWarningMetadata() {
        FinancialFieldDefinitionCatalog catalog = FinancialFieldDefinitionCatalog.loadDefault();

        for (FinancialFieldDefinition definition : catalog.definitions()) {
            assertNotNull(definition.fieldName(), definition.fieldName());
            assertFalse(definition.humanLabel().isBlank(), definition.fieldName());
            assertFalse(definition.valuationUse().isBlank(), definition.fieldName());
            assertFalse(definition.statementFamily().isBlank(), definition.fieldName());
            assertFalse(definition.basis().isBlank(), definition.fieldName());
            assertFalse(definition.periodExpectations().isBlank(), definition.fieldName());
            assertFalse(definition.unitExpectations().isBlank(), definition.fieldName());
            assertFalse(definition.secPreferredConcepts().isEmpty(), definition.fieldName());
            assertFalse(definition.yahooAcceptedKeys().isEmpty(), definition.fieldName());
            assertFalse(definition.adjustmentRisksByProvider().isEmpty(), definition.fieldName());
            assertFalse(definition.knownProviderDifferences().isBlank(), definition.fieldName());
            assertFalse(definition.fallbackBehaviorWhenMissing().isBlank(), definition.fieldName());
            assertTrue(definition.reconciliationThreshold().relativeDifference() > 0.0, definition.fieldName());
            assertFalse(definition.warningRules().isEmpty(), definition.fieldName());
            assertTrue(definition.auditProvenanceRequired(), definition.fieldName());
        }
    }

    @Test
    void catalogExposesFieldSpecificReconciliationThresholds() {
        FinancialFieldDefinitionCatalog catalog = FinancialFieldDefinitionCatalog.loadDefault();

        assertThreshold(catalog, "revenue", 0.05);
        assertThreshold(catalog, "operating_income", 0.05);
        assertThreshold(catalog, "total_debt", 0.05);
        assertThreshold(catalog, "shares_outstanding", 0.02);
        assertThreshold(catalog, "research_and_development", 0.10);
        assertThreshold(catalog, "stock_based_compensation", 0.10);
        assertTrue(catalog.definition("operating_income").warningRules().contains("sign_mismatch"));
        assertTrue(catalog.definition("tax_provision").warningRules().contains("sign_mismatch"));
        assertTrue(catalog.definition("pretax_income").warningRules().contains("sign_mismatch"));
    }

    @Test
    void canonicalDefinitionsCoverAllMapperConceptsAndKeys() {
        FinancialFieldDefinitionCatalog catalog = FinancialFieldDefinitionCatalog.loadDefault();

        assertTrue(catalog.secConcepts("revenue").contains("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"));
        assertTrue(catalog.secConcepts("total_debt").contains("us-gaap:DebtCurrentAndNoncurrent"));
        assertTrue(catalog.secConcepts("cash_and_short_term_investments").contains("us-gaap:CashCashEquivalentsAndShortTermInvestments"));
        assertTrue(catalog.secConcepts("shares_outstanding").contains("us-gaap:CommonStockSharesOutstanding"));
        assertTrue(catalog.yahooKeys("revenue").contains("totalRevenue"));
        assertTrue(catalog.yahooKeys("operating_income").contains("operatingIncome"));
        assertTrue(catalog.yahooKeys("total_debt").contains("TotalDebt"));
        assertTrue(catalog.yahooKeys("stock_based_compensation").contains("StockBasedCompensation"));
    }

    private static void assertThreshold(
            FinancialFieldDefinitionCatalog catalog,
            String fieldName,
            double expected) {
        assertTrue(Math.abs(catalog.definition(fieldName).reconciliationThreshold().relativeDifference() - expected) < 0.0001);
    }
}
