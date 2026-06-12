package io.stockvaluation.service;

import io.stockvaluation.domain.SectorMapping;
import io.stockvaluation.provider.SourceProvenance;
import io.stockvaluation.provider.prospectus.ProspectusFinancialPacket;
import io.stockvaluation.provider.prospectus.ProspectusRawCell;
import io.stockvaluation.provider.prospectus.ProspectusRawRow;
import io.stockvaluation.provider.prospectus.ProspectusRawTable;
import io.stockvaluation.provider.prospectus.ProspectusSegmentFact;
import io.stockvaluation.provider.prospectus.ProspectusTestPackets;
import io.stockvaluation.repository.SectorMappingRepository;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class SegmentMappingProposalServiceTest {

    @Test
    void proposesMappingsForSuppliedGenericSegmentRows() {
        SectorMappingRepository repository = repositoryWith(
                mapping(1L, "healthcare", "drug-manufacturers-general", "Drugs (Pharmaceutical)"),
                mapping(2L, "consumer-defensive", "household-personal-products", "Household Products"));
        SegmentMappingProposalService service = new SegmentMappingProposalService(repository);

        SegmentMappingProposalService.SegmentMappingProposalResult result = service.proposeMappings(
                List.of(
                        new SegmentMappingProposalService.SegmentMappingInput(
                                "Pharmaceuticals",
                                600.0,
                                null,
                                List.of("Prescription drugs"),
                                "reportable_segment",
                                "Annual report segment note",
                                List.of()),
                        new SegmentMappingProposalService.SegmentMappingInput(
                                "Consumer Health",
                                400.0,
                                null,
                                List.of("Personal care"),
                                "reportable_segment",
                                "Annual report segment note",
                                List.of())),
                1_000.0);

        assertEquals(100.0, result.revenueCoveragePct(), 0.001);
        assertFalse(result.materialGap());
        assertEquals(2, result.proposals().size());
        assertEquals("drug-manufacturers-general", result.proposals().get(0).sectorKey());
        assertEquals("high", result.proposals().get(0).mappingConfidence());
        assertTrue(result.proposals().get(0).rationale().contains("drug-manufacturers-general"));
        assertEquals("household-personal-products", result.proposals().get(1).sectorKey());
    }

    @Test
    void mapsGenericTwoSegmentCompanyWithoutSpacexAliases() {
        SectorMappingRepository repository = repositoryWith(
                mapping(1L, "healthcare", "drug-manufacturers-general", "Drugs (Pharmaceutical)"),
                mapping(2L, "consumer-defensive", "household-personal-products", "Household Products"));
        ProspectusFinancialPacket packet = packetWithRevenue(
                1_000.0,
                table("Segment revenue",
                        row("Pharmaceuticals", 600.0),
                        row("Consumer Health", 400.0)));

        mapper(repository).applyProposedMappings(packet);

        ProspectusSegmentFact pharmaceuticals = segment(packet, "Pharmaceuticals");
        assertEquals("drug-manufacturers-general", pharmaceuticals.getSectorKey());
        assertEquals("Drugs (Pharmaceutical)", pharmaceuticals.getMappedIndustry());
        assertEquals("high", pharmaceuticals.getMappingConfidence());
        assertTrue(pharmaceuticals.getMappingScore() >= 0.75);
        assertEquals("reportable_segment", pharmaceuticals.getRowRole());
        assertTrue(pharmaceuticals.getRationale().contains("drug-manufacturers-general"));

        ProspectusSegmentFact consumerHealth = segment(packet, "Consumer Health");
        assertEquals("household-personal-products", consumerHealth.getSectorKey());
        assertEquals("high", consumerHealth.getMappingConfidence());
        assertTrue(consumerHealth.getMappingScore() >= 0.75);
    }

    @Test
    void ambiguousPlatformSegmentIsNotHighConfidence() {
        SectorMappingRepository repository = repositoryWith(
                mapping(1L, "technology", "software-infrastructure", "Software (System & Application)"),
                mapping(2L, "communication-services", "internet-content-information", "Information Services"));
        ProspectusFinancialPacket packet = packetWithRevenue(
                1_000.0,
                table("Segment revenue",
                        row("Platform", 700.0),
                        row("Payments", 300.0)));

        mapper(repository).applyProposedMappings(packet);

        ProspectusSegmentFact platform = segment(packet, "Platform");
        assertNotEquals("high", platform.getMappingConfidence());
        assertTrue(platform.getMappingScore() < 0.55);
        assertFalse(platform.getWarnings().isEmpty());
    }

    @Test
    void geographyOnlyTableIsClassifiedAndNotMappedToIndustries() {
        SectorMappingRepository repository = repositoryWith(
                mapping(1L, "consumer-cyclical", "discount-stores", "Retail (General)"));
        ProspectusFinancialPacket packet = packetWithRevenue(
                1_000.0,
                table("Revenue by geography",
                        row("United States", 650.0),
                        row("International", 350.0)));

        mapper(repository).applyProposedMappings(packet);

        assertEquals(2, packet.getSegments().size());
        for (ProspectusSegmentFact segment : packet.getSegments()) {
            assertEquals("geography", segment.getRowRole());
            assertNull(segment.getSectorKey());
            assertNull(segment.getMappedIndustry());
            assertTrue(segment.getWarnings().stream().anyMatch(warning -> warning.contains("geography")));
        }
    }

    @Test
    void productLineSubrowsRollIntoParentAndGrandTotalIsExcluded() {
        SectorMappingRepository repository = repositoryWith(
                mapping(1L, "technology", "software-infrastructure", "Software (System & Application)"),
                mapping(2L, "technology", "information-technology-services", "IT Services"));
        ProspectusFinancialPacket packet = packetWithRevenue(
                1_000.0,
                table("Segment revenue",
                        row("Cloud subscriptions", 250.0),
                        row("Developer tools", 150.0),
                        row("Software infrastructure", 400.0),
                        row("Consulting Services", 600.0),
                        row("Total revenue", 1_000.0)));

        mapper(repository).applyProposedMappings(packet);

        assertEquals(2, packet.getSegments().size());
        ProspectusSegmentFact software = segment(packet, "Software infrastructure");
        assertEquals(List.of("Cloud subscriptions", "Developer tools"), software.getComponents());
        assertEquals("reportable_segment", software.getRowRole());
        assertTrue(packet.getSegments().stream().noneMatch(segment -> "Total revenue".equals(segment.getSegmentName())));
        assertTrue(packet.getSegments().stream().noneMatch(segment -> "Cloud subscriptions".equals(segment.getSegmentName())));
    }

    @Test
    void materialOtherBucketStaysUnmappedForMaterialityBackstop() {
        SectorMappingRepository repository = repositoryWith(
                mapping(1L, "healthcare", "medical-devices", "Healthcare Products"));
        ProspectusFinancialPacket packet = packetWithRevenue(
                1_000.0,
                table("Segment revenue",
                        row("Medical products", 880.0),
                        row("Other", 120.0),
                        row("Total revenue", 1_000.0)));

        mapper(repository).applyProposedMappings(packet);

        ProspectusSegmentFact other = segment(packet, "Other");
        assertEquals("residual", other.getRowRole());
        assertNull(other.getSectorKey());
        assertEquals("unmapped", other.getMappingConfidence());
        assertEquals(0.12, other.getRevenueWeight(), 0.000001);
        assertTrue(other.getWarnings().stream().anyMatch(warning -> warning.contains("residual")));
    }

    @Test
    void partialCoverageStillEmitsProposalsWithCoverageWarning() {
        SectorMappingRepository repository = repositoryWith(
                mapping(1L, "technology", "software-infrastructure", "Software (System & Application)"),
                mapping(2L, "consumer-cyclical", "consumer-electronics", "Electronics (Consumer & Office)"));
        ProspectusFinancialPacket packet = packetWithRevenue(
                1_000.0,
                table("Segment revenue",
                        row("Cloud software", 450.0),
                        row("Devices", 300.0)));

        mapper(repository).applyProposedMappings(packet);

        assertEquals(2, packet.getSegments().size());
        assertEquals(0.75, packet.getSegments().stream().mapToDouble(ProspectusSegmentFact::getRevenueWeight).sum(), 0.000001);
        assertTrue(packet.getSegments().stream()
                .flatMap(segment -> segment.getWarnings().stream())
                .anyMatch(warning -> warning.contains("75.00%")));
    }

    @Test
    void duplicateRowsAreFlaggedAndDoNotInflateRevenue() {
        SectorMappingRepository repository = repositoryWith(
                mapping(1L, "technology", "software-infrastructure", "Software (System & Application)"),
                mapping(2L, "consumer-cyclical", "consumer-electronics", "Electronics (Consumer & Office)"));
        ProspectusFinancialPacket packet = packetWithRevenue(
                1_000.0,
                table("Segment revenue",
                        row("Cloud software", 600.0),
                        row("Cloud software", 600.0),
                        row("Devices", 400.0)));

        mapper(repository).applyProposedMappings(packet);

        assertEquals(2, packet.getSegments().size());
        assertEquals(1.0, packet.getSegments().stream().mapToDouble(ProspectusSegmentFact::getRevenueWeight).sum(), 0.000001);
        ProspectusSegmentFact cloud = segment(packet, "Cloud software");
        assertTrue(cloud.getWarnings().stream().anyMatch(warning -> warning.contains("duplicate segment row ignored")));
    }

    @Test
    void repositoryFailureCreatesExplicitWarningsInsteadOfSilentLowConfidence() {
        SectorMappingRepository repository = mock(SectorMappingRepository.class);
        when(repository.findUsableForSegmentValuation()).thenThrow(new IllegalStateException("database unavailable"));
        ProspectusFinancialPacket packet = packetWithRevenue(
                1_000.0,
                table("Segment revenue",
                        row("Cloud software", 600.0),
                        row("Devices", 400.0)));

        mapper(repository).applyProposedMappings(packet);

        assertEquals(2, packet.getSegments().size());
        assertTrue(packet.getSegments().stream().allMatch(segment -> segment.getSectorKey() == null));
        assertTrue(packet.getSegments().stream()
                .flatMap(segment -> segment.getWarnings().stream())
                .anyMatch(warning -> warning.contains("sector mapping lookup failed")));
        assertTrue(packet.getExtractionIssues().stream()
                .anyMatch(issue -> "segment_mapping_repository_failure".equals(issue.code())));
    }

    @Test
    void consumerBankingDoesNotMapToTelecomServices() {
        SectorMappingRepository repository = repositoryWith(
                mapping(1L, "communication-services", "telecom-services", "Telecom. Services"),
                mapping(2L, "financial-services", "banks-diversified", "Bank (Money Center)"));
        ProspectusFinancialPacket packet = packetWithRevenue(
                1_000.0,
                table("Segment revenue",
                        row("Consumer Banking", 700.0),
                        row("Wealth Management", 300.0)));

        mapper(repository).applyProposedMappings(packet);

        ProspectusSegmentFact consumerBanking = segment(packet, "Consumer Banking");
        assertNotEquals("telecom-services", consumerBanking.getSectorKey());
    }

    private static ProspectusSegmentAutoMapper mapper(SectorMappingRepository repository) {
        return new ProspectusSegmentAutoMapper(new SegmentMappingProposalService(repository));
    }

    private static SectorMappingRepository repositoryWith(SectorMapping... mappings) {
        SectorMappingRepository repository = mock(SectorMappingRepository.class);
        when(repository.findUsableForSegmentValuation()).thenReturn(List.of(mappings));
        return repository;
    }

    private static ProspectusFinancialPacket packetWithRevenue(double revenue, ProspectusRawTable table) {
        SourceProvenance provenance = SourceProvenance.primaryFiling(
                "sec-edgar-prospectus",
                "2026-06-12",
                "2025-12-31");
        ProspectusFinancialPacket packet = new ProspectusFinancialPacket();
        packet.setSourceProvenance(provenance);
        packet.getFinancials().setIncomeStatement(List.of(ProspectusTestPackets.fact(
                "revenue",
                "Revenue",
                "Year Ended December 31, 2025",
                revenue,
                "actual",
                provenance)));
        packet.setSegmentCandidateTables(List.of(table));
        return packet;
    }

    private static ProspectusSegmentFact segment(ProspectusFinancialPacket packet, String name) {
        return packet.getSegments().stream()
                .filter(segment -> name.equals(segment.getSegmentName()))
                .findFirst()
                .orElseThrow();
    }

    private static SectorMapping mapping(Long id, String sector, String key, String industry) {
        return new SectorMapping(id, sector, key, industry);
    }

    private static ProspectusRawTable table(String title, Row... rows) {
        return new ProspectusRawTable(
                title,
                "USD",
                "actual",
                List.of("Year Ended December 31, 2025"),
                List.of(rows).stream()
                        .map(row -> new ProspectusRawRow(
                                row.label(),
                                List.of(new ProspectusRawCell(Double.toString(row.amount()), row.amount()))))
                        .toList(),
                "table-segments");
    }

    private static Row row(String label, double amount) {
        return new Row(label, amount);
    }

    private record Row(String label, double amount) {
    }
}
