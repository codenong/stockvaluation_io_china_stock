package io.stockvaluation.provider.prospectus;

import com.fasterxml.jackson.annotation.JsonAlias;

import java.util.List;

public record ProspectusSegmentScenario(
        String name,
        @JsonAlias("sector_key") String sectorKey,
        @JsonAlias("mapped_industry") String mappedIndustry,
        @JsonAlias("base_revenue") Double baseRevenue,
        @JsonAlias("target_revenue") Double targetRevenue,
        @JsonAlias("projected_revenues") List<Double> projectedRevenues,
        @JsonAlias("revenue_next_year") Double revenueNextYear,
        @JsonAlias("compound_annual_growth_2_5") Double compoundAnnualGrowth2_5,
        @JsonAlias("terminal_growth_rate") Double terminalGrowthRate,
        @JsonAlias("operating_margin_next_year") Double operatingMarginNextYear,
        @JsonAlias({"target_operating_margin", "target_pre_tax_operating_margin"}) Double targetOperatingMargin,
        @JsonAlias({"margin_convergence_year", "convergence_year_margin"}) Double marginConvergenceYear,
        @JsonAlias("sales_to_capital_years_1_to_5") Double salesToCapitalYears1To5,
        @JsonAlias("sales_to_capital_years_6_to_10") Double salesToCapitalYears6To10,
        @JsonAlias({"initial_cost_of_capital", "wacc"}) Double initialCostOfCapital) {

    public List<Double> projectedRevenuesOrEmpty() {
        return projectedRevenues == null ? List.of() : projectedRevenues;
    }
}
