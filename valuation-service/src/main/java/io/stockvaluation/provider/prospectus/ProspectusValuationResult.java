package io.stockvaluation.provider.prospectus;

import io.stockvaluation.dto.SourceQualityGateDTO;
import io.stockvaluation.dto.ValuationOutputDTO;
import io.stockvaluation.provider.SourceProvenance;

import java.util.List;

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
        ValuationOutputDTO valuation) {
}
