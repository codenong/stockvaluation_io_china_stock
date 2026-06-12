package io.stockvaluation.controller;

import io.stockvaluation.dto.SegmentMappingProposalRequest;
import io.stockvaluation.service.SegmentMappingProposalService;
import io.stockvaluation.utils.ResponseGenerator;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/segments")
public class SegmentMappingController {

    private final SegmentMappingProposalService proposalService;

    @PostMapping("/propose-mappings")
    public ResponseEntity<?> proposeMappings(@RequestBody SegmentMappingProposalRequest request) {
        if (request == null || request.segments() == null || request.segments().isEmpty()) {
            return ResponseGenerator.generateBadRequestResponse("segments must be a non-empty list.");
        }
        List<SegmentMappingProposalService.SegmentMappingInput> inputs = request.segments().stream()
                .map(row -> new SegmentMappingProposalService.SegmentMappingInput(
                        row.name(),
                        row.revenueAmount(),
                        row.revenueWeight(),
                        row.components(),
                        row.rowRole(),
                        row.tableTitle(),
                        row.warnings()))
                .toList();
        return ResponseGenerator.generateSuccessResponse(
                proposalService.proposeMappings(inputs, request.consolidatedRevenue() == null ? 0.0 : request.consolidatedRevenue()));
    }
}
