package io.stockvaluation.service;

import io.stockvaluation.provider.prospectus.ProspectusFinancialPacket;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class ProspectusSegmentAutoMapper {

    private final SegmentMappingProposalService proposalService;

    public void applyProposedMappings(ProspectusFinancialPacket packet) {
        proposalService.applyProposedMappings(packet);
    }
}
