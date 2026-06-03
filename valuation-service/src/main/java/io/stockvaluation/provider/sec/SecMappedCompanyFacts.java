package io.stockvaluation.provider.sec;

import io.stockvaluation.provider.BalanceSheetSnapshot;
import io.stockvaluation.provider.CashFlowSnapshot;
import io.stockvaluation.provider.IncomeStatementSnapshot;
import io.stockvaluation.provider.PrimaryFilingAvailability;

import java.util.Map;

public record SecMappedCompanyFacts(
        Map<String, IncomeStatementSnapshot> yearlyIncome,
        Map<String, IncomeStatementSnapshot> quarterlyIncome,
        Map<String, BalanceSheetSnapshot> yearlyBalance,
        Map<String, BalanceSheetSnapshot> quarterlyBalance,
        Map<String, CashFlowSnapshot> yearlyCashFlow,
        Map<String, CashFlowSnapshot> quarterlyCashFlow,
        PrimaryFilingAvailability availability) {

    static SecMappedCompanyFacts unavailable(String status, String provider, java.util.List<String> warnings) {
        return new SecMappedCompanyFacts(
                Map.of(),
                Map.of(),
                Map.of(),
                Map.of(),
                Map.of(),
                Map.of(),
                PrimaryFilingAvailability.unavailable(status, provider, warnings));
    }
}
