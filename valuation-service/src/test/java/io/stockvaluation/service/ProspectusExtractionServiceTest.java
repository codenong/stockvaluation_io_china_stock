package io.stockvaluation.service;

import io.stockvaluation.dto.SourceQualityGateDTO;
import io.stockvaluation.domain.SectorMapping;
import io.stockvaluation.provider.prospectus.ProspectusDocument;
import io.stockvaluation.provider.prospectus.ProspectusDocumentClient;
import io.stockvaluation.provider.prospectus.ProspectusExtractionRequest;
import io.stockvaluation.provider.prospectus.ProspectusExtractionResult;
import io.stockvaluation.provider.prospectus.ProspectusFinancialExtractor;
import io.stockvaluation.provider.prospectus.ProspectusSegmentFact;
import io.stockvaluation.provider.prospectus.ProspectusTableExtractor;
import io.stockvaluation.repository.SectorMappingRepository;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ProspectusExtractionServiceTest {

    @Test
    void extractionReturnsReviewGateAndCompactPacket() throws Exception {
        String filingUrl = "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm";
        String html = Files.readString(Path.of("src/test/resources/prospectus/spacex_s1a_trimmed.html"));
        ProspectusDocumentClient client = mock(ProspectusDocumentClient.class);
        SectorMappingRepository sectorMappingRepository = mock(SectorMappingRepository.class);
        SegmentEconomicAnchorService economicAnchorService = mock(SegmentEconomicAnchorService.class);
        when(client.fetch(filingUrl)).thenReturn(new ProspectusDocument(filingUrl, html));
        when(sectorMappingRepository.findUsableForSegmentValuation()).thenReturn(List.of(
                new SectorMapping(1L, "industrials", "aerospace-defense", "Aerospace/Defense"),
                new SectorMapping(2L, "communication-services", "telecom-services", "Telecom. Services"),
                new SectorMapping(3L, "technology", "software-infrastructure", "Software (System & Application)"),
                new SectorMapping(4L, "communication-services", "advertising-agencies", "Advertising")));
        when(economicAnchorService.anchorsForPacket(any())).thenReturn(Map.of("sales_to_capital", Map.of("source", "test")));
        ProspectusExtractionService service = new ProspectusExtractionService(
                client,
                new ProspectusTableExtractor(),
                new ProspectusFinancialExtractor(),
                new ProspectusSegmentAutoMapper(new SegmentMappingProposalService(sectorMappingRepository)),
                economicAnchorService);

        ProspectusExtractionResult result = service.extract(new ProspectusExtractionRequest(filingUrl, "SpaceX", "SPCX"));

        assertEquals("requires_review", result.status());
        assertEquals("review_required", result.packet().getReviewStatus());
        assertFalse(result.packet().getFinancials().getIncomeStatement().isEmpty());
        assertEquals(3, result.packet().getSegments().size());
        ProspectusSegmentFact space = result.packet().getSegments().stream()
                .filter(segment -> "Space".equals(segment.getSegmentName()))
                .findFirst()
                .orElseThrow();
        assertEquals("aerospace-defense", space.getSectorKey());
        assertEquals("Aerospace/Defense", space.getMappedIndustry());
        assertEquals("high", space.getMappingConfidence());
        assertEquals(0.218807, space.getRevenueWeight(), 0.000001);
        ProspectusSegmentFact connectivity = result.packet().getSegments().stream()
                .filter(segment -> "Connectivity".equals(segment.getSegmentName()))
                .findFirst()
                .orElseThrow();
        assertEquals("telecom-services", connectivity.getSectorKey());
        assertEquals("Telecom. Services", connectivity.getMappedIndustry());
        assertEquals("high", connectivity.getMappingConfidence());
        ProspectusSegmentFact ai = result.packet().getSegments().stream()
                .filter(segment -> "AI".equals(segment.getSegmentName()))
                .findFirst()
                .orElseThrow();
        assertEquals("software-infrastructure", ai.getSectorKey());
        assertEquals("low", ai.getMappingConfidence());
        assertNotNull(ai.getSourceProvenance());
        SourceQualityGateDTO gate = result.sourceQualityGate();
        assertEquals("requires_user_decision", gate.getStatus());
        assertEquals("prospectus_extraction_review_required", gate.getReason());
        assertEquals("approve_extracted_packet", gate.getAllowedActions().get(0));
        assertEquals("test", ((Map<?, ?>) result.driverAnchors().get("sales_to_capital")).get("source"));
    }
}
