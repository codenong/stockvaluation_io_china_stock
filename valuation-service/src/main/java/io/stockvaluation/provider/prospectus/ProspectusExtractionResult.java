package io.stockvaluation.provider.prospectus;

import io.stockvaluation.dto.SourceQualityGateDTO;

import java.util.Map;

public record ProspectusExtractionResult(
        String status,
        ProspectusFinancialPacket packet,
        SourceQualityGateDTO sourceQualityGate,
        Map<String, Object> driverAnchors) {

    public ProspectusExtractionResult(
            String status,
            ProspectusFinancialPacket packet,
            SourceQualityGateDTO sourceQualityGate) {
        this(status, packet, sourceQualityGate, Map.of());
    }
}
