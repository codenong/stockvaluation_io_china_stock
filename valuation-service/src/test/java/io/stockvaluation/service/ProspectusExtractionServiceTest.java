package io.stockvaluation.service;

import io.stockvaluation.dto.SourceQualityGateDTO;
import io.stockvaluation.provider.prospectus.ProspectusDocument;
import io.stockvaluation.provider.prospectus.ProspectusDocumentClient;
import io.stockvaluation.provider.prospectus.ProspectusExtractionRequest;
import io.stockvaluation.provider.prospectus.ProspectusExtractionResult;
import io.stockvaluation.provider.prospectus.ProspectusFinancialExtractor;
import io.stockvaluation.provider.prospectus.ProspectusTableExtractor;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ProspectusExtractionServiceTest {

    @Test
    void extractionReturnsReviewGateAndCompactPacket() throws Exception {
        String filingUrl = "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm";
        String html = Files.readString(Path.of("src/test/resources/prospectus/spacex_s1a_trimmed.html"));
        ProspectusDocumentClient client = mock(ProspectusDocumentClient.class);
        when(client.fetch(filingUrl)).thenReturn(new ProspectusDocument(filingUrl, html));
        ProspectusExtractionService service = new ProspectusExtractionService(
                client,
                new ProspectusTableExtractor(),
                new ProspectusFinancialExtractor());

        ProspectusExtractionResult result = service.extract(new ProspectusExtractionRequest(filingUrl, "SpaceX", "SPCX"));

        assertEquals("requires_review", result.status());
        assertEquals("review_required", result.packet().getReviewStatus());
        assertFalse(result.packet().getFinancials().getIncomeStatement().isEmpty());
        SourceQualityGateDTO gate = result.sourceQualityGate();
        assertEquals("requires_user_decision", gate.getStatus());
        assertEquals("prospectus_extraction_review_required", gate.getReason());
        assertEquals("approve_extracted_packet", gate.getAllowedActions().get(0));
    }
}
