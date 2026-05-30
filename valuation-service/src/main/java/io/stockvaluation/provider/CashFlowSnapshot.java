package io.stockvaluation.provider;

public record CashFlowSnapshot(
        Double stockBasedCompensation,
        SourceProvenance sourceProvenance) {

    public static CashFlowSnapshot empty() {
        return new CashFlowSnapshot(null, null);
    }
}
