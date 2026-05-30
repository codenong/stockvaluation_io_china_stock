package io.stockvaluation.provider;

import java.util.Map;

public interface FinancialSnapshotProvider {

    Map<String, IncomeStatementSnapshot> getIncomeStatementSnapshots(String ticker, String freq);

    Map<String, BalanceSheetSnapshot> getBalanceSheetSnapshots(String ticker, String freq);

    String getProviderName();
}
