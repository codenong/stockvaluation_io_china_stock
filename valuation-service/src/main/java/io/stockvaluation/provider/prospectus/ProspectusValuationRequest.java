package io.stockvaluation.provider.prospectus;

public record ProspectusValuationRequest(ProspectusFinancialPacket packet, ProspectusScenario scenario) {
    public ProspectusValuationRequest(ProspectusFinancialPacket packet) {
        this(packet, null);
    }
}
