package io.stockvaluation.provider.prospectus;

import com.fasterxml.jackson.annotation.JsonAlias;

import java.util.List;

public record ProspectusScenario(
        @JsonAlias("scenario_name") String scenarioName,
        @JsonAlias("net_proceeds") Double netProceeds,
        @JsonAlias("proceeds_basis") String proceedsBasis,
        @JsonAlias({"rd_capitalization", "capitalize_rd", "capitalizeRD"}) Boolean rdCapitalization,
        @JsonAlias("rd_amortization_method") String rdAmortizationMethod,
        @JsonAlias("rd_amortization_period_years") Integer rdAmortizationPeriodYears,
        @JsonAlias({"initial_cost_of_capital", "wacc"}) Double initialCostOfCapital,
        @JsonAlias("terminal_cost_of_capital") Double terminalCostOfCapital,
        @JsonAlias("terminal_growth_rate") Double terminalGrowthRate,
        @JsonAlias("terminal_return_on_capital") Double terminalReturnOnCapital,
        @JsonAlias("revenue_next_year") Double revenueNextYear,
        @JsonAlias("compound_annual_growth_2_5") Double compoundAnnualGrowth2_5,
        @JsonAlias("operating_margin_next_year") Double operatingMarginNextYear,
        @JsonAlias({"target_operating_margin", "target_pre_tax_operating_margin"}) Double targetOperatingMargin,
        @JsonAlias({"margin_convergence_year", "convergence_year_margin"}) Double marginConvergenceYear,
        @JsonAlias("sales_to_capital_years_1_to_5") Double salesToCapitalYears1To5,
        @JsonAlias("sales_to_capital_years_6_to_10") Double salesToCapitalYears6To10,
        @JsonAlias({"segments", "segment_assumptions"}) List<ProspectusSegmentScenario> segments) {

    public List<ProspectusSegmentScenario> segmentsOrEmpty() {
        return segments == null ? List.of() : segments;
    }
}
