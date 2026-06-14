package io.stockvaluation.controller;

import io.stockvaluation.config.SecurityConfig;
import io.stockvaluation.service.SegmentMappingProposalService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.anyDouble;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(SegmentMappingController.class)
@Import(SecurityConfig.class)
class SegmentMappingControllerSecurityTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private SegmentMappingProposalService proposalService;

    @Test
    void proposeMappingsAllowsAnonymousLocalWorkflowRequest() throws Exception {
        SegmentMappingProposalService.SegmentMappingProposalResult result =
                new SegmentMappingProposalService.SegmentMappingProposalResult(List.of(), 0.0, false, List.of());
        when(proposalService.proposeMappings(anyList(), anyDouble())).thenReturn(result);

        mockMvc.perform(post("/api/v1/segments/propose-mappings")
                        .contentType(MediaType.APPLICATION_JSON)
                        .accept(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "segments": [
                                    {"name": "Google Services", "revenueAmount": 350000000000},
                                    {"name": "Google Cloud", "revenueAmount": 43000000000}
                                  ],
                                  "consolidatedRevenue": 393000000000
                                }
                                """))
                .andExpect(status().isOk());
    }
}
