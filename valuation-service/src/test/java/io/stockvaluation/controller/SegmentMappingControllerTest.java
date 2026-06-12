package io.stockvaluation.controller;

import io.stockvaluation.dto.ResponseDTO;
import io.stockvaluation.dto.SegmentMappingProposalRequest;
import io.stockvaluation.service.SegmentMappingProposalService;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.anyDouble;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class SegmentMappingControllerTest {

    @Test
    void proposeMappingsCallsDeterministicJavaProposalService() {
        SegmentMappingProposalService proposalService = mock(SegmentMappingProposalService.class);
        SegmentMappingProposalService.SegmentMappingProposalResult result =
                new SegmentMappingProposalService.SegmentMappingProposalResult(List.of(), 0.0, false, List.of());
        when(proposalService.proposeMappings(anyList(), anyDouble())).thenReturn(result);
        SegmentMappingController controller = new SegmentMappingController(proposalService);

        ResponseEntity<?> response = controller.proposeMappings(new SegmentMappingProposalRequest(
                List.of(new SegmentMappingProposalRequest.SegmentRow(
                        "Pharmaceuticals",
                        600.0,
                        null,
                        List.of("Prescription drugs"),
                        "reportable_segment",
                        "Segment note",
                        List.of())),
                1_000.0));

        assertEquals(HttpStatus.OK, response.getStatusCode());
        ResponseDTO<?> body = (ResponseDTO<?>) response.getBody();
        assertNotNull(body);
        assertEquals(result, body.getData());
        verify(proposalService).proposeMappings(anyList(), anyDouble());
    }

    @Test
    void proposeMappingsRejectsEmptyRows() {
        SegmentMappingProposalService proposalService = mock(SegmentMappingProposalService.class);
        SegmentMappingController controller = new SegmentMappingController(proposalService);

        ResponseEntity<?> response = controller.proposeMappings(new SegmentMappingProposalRequest(List.of(), 1_000.0));

        assertEquals(HttpStatus.BAD_REQUEST, response.getStatusCode());
        verifyNoInteractions(proposalService);
    }
}
