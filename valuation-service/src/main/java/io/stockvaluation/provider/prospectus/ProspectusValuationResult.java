package io.stockvaluation.provider.prospectus;

import io.stockvaluation.dto.SourceQualityGateDTO;
import io.stockvaluation.dto.ValuationOutputDTO;
import io.stockvaluation.provider.SourceProvenance;

import java.util.List;
import java.util.Map;

public record ProspectusValuationResult(
        String status,
        String priceBasis,
        ProspectusFinancialPacket packet,
        ProspectusScenario scenario,
        SourceProvenance sourceProvenance,
        SourceQualityGateDTO sourceQualityGate,
        String valuationBasisStatus,
        String valuationCaseStatus,
        String proceedsBasis,
        List<String> valuationBasisWarnings,
        ValuationOutputDTO valuation,
        Map<String, Object> driverAnchors) {

    public ProspectusValuationResult(
            String status,
            String priceBasis,
            ProspectusFinancialPacket packet,
            ProspectusScenario scenario,
            SourceProvenance sourceProvenance,
            SourceQualityGateDTO sourceQualityGate,
            String valuationBasisStatus,
            String valuationCaseStatus,
            String proceedsBasis,
            List<String> valuationBasisWarnings,
            ValuationOutputDTO valuation) {
        this(
                status,
                priceBasis,
                packet,
                scenario,
                sourceProvenance,
                sourceQualityGate,
                valuationBasisStatus,
                valuationCaseStatus,
                proceedsBasis,
                valuationBasisWarnings,
                valuation,
                Map.of());
    }
}
