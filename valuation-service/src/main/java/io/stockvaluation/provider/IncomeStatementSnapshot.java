package io.stockvaluation.provider;

public record IncomeStatementSnapshot(
        Double totalRevenue,
        Double operatingIncome,
        Double specialIncomeCharges,
        Double interestExpense,
        Double taxProvision,
        Double pretaxIncome,
        Double researchAndDevelopment,
        Double basicAverageShares,
        Double dilutedAverageShares,
        SourceProvenance sourceProvenance) {

    public IncomeStatementSnapshot(
            Double totalRevenue,
            Double operatingIncome,
            Double specialIncomeCharges,
            Double interestExpense,
            Double taxProvision,
            Double pretaxIncome,
            Double researchAndDevelopment) {
        this(totalRevenue, operatingIncome, specialIncomeCharges, interestExpense, taxProvision,
                pretaxIncome, researchAndDevelopment, null, null, null);
    }

    public IncomeStatementSnapshot(
            Double totalRevenue,
            Double operatingIncome,
            Double specialIncomeCharges,
            Double interestExpense,
            Double taxProvision,
            Double pretaxIncome,
            Double researchAndDevelopment,
            SourceProvenance sourceProvenance) {
        this(totalRevenue, operatingIncome, specialIncomeCharges, interestExpense, taxProvision,
                pretaxIncome, researchAndDevelopment, null, null, sourceProvenance);
    }

    public IncomeStatementSnapshot(
            Double totalRevenue,
            Double operatingIncome,
            Double specialIncomeCharges,
            Double interestExpense,
            Double taxProvision,
            Double pretaxIncome,
            Double researchAndDevelopment,
            Double basicAverageShares,
            Double dilutedAverageShares) {
        this(totalRevenue, operatingIncome, specialIncomeCharges, interestExpense, taxProvision,
                pretaxIncome, researchAndDevelopment, basicAverageShares, dilutedAverageShares, null);
    }

    public static IncomeStatementSnapshot empty() {
        return new IncomeStatementSnapshot(null, null, null, null, null, null, null);
    }
}
