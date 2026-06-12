package io.stockvaluation.service;

import io.stockvaluation.domain.InputStatDistribution;
import io.stockvaluation.domain.SectorMapping;
import io.stockvaluation.provider.prospectus.ProspectusFinancialPacket;
import io.stockvaluation.provider.prospectus.ProspectusScenario;
import io.stockvaluation.provider.prospectus.ProspectusSegmentFact;
import io.stockvaluation.provider.prospectus.ProspectusSegmentScenario;
import io.stockvaluation.repository.InputStatRepository;
import io.stockvaluation.repository.SectorMappingRepository;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class SegmentEconomicAnchorServiceTest {

    @Test
    void buildsWeightedDamodaranQuantileAnchorsForMappedSegments() {
        SectorMappingRepository sectorMappings = mock(SectorMappingRepository.class);
        InputStatRepository inputStats = mock(InputStatRepository.class);
        when(sectorMappings.findByIndustryName("telecom-services"))
                .thenReturn(mapping("telecom-services", "Telecom. Services"));
        when(sectorMappings.findByIndustryName("aerospace-defense"))
                .thenReturn(mapping("aerospace-defense", "Aerospace/Defense"));
        when(inputStats.findFirstByIndustryGroupOrderByIdAsc("Telecom. Services"))
                .thenReturn(Optional.of(stats(
                        "Telecom. Services",
                        4.0, 8.0, 12.0,
                        1.0, 2.0, 3.0,
                        0.5, 1.0, 1.5)));
        when(inputStats.findFirstByIndustryGroupOrderByIdAsc("Aerospace/Defense"))
                .thenReturn(Optional.of(stats(
                        "Aerospace/Defense",
                        10.0, 20.0, 30.0,
                        -2.0, 6.0, 14.0,
                        0.8, 1.2, 2.0)));

        SegmentEconomicAnchorService service = new SegmentEconomicAnchorService(sectorMappings, inputStats);
        Map<String, Object> anchors = service.anchorsForPacket(packet(
                segment("Connectivity", 0.60, "telecom-services", null),
                segment("Launch", 0.40, "aerospace-defense", null)));

        assertAnchor(anchors, "revenue_growth", 6.4, 12.8, 19.2);
        assertAnchor(anchors, "target_operating_margin", -0.2, 3.6, 7.4);
        assertAnchor(anchors, "sales_to_capital", 0.62, 1.08, 1.70);
        assertTrue(((String) ((Map<?, ?>) anchors.get("sales_to_capital")).get("source"))
                .contains("damodaran_segment_quantiles"));
        assertEquals(
                "filing-based segment mix plus Damodaran industry quantiles",
                ((Map<?, ?>) anchors.get("sales_to_capital")).get("source_note"));
    }

    @Test
    void segmentBreakdownCarriesPerSegmentQuantilesAndRevenueWeights() {
        SectorMappingRepository sectorMappings = mock(SectorMappingRepository.class);
        InputStatRepository inputStats = mock(InputStatRepository.class);
        when(sectorMappings.findByIndustryName("telecom-services"))
                .thenReturn(mapping("telecom-services", "Telecom. Services"));
        when(sectorMappings.findByIndustryName("aerospace-defense"))
                .thenReturn(mapping("aerospace-defense", "Aerospace/Defense"));
        when(inputStats.findFirstByIndustryGroupOrderByIdAsc("Telecom. Services"))
                .thenReturn(Optional.of(stats(
                        "Telecom. Services",
                        4.0, 8.0, 12.0,
                        1.16, 9.76, 20.31,
                        0.5, 1.0, 1.5)));
        when(inputStats.findFirstByIndustryGroupOrderByIdAsc("Aerospace/Defense"))
                .thenReturn(Optional.of(stats(
                        "Aerospace/Defense",
                        10.0, 20.0, 30.0,
                        -4.44, 6.68, 13.39,
                        0.8, 1.2, 2.0)));

        SegmentEconomicAnchorService service = new SegmentEconomicAnchorService(sectorMappings, inputStats);
        Map<String, Object> anchors = service.anchorsForPacket(packet(
                segment("Connectivity", 0.736, "telecom-services", null),
                segment("Space", 0.264, "aerospace-defense", null)));

        Map<String, Object> aerospaceRow = firstBreakdownRow(anchors, "target_operating_margin");
        assertEquals("Space", aerospaceRow.get("segment"));
        assertEquals("Aerospace/Defense", aerospaceRow.get("industry_group"));
        assertEquals(0.264, ((Number) aerospaceRow.get("weight")).doubleValue(), 0.000001);
        assertEquals(-4.44, ((Number) aerospaceRow.get("low")).doubleValue(), 0.001);
        assertEquals(6.68, ((Number) aerospaceRow.get("base")).doubleValue(), 0.001);
        assertEquals(13.39, ((Number) aerospaceRow.get("high")).doubleValue(), 0.001);

        Map<String, Object> growthRow = firstBreakdownRow(anchors, "revenue_growth");
        assertEquals(10.0, ((Number) growthRow.get("low")).doubleValue(), 0.001);
        assertEquals(20.0, ((Number) growthRow.get("base")).doubleValue(), 0.001);
        assertEquals(30.0, ((Number) growthRow.get("high")).doubleValue(), 0.001);
    }

    @Test
    void unmappedMaterialSegmentsAreVisibleInOmittedSegmentsAndWarnings() {
        SectorMappingRepository sectorMappings = mock(SectorMappingRepository.class);
        InputStatRepository inputStats = mock(InputStatRepository.class);
        when(sectorMappings.findByIndustryName("telecom-services"))
                .thenReturn(mapping("telecom-services", "Telecom. Services"));
        when(inputStats.findFirstByIndustryGroupOrderByIdAsc("Telecom. Services"))
                .thenReturn(Optional.of(stats(
                        "Telecom. Services",
                        4.0, 8.0, 12.0,
                        1.0, 2.0, 3.0,
                        0.5, 1.0, 1.5)));

        SegmentEconomicAnchorService service = new SegmentEconomicAnchorService(sectorMappings, inputStats);
        Map<String, Object> anchors = service.anchorsForPacket(packet(
                segment("Connectivity", 0.60, "telecom-services", null),
                segment("AI", 0.40, null, null)));

        Map<String, Object> anchorSet = anchorSet(anchors, "target_operating_margin");
        List<Map<String, Object>> omitted = listOfMaps(anchorSet.get("omitted_segments"));
        assertEquals(1, omitted.size());
        assertEquals("AI", omitted.get(0).get("segment"));
        assertEquals("unmapped_segment", omitted.get(0).get("reason"));
        assertEquals(0.40, ((Number) omitted.get(0).get("weight")).doubleValue(), 0.000001);

        List<String> warnings = stringList(anchorSet.get("warnings"));
        assertTrue(warnings.stream().anyMatch(warning ->
                warning.contains("Material segment AI")
                        && warning.contains("omitted")
                        && warning.contains("incomplete")));
    }

    @Test
    void usesMappedIndustryWhenItIsAlreadyPresentOnSegmentFact() {
        SectorMappingRepository sectorMappings = mock(SectorMappingRepository.class);
        InputStatRepository inputStats = mock(InputStatRepository.class);
        when(inputStats.findFirstByIndustryGroupOrderByIdAsc("Software (Internet)"))
                .thenReturn(Optional.of(stats(
                        "Software (Internet)",
                        1.0, 2.0, 3.0,
                        -5.0, 4.0, 11.0,
                        0.7, 1.6, 3.5)));

        SegmentEconomicAnchorService service = new SegmentEconomicAnchorService(sectorMappings, inputStats);
        Map<String, Object> anchors = service.anchorsForPacket(packet(
                segment("Platform", 1.0, "internet-content-information", "Software (Internet)")));

        assertAnchor(anchors, "target_operating_margin", -5.0, 4.0, 11.0);
        assertAnchor(anchors, "sales_to_capital", 0.7, 1.6, 3.5);
    }

    @Test
    void scenarioSegmentsOverridePacketSegmentsForReviewedAnchorRanges() {
        SectorMappingRepository sectorMappings = mock(SectorMappingRepository.class);
        InputStatRepository inputStats = mock(InputStatRepository.class);
        when(sectorMappings.findByIndustryName("telecom-services"))
                .thenReturn(mapping("telecom-services", "Telecom. Services"));
        when(inputStats.findFirstByIndustryGroupOrderByIdAsc("Telecom. Services"))
                .thenReturn(Optional.of(stats(
                        "Telecom. Services",
                        2.0, 4.0, 6.0,
                        1.0, 2.0, 3.0,
                        0.4, 0.8, 1.2)));
        when(inputStats.findFirstByIndustryGroupOrderByIdAsc("Software (Internet)"))
                .thenReturn(Optional.of(stats(
                        "Software (Internet)",
                        8.0, 16.0, 24.0,
                        5.0, 15.0, 25.0,
                        1.0, 2.0, 3.0)));

        SegmentEconomicAnchorService service = new SegmentEconomicAnchorService(sectorMappings, inputStats);
        ProspectusFinancialPacket packet = packet(segment("Connectivity", 1.0, "telecom-services", null));
        ProspectusScenario scenario = scenario(segmentScenario(
                "Consumer Platform",
                "internet-content-information",
                "Software (Internet)",
                100.0,
                300.0));

        Map<String, Object> anchors = service.anchorsForPacketAndScenario(packet, scenario);

        assertAnchor(anchors, "target_operating_margin", 5.0, 15.0, 25.0);
        assertAnchor(anchors, "sales_to_capital", 1.0, 2.0, 3.0);
        assertEquals("reviewed", firstBreakdownRow(anchors, "target_operating_margin").get("mapping_confidence"));
    }

    @SuppressWarnings("unchecked")
    private static void assertAnchor(
            Map<String, Object> anchors,
            String field,
            double low,
            double base,
            double high) {
        Map<String, Object> anchorSet = (Map<String, Object>) anchors.get(field);
        Map<String, Object> values = (Map<String, Object>) anchorSet.get("anchors");
        assertEquals(low, ((Number) ((Map<String, Object>) values.get("low")).get("value")).doubleValue(), 0.001);
        assertEquals(base, ((Number) ((Map<String, Object>) values.get("base")).get("value")).doubleValue(), 0.001);
        assertEquals(high, ((Number) ((Map<String, Object>) values.get("high")).get("value")).doubleValue(), 0.001);
    }

    private static ProspectusFinancialPacket packet(ProspectusSegmentFact... segments) {
        ProspectusFinancialPacket packet = new ProspectusFinancialPacket();
        packet.setSegments(List.of(segments));
        return packet;
    }

    private static ProspectusSegmentFact segment(
            String name,
            double weight,
            String sectorKey,
            String mappedIndustry) {
        ProspectusSegmentFact fact = new ProspectusSegmentFact();
        fact.setSegmentName(name);
        fact.setRevenueWeight(weight);
        fact.setSectorKey(sectorKey);
        fact.setMappedIndustry(mappedIndustry);
        return fact;
    }

    private static ProspectusScenario scenario(ProspectusSegmentScenario... segments) {
        return new ProspectusScenario(
                "reviewed_segments",
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                List.of(segments));
    }

    private static ProspectusSegmentScenario segmentScenario(
            String name,
            String sectorKey,
            String mappedIndustry,
            Double baseRevenue,
            Double targetRevenue) {
        return new ProspectusSegmentScenario(
                name,
                sectorKey,
                mappedIndustry,
                baseRevenue,
                targetRevenue,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> firstBreakdownRow(Map<String, Object> anchors, String field) {
        List<Map<String, Object>> rows = listOfMaps(anchorSet(anchors, field).get("segment_breakdown"));
        return rows.get(0);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> anchorSet(Map<String, Object> anchors, String field) {
        return (Map<String, Object>) anchors.get(field);
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> listOfMaps(Object value) {
        return (List<Map<String, Object>>) value;
    }

    @SuppressWarnings("unchecked")
    private static List<String> stringList(Object value) {
        return (List<String>) value;
    }

    private static SectorMapping mapping(String yahooIndustryKey, String industryAsPerExcel) {
        SectorMapping mapping = new SectorMapping();
        mapping.setYahooIndustryKey(yahooIndustryKey);
        mapping.setIndustryAsPerExcel(industryAsPerExcel);
        return mapping;
    }

    private static InputStatDistribution stats(
            String industry,
            double growthQ1,
            double growthMedian,
            double growthQ3,
            double marginQ1,
            double marginMedian,
            double marginQ3,
            double salesToCapitalQ1,
            double salesToCapitalMedian,
            double salesToCapitalQ3) {
        InputStatDistribution stats = new InputStatDistribution();
        stats.setIndustryGroup(industry);
        stats.setRevenueGrowthRateFirstQuartile(growthQ1);
        stats.setRevenueGrowthRateMedian(growthMedian);
        stats.setRevenueGrowthRateThirdQuartile(growthQ3);
        stats.setPreTaxOperatingMarginFirstQuartile(marginQ1);
        stats.setPreTaxOperatingMarginMedian(marginMedian);
        stats.setPreTaxOperatingMarginThirdQuartile(marginQ3);
        stats.setSalesToInvestedCapitalFirstQuartile(salesToCapitalQ1);
        stats.setSalesToInvestedCapitalMedian(salesToCapitalMedian);
        stats.setSalesToInvestedCapitalThirdQuartile(salesToCapitalQ3);
        return stats;
    }
}
