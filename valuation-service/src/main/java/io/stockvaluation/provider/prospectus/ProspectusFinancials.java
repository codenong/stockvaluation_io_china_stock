package io.stockvaluation.provider.prospectus;

import lombok.Getter;
import lombok.Setter;

import java.util.ArrayList;
import java.util.List;

@Getter
@Setter
public class ProspectusFinancials {
    private List<ProspectusFact> incomeStatement = new ArrayList<>();
    private List<ProspectusFact> balanceSheet = new ArrayList<>();
    private List<ProspectusFact> cashFlowOrCapex = new ArrayList<>();

    public List<ProspectusFact> allFacts() {
        List<ProspectusFact> facts = new ArrayList<>();
        facts.addAll(incomeStatement == null ? List.of() : incomeStatement);
        facts.addAll(balanceSheet == null ? List.of() : balanceSheet);
        facts.addAll(cashFlowOrCapex == null ? List.of() : cashFlowOrCapex);
        return facts;
    }
}
