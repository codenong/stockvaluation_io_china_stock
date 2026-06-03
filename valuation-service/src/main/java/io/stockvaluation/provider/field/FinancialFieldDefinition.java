package io.stockvaluation.provider.field;

import java.util.List;
import java.util.Map;

public record FinancialFieldDefinition(
        String fieldName,
        String humanLabel,
        String valuationUse,
        String statementFamily,
        String basis,
        String periodExpectations,
        String unitExpectations,
        List<String> secPreferredConcepts,
        List<String> yahooAcceptedKeys,
        String commonAdjustmentsIncluded,
        String commonAdjustmentsExcluded,
        Map<String, String> adjustmentRisksByProvider,
        String knownProviderDifferences,
        String fallbackBehaviorWhenMissing,
        ReconciliationThreshold reconciliationThreshold,
        List<String> warningRules,
        boolean auditProvenanceRequired) {

    public record ReconciliationThreshold(
            double relativeDifference,
            String materialityBasis) {
    }
}
