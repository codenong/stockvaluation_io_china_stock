package io.stockvaluation.provider;

public record BalanceSheetSnapshot(
        Double bookValueEquity,
        Double totalDebt,
        Double cashAndShortTermInvestments,
        Double sharesOutstanding,
        Double minorityInterest,
        SourceProvenance sourceProvenance) {

    public BalanceSheetSnapshot(
            Double bookValueEquity,
            Double totalDebt,
            Double cashAndShortTermInvestments,
            Double sharesOutstanding,
            Double minorityInterest) {
        this(bookValueEquity, totalDebt, cashAndShortTermInvestments, sharesOutstanding, minorityInterest, null);
    }

    public static BalanceSheetSnapshot empty() {
        return new BalanceSheetSnapshot(null, null, null, null, null);
    }
}
