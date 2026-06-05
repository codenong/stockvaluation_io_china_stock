package io.stockvaluation.provider.prospectus;

import io.stockvaluation.dto.SourceQualityGateDTO;

public record ProspectusExtractionResult(
        String status,
        ProspectusFinancialPacket packet,
        SourceQualityGateDTO sourceQualityGate) {
}
