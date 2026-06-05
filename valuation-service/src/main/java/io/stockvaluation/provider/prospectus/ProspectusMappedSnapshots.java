package io.stockvaluation.provider.prospectus;

import io.stockvaluation.provider.BalanceSheetSnapshot;
import io.stockvaluation.provider.CashFlowSnapshot;
import io.stockvaluation.provider.IncomeStatementSnapshot;

import java.util.Map;

public record ProspectusMappedSnapshots(
        Map<String, IncomeStatementSnapshot> yearlyIncome,
        Map<String, BalanceSheetSnapshot> yearlyBalance,
        Map<String, CashFlowSnapshot> yearlyCashFlow) {
}
