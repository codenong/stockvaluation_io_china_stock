package io.stockvaluation.provider.prospectus;

import io.stockvaluation.dto.SourceQualityGateDTO;
import io.stockvaluation.dto.ValuationOutputDTO;
import io.stockvaluation.provider.SourceProvenance;

public record ProspectusValuationResult(
        String status,
        String priceBasis,
        ProspectusFinancialPacket packet,
        SourceProvenance sourceProvenance,
        SourceQualityGateDTO sourceQualityGate,
        ValuationOutputDTO valuation) {
}
