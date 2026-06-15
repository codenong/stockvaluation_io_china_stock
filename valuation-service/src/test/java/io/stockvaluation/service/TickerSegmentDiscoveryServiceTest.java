package io.stockvaluation.service;

import io.stockvaluation.dto.CompanyDataDTO;
import io.stockvaluation.dto.FinancialDataDTO;
import io.stockvaluation.dto.SegmentResponseDTO;
import io.stockvaluation.provider.prospectus.ProspectusDocument;
import io.stockvaluation.provider.prospectus.ProspectusDocumentClient;
import io.stockvaluation.provider.prospectus.ProspectusRawCell;
import io.stockvaluation.provider.prospectus.ProspectusRawRow;
import io.stockvaluation.provider.prospectus.ProspectusRawTable;
import io.stockvaluation.provider.prospectus.ProspectusRawTableSet;
import io.stockvaluation.provider.prospectus.ProspectusTableExtractor;
import io.stockvaluation.provider.sec.SecEdgarHttpClient;
import io.stockvaluation.provider.sec.SecEdgarProviderProperties;
import io.stockvaluation.provider.sec.SecTickerCikResolver;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyDouble;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TickerSegmentDiscoveryServiceTest {

    @Mock
    private SecTickerCikResolver cikResolver;
    @Mock
    private SecEdgarHttpClient secClient;
    @Mock
    private ProspectusDocumentClient documentClient;
    @Mock
    private ProspectusTableExtractor tableExtractor;
    @Mock
    private SegmentMappingProposalService proposalService;

    private SecEdgarProviderProperties secProperties;
    private TickerSegmentDiscoveryService service;

    @BeforeEach
    void setUp() {
        secProperties = new SecEdgarProviderProperties();
        secProperties.setDataBaseUrl("https://data.sec.gov");
        secProperties.setSecBaseUrl("https://www.sec.gov");
        service = new TickerSegmentDiscoveryService(
                cikResolver,
                secClient,
                secProperties,
                documentClient,
                tableExtractor,
                proposalService);
    }

    @Test
    void discoversCuratedMappedSegmentsFromLatestAnnualFilingRevenueTable() {
        when(cikResolver.resolveCik("AMZN")).thenReturn(Optional.of("0001018724"));
        when(secClient.getJson("https://data.sec.gov/submissions/CIK0001018724.json"))
                .thenReturn(submissions("10-K", "2026-02-06", "0001018724-26-000004", "amzn-20251231.htm"));
        String filingUrl = "https://www.sec.gov/Archives/edgar/data/1018724/000101872426000004/amzn-20251231.htm";
        when(documentClient.fetch(filingUrl)).thenReturn(new ProspectusDocument(filingUrl, "<html></html>"));
        when(tableExtractor.extract("<html></html>")).thenReturn(new ProspectusRawTableSet(List.of(
                table(
                        row("North America", 50_000_000_000.0),
                        row("International", 30_000_000_000.0),
                        row("AWS", 20_000_000_000.0),
                        row("Consolidated", 100_000_000_000.0)))));
        when(proposalService.proposeMappings(anyList(), anyDouble()))
                .thenReturn(new SegmentMappingProposalService.SegmentMappingProposalResult(List.of(), 100.0, false, List.of()));

        Optional<SegmentResponseDTO> result = service.discoverSegments("AMZN", companyData(100_000_000_000.0));

        assertTrue(result.isPresent());
        List<SegmentResponseDTO.Segment> segments = result.get().getSegments();
        assertEquals(3, segments.size());
        assertEquals("internet-retail", segments.get(0).getSector());
        assertEquals(0.5, segments.get(0).getRevenueShare(), 0.000001);
        assertEquals("software-infrastructure", segments.get(2).getSector());
        assertEquals(0.2, segments.get(2).getRevenueShare(), 0.000001);
    }

    @Test
    void choosesCurrentRevenueColumnClosestToExpectedRevenue() {
        when(cikResolver.resolveCik("AMZN")).thenReturn(Optional.of("0001018724"));
        when(secClient.getJson("https://data.sec.gov/submissions/CIK0001018724.json"))
                .thenReturn(submissions("10-K", "2026-02-06", "0001018724-26-000004", "amzn-20251231.htm"));
        String filingUrl = "https://www.sec.gov/Archives/edgar/data/1018724/000101872426000004/amzn-20251231.htm";
        when(documentClient.fetch(filingUrl)).thenReturn(new ProspectusDocument(filingUrl, "<html></html>"));
        when(tableExtractor.extract("<html></html>")).thenReturn(new ProspectusRawTableSet(List.of(
                table(
                        row("North America", 387_497_000_000.0, 426_305_000_000.0),
                        row("International", 142_906_000_000.0, 161_894_000_000.0),
                        row("AWS", 107_556_000_000.0, 128_725_000_000.0),
                        row("Consolidated", 637_959_000_000.0, 716_924_000_000.0)))));
        when(proposalService.proposeMappings(anyList(), anyDouble()))
                .thenReturn(new SegmentMappingProposalService.SegmentMappingProposalResult(List.of(), 100.0, false, List.of()));

        Optional<SegmentResponseDTO> result = service.discoverSegments("AMZN", companyData(716_924_000_000.0));

        assertTrue(result.isPresent());
        List<SegmentResponseDTO.Segment> segments = result.get().getSegments();
        assertEquals(0.59463, segments.get(0).getRevenueShare(), 0.00001);
        assertEquals(0.17955, segments.get(2).getRevenueShare(), 0.00001);
    }

    @Test
    void choosesCuratedReportableSegmentRowsWhenSubcategoryRowsAlsoSumToTotal() {
        when(cikResolver.resolveCik("META")).thenReturn(Optional.of("0001326801"));
        when(secClient.getJson("https://data.sec.gov/submissions/CIK0001326801.json"))
                .thenReturn(submissions("10-K", "2026-01-29", "0001628280-26-003942", "meta-20251231.htm"));
        String filingUrl = "https://www.sec.gov/Archives/edgar/data/1326801/000162828026003942/meta-20251231.htm";
        when(documentClient.fetch(filingUrl)).thenReturn(new ProspectusDocument(filingUrl, "<html></html>"));
        when(tableExtractor.extract("<html></html>")).thenReturn(new ProspectusRawTableSet(List.of(
                table(
                        row("Advertising", 196_175_000_000.0),
                        row("Other revenue", 2_584_000_000.0),
                        row("Family of Apps", 198_759_000_000.0),
                        row("Reality Labs", 2_207_000_000.0),
                        row("Total revenue", 200_966_000_000.0)))));
        when(proposalService.proposeMappings(anyList(), anyDouble()))
                .thenReturn(new SegmentMappingProposalService.SegmentMappingProposalResult(List.of(), 100.0, false, List.of()));

        Optional<SegmentResponseDTO> result = service.discoverSegments("META", companyData(200_966_000_000.0));

        assertTrue(result.isPresent());
        List<SegmentResponseDTO.Segment> segments = result.get().getSegments();
        assertEquals(2, segments.size());
        assertEquals("advertising-agencies", segments.get(0).getSector());
        assertEquals(0.98902, segments.get(0).getRevenueShare(), 0.00001);
        assertEquals("consumer-electronics", segments.get(1).getSector());
        assertEquals(0.01098, segments.get(1).getRevenueShare(), 0.00001);
    }

    @Test
    void returnsUnmappedSegmentsWhenMappedCoverageIsInsufficientForValidatorToBlock() {
        when(cikResolver.resolveCik("XYZ")).thenReturn(Optional.of("0000001234"));
        when(secClient.getJson("https://data.sec.gov/submissions/CIK0000001234.json"))
                .thenReturn(submissions("10-K", "2026-02-06", "0000001234-26-000004", "xyz-20251231.htm"));
        String filingUrl = "https://www.sec.gov/Archives/edgar/data/1234/000000123426000004/xyz-20251231.htm";
        when(documentClient.fetch(filingUrl)).thenReturn(new ProspectusDocument(filingUrl, "<html></html>"));
        when(tableExtractor.extract("<html></html>")).thenReturn(new ProspectusRawTableSet(List.of(
                table(
                        row("Segment Alpha", 60_000_000_000.0),
                        row("Segment Beta", 40_000_000_000.0),
                        row("Consolidated", 100_000_000_000.0)))));
        when(proposalService.proposeMappings(anyList(), anyDouble()))
                .thenReturn(new SegmentMappingProposalService.SegmentMappingProposalResult(
                        List.of(
                                proposal("Segment Alpha", 0.6, null, null, "unmapped", 0.0),
                                proposal("Segment Beta", 0.4, null, null, "unmapped", 0.0)),
                        100.0,
                        true,
                        List.of()));

        Optional<SegmentResponseDTO> result = service.discoverSegments("XYZ", companyData(100_000_000_000.0));

        assertTrue(result.isPresent());
        List<SegmentResponseDTO.Segment> segments = result.get().getSegments();
        assertEquals(2, segments.size());
        assertNull(segments.get(0).getSector());
        assertEquals(0.6, segments.get(0).getRevenueShare(), 0.000001);
        assertNull(segments.get(1).getSector());
        assertEquals(0.4, segments.get(1).getRevenueShare(), 0.000001);
    }

    private static Map<String, Object> submissions(String form, String filingDate, String accession, String document) {
        return Map.of(
                "filings",
                Map.of(
                        "recent",
                        Map.of(
                                "form", List.of(form),
                                "filingDate", List.of(filingDate),
                                "accessionNumber", List.of(accession),
                                "primaryDocument", List.of(document))));
    }

    private static CompanyDataDTO companyData(double revenue) {
        FinancialDataDTO financial = new FinancialDataDTO();
        financial.setRevenueLTM(revenue);
        CompanyDataDTO companyData = new CompanyDataDTO();
        companyData.setFinancialDataDTO(financial);
        return companyData;
    }

    private static ProspectusRawTable table(ProspectusRawRow... rows) {
        return new ProspectusRawTable(
                "Untitled prospectus table",
                "USD",
                "actual",
                List.of("Year Ended December 31, 2025"),
                List.of(rows),
                "table-segments");
    }

    private static ProspectusRawRow row(String label, double... values) {
        return new ProspectusRawRow(label, java.util.Arrays.stream(values)
                .mapToObj(value -> new ProspectusRawCell(Double.toString(value), value))
                .toList());
    }

    private static SegmentMappingProposalService.SegmentMappingProposal proposal(
            String name,
            double weight,
            String sectorKey,
            String industry,
            String confidence,
            double score) {
        return new SegmentMappingProposalService.SegmentMappingProposal(
                name,
                weight * 100_000_000_000.0,
                weight,
                sectorKey,
                industry,
                confidence,
                score,
                0.0,
                "test proposal",
                List.of(name),
                "reportable_segment",
                List.of(),
                "Segment revenue");
    }
}
