package io.stockvaluation.provider;

import java.util.Map;
import java.util.Collections;

public interface FinancialSnapshotProvider {

    Map<String, IncomeStatementSnapshot> getIncomeStatementSnapshots(String ticker, String freq);

    Map<String, BalanceSheetSnapshot> getBalanceSheetSnapshots(String ticker, String freq);

    default Map<String, CashFlowSnapshot> getCashFlowSnapshots(String ticker, String freq) {
        return Collections.emptyMap();
    }

    String getProviderName();
}
