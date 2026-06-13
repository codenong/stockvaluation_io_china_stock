package io.stockvaluation.service;

import io.stockvaluation.domain.InputStatDistribution;
import io.stockvaluation.domain.SectorMapping;
import io.stockvaluation.provider.prospectus.ProspectusFinancialPacket;
import io.stockvaluation.provider.prospectus.ProspectusFact;
import io.stockvaluation.provider.prospectus.ProspectusScenario;
import io.stockvaluation.provider.prospectus.ProspectusSegmentFact;
import io.stockvaluation.provider.prospectus.ProspectusSegmentScenario;
import io.stockvaluation.repository.InputStatRepository;
import io.stockvaluation.repository.SectorMappingRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class SegmentEconomicAnchorService {

    private static final String SCHEMA_VERSION = "driver_anchors.v1";
    private static final String SOURCE = "damodaran_segment_quantiles";
    private static final String SOURCE_NOTE =
            "filing-based segment mix plus Damodaran industry quantiles";
    private static final double MATERIAL_OMITTED_WEIGHT = 0.10;

    private final SectorMappingRepository sectorMappingRepository;
    private final InputStatRepository inputStatRepository;

    public Map<String, Object> anchorsForPacketAndScenario(
            ProspectusFinancialPacket packet,
            ProspectusScenario scenario) {
        if (scenario == null || scenario.segmentsOrEmpty().isEmpty()) {
            return anchorsForPacket(packet);
        }
        ProspectusFinancialPacket scenarioPacket = new ProspectusFinancialPacket();
        scenarioPacket.setFinancials(packet == null ? null : packet.getFinancials());
        scenarioPacket.setSegments(scenarioSegmentFacts(packet, scenario.segmentsOrEmpty()));
        return anchorsForPacket(scenarioPacket);
    }

    public Map<String, Object> anchorsForPacket(ProspectusFinancialPacket packet) {
        if (packet == null || packet.getSegments() == null || packet.getSegments().isEmpty()) {
            return Map.of();
        }
        double consolidatedRevenue = latestRevenue(packet);
        List<SegmentStats> segmentStats = new ArrayList<>();
        List<Map<String, Object>> omittedSegments = new ArrayList<>();
        for (ProspectusSegmentFact segment : packet.getSegments()) {
            if (segment == null) {
                continue;
            }
            Optional<SegmentStats> stats = segmentStats(segment, consolidatedRevenue);
            if (stats.isPresent()) {
                segmentStats.add(stats.get());
            } else {
                Map<String, Object> omitted = omittedSegment(segment, consolidatedRevenue);
                if (omitted != null) {
                    omittedSegments.add(omitted);
                }
            }
        }
        if (segmentStats.isEmpty()) {
            return Map.of();
        }
        double totalWeight = segmentStats.stream()
                .mapToDouble(SegmentStats::weight)
                .filter(SegmentEconomicAnchorService::positiveFinite)
                .sum();
        if (totalWeight <= 0.0) {
            totalWeight = segmentStats.size();
            List<SegmentStats> equalWeighted = new ArrayList<>();
            for (SegmentStats stats : segmentStats) {
                equalWeighted.add(stats.withWeight(1.0));
            }
            segmentStats = equalWeighted;
        }

        Map<String, Object> anchors = new LinkedHashMap<>();
        anchors.put("revenue_growth", anchorSet(
                "revenue_growth",
                "percent",
                DriverQuantiles.REVENUE_GROWTH,
                segmentStats,
                totalWeight,
                omittedSegments));
        anchors.put("target_operating_margin", anchorSet(
                "target_operating_margin",
                "percent",
                DriverQuantiles.TARGET_OPERATING_MARGIN,
                segmentStats,
                totalWeight,
                omittedSegments));
        anchors.put("sales_to_capital", anchorSet(
                "sales_to_capital",
                "ratio",
                DriverQuantiles.SALES_TO_CAPITAL,
                segmentStats,
                totalWeight,
                omittedSegments));
        return anchors;
    }

    private Optional<SegmentStats> segmentStats(ProspectusSegmentFact segment, double consolidatedRevenue) {
        if (segment == null) {
            return Optional.empty();
        }
        String industry = blankToNull(segment.getMappedIndustry());
        if (industry == null) {
            SectorMapping mapping = blankToNull(segment.getSectorKey()) == null
                    ? null
                    : sectorMappingRepository.findByIndustryName(segment.getSectorKey());
            industry = mapping == null ? null : blankToNull(mapping.getIndustryAsPerExcel());
        }
        if (industry == null) {
            return Optional.empty();
        }
        Optional<InputStatDistribution> stats = inputStatRepository.findFirstByIndustryGroupOrderByIdAsc(industry);
        if (stats.isEmpty()) {
            return Optional.empty();
        }
        return Optional.of(new SegmentStats(
                blankToNull(segment.getSegmentName()),
                blankToNull(segment.getSectorKey()),
                industry,
                blankToNull(segment.getMappingConfidence()),
                segment.getWarnings() == null ? List.of() : List.copyOf(segment.getWarnings()),
                weight(segment, consolidatedRevenue),
                stats.get()));
    }

    private static Map<String, Object> anchorSet(
            String field,
            String unit,
            DriverQuantiles quantiles,
            List<SegmentStats> segmentStats,
            double totalWeight,
            List<Map<String, Object>> omittedSegments) {
        Map<String, Object> set = new LinkedHashMap<>();
        set.put("schema_version", SCHEMA_VERSION);
        set.put("driver", field);
        set.put("field", field);
        set.put("unit", unit);
        set.put("source", SOURCE);
        set.put("source_note", SOURCE_NOTE);
        Map<String, Object> anchors = new LinkedHashMap<>();
        anchors.put("low", anchor(weighted(segmentStats, totalWeight, quantiles.low), field, "Q1"));
        anchors.put("base", anchor(weighted(segmentStats, totalWeight, quantiles.base), field, "median"));
        anchors.put("high", anchor(weighted(segmentStats, totalWeight, quantiles.high), field, "Q3"));
        set.put("anchors", anchors);
        set.put("segment_breakdown", breakdown(segmentStats, totalWeight, quantiles));
        if (!omittedSegments.isEmpty()) {
            set.put("omitted_segments", List.copyOf(omittedSegments));
        }
        List<String> warnings = anchorWarnings(segmentStats, omittedSegments);
        if (!warnings.isEmpty()) {
            set.put("warnings", warnings);
        }
        return set;
    }

    private static Map<String, Object> anchor(double value, String field, String quantile) {
        return Map.of(
                "value", round2(value),
                "provenance", SOURCE + ": revenue-weighted " + quantile + " for " + field);
    }

    private static List<Map<String, Object>> breakdown(
            List<SegmentStats> segmentStats,
            double totalWeight,
            DriverQuantiles quantiles) {
        return segmentStats.stream()
                .sorted(Comparator.comparing(SegmentStats::industry))
                .map(stats -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("segment", stats.segmentName());
                    row.put("sector_key", stats.sectorKey());
                    row.put("industry_group", stats.industry());
                    row.put("mapping_confidence", stats.mappingConfidence());
                    row.put("weight", round6(stats.weight()));
                    row.put("filing_weight", round6(stats.weight()));
                    row.put("effective_anchor_weight", round6(effectiveAnchorWeight(stats.weight(), totalWeight)));
                    row.put("low", round2(value(stats.stats(), quantiles.low)));
                    row.put("base", round2(value(stats.stats(), quantiles.base)));
                    row.put("high", round2(value(stats.stats(), quantiles.high)));
                    row.put("count", stats.stats().getCount());
                    if (!stats.warnings().isEmpty()) {
                        row.put("warnings", stats.warnings());
                    }
                    return row;
                })
                .toList();
    }

    private Map<String, Object> omittedSegment(ProspectusSegmentFact segment, double consolidatedRevenue) {
        if ("geography".equalsIgnoreCase(segment.getRowRole())) {
            return null;
        }
        String name = blankToNull(segment.getSegmentName());
        if (name == null) {
            return null;
        }
        String industry = blankToNull(segment.getMappedIndustry());
        if (industry == null) {
            SectorMapping mapping = blankToNull(segment.getSectorKey()) == null
                    ? null
                    : sectorMappingRepository.findByIndustryName(segment.getSectorKey());
            industry = mapping == null ? null : blankToNull(mapping.getIndustryAsPerExcel());
        }
        Map<String, Object> omitted = new LinkedHashMap<>();
        omitted.put("segment", name);
        omitted.put("sector_key", blankToNull(segment.getSectorKey()));
        omitted.put("mapping_confidence", blankToNull(segment.getMappingConfidence()));
        omitted.put("weight", round6(weight(segment, consolidatedRevenue)));
        omitted.put("reason", industry == null ? "unmapped_segment" : "missing_industry_quantiles");
        return omitted;
    }

    private static List<String> anchorWarnings(
            List<SegmentStats> segmentStats,
            List<Map<String, Object>> omittedSegments) {
        List<String> warnings = new ArrayList<>(segmentStats.stream()
                .filter(stats -> Set.of("low", "unmapped", "unknown").contains(
                        stats.mappingConfidence() == null ? "" : stats.mappingConfidence().toLowerCase()))
                .map(stats -> "Anchor includes " + stats.mappingConfidence()
                        + "-confidence mapping for segment " + stats.segmentName() + ".")
                .distinct()
                .toList());
        for (Map<String, Object> omitted : omittedSegments) {
            double weight = omitted.get("weight") instanceof Number number ? number.doubleValue() : 0.0;
            String reason = "unmapped_segment".equals(omitted.get("reason"))
                    ? "has no reviewed industry mapping"
                    : "has no Damodaran industry quantiles";
            String label = weight >= MATERIAL_OMITTED_WEIGHT ? "Material segment " : "Segment ";
            warnings.add(label + omitted.get("segment") + " (revenue weight " + percentLabel(weight) + ") "
                    + reason + " and is omitted from this weighted anchor; the anchor is incomplete.");
        }
        return warnings;
    }

    private static String percentLabel(double weight) {
        return Math.round(weight * 1000.0) / 10.0 + "%";
    }

    private static double weighted(List<SegmentStats> stats, double totalWeight, ValueKind kind) {
        return stats.stream()
                .mapToDouble(row -> value(row.stats(), kind) * row.weight())
                .sum() / totalWeight;
    }

    private static double effectiveAnchorWeight(double weight, double totalWeight) {
        if (!positiveFinite(weight) || !positiveFinite(totalWeight)) {
            return 0.0;
        }
        return weight / totalWeight;
    }

    private static double value(InputStatDistribution stats, ValueKind kind) {
        return switch (kind) {
            case REVENUE_GROWTH_Q1 -> stats.getRevenueGrowthRateFirstQuartile();
            case REVENUE_GROWTH_MEDIAN -> stats.getRevenueGrowthRateMedian();
            case REVENUE_GROWTH_Q3 -> stats.getRevenueGrowthRateThirdQuartile();
            case MARGIN_Q1 -> stats.getPreTaxOperatingMarginFirstQuartile();
            case MARGIN_MEDIAN -> stats.getPreTaxOperatingMarginMedian();
            case MARGIN_Q3 -> stats.getPreTaxOperatingMarginThirdQuartile();
            case SALES_TO_CAPITAL_Q1 -> stats.getSalesToInvestedCapitalFirstQuartile();
            case SALES_TO_CAPITAL_MEDIAN -> stats.getSalesToInvestedCapitalMedian();
            case SALES_TO_CAPITAL_Q3 -> stats.getSalesToInvestedCapitalThirdQuartile();
        };
    }

    private static double weight(ProspectusSegmentFact segment, double consolidatedRevenue) {
        if (positiveFinite(segment.getRevenueWeight())) {
            return segment.getRevenueWeight();
        }
        if (positiveFinite(segment.getRevenueAmount()) && consolidatedRevenue > 0.0) {
            return segment.getRevenueAmount() / consolidatedRevenue;
        }
        return 0.0;
    }

    private static List<ProspectusSegmentFact> scenarioSegmentFacts(
            ProspectusFinancialPacket packet,
            List<ProspectusSegmentScenario> scenarioSegments) {
        double targetTotal = scenarioSegments.stream()
                .map(segment -> scenarioTerminalRevenue(packet, segment))
                .filter(SegmentEconomicAnchorService::positiveFinite)
                .mapToDouble(Double::doubleValue)
                .sum();
        double baseTotal = scenarioSegments.stream()
                .map(segment -> scenarioBaseRevenue(packet, segment))
                .filter(SegmentEconomicAnchorService::positiveFinite)
                .mapToDouble(Double::doubleValue)
                .sum();

        List<ProspectusSegmentFact> facts = new ArrayList<>();
        for (ProspectusSegmentScenario segment : scenarioSegments) {
            if (segment == null) {
                continue;
            }
            Double baseRevenue = scenarioBaseRevenue(packet, segment);
            Double terminalRevenue = scenarioTerminalRevenue(packet, segment);
            ProspectusSegmentFact fact = new ProspectusSegmentFact();
            fact.setSegmentName(blankToNull(segment.name()));
            fact.setSectorKey(blankToNull(segment.sectorKey()));
            fact.setMappedIndustry(blankToNull(segment.mappedIndustry()));
            fact.setRevenueAmount(firstPositive(terminalRevenue, baseRevenue));
            fact.setRevenueWeight(scenarioSegmentWeight(
                    baseRevenue,
                    terminalRevenue,
                    baseTotal,
                    targetTotal,
                    scenarioSegments.size()));
            fact.setMappingConfidence("reviewed");
            fact.setRowRole("reportable_segment");
            facts.add(fact);
        }
        return facts;
    }

    private static Double scenarioBaseRevenue(ProspectusFinancialPacket packet, ProspectusSegmentScenario segment) {
        if (segment == null) {
            return null;
        }
        if (positiveFinite(segment.baseRevenue())) {
            return segment.baseRevenue();
        }
        if (!segment.projectedRevenuesOrEmpty().isEmpty()) {
            Double baseRevenue = segment.projectedRevenuesOrEmpty().get(0);
            if (positiveFinite(baseRevenue)) {
                return baseRevenue;
            }
        }
        String name = blankToNull(segment.name());
        if (name == null || packet == null || packet.getSegments() == null) {
            return null;
        }
        String normalizedName = normalizeKey(name);
        for (ProspectusSegmentFact fact : packet.getSegments()) {
            if (fact == null || fact.getSegmentName() == null) {
                continue;
            }
            if (normalizedName.equals(normalizeKey(fact.getSegmentName()))
                    && positiveFinite(fact.getRevenueAmount())) {
                return fact.getRevenueAmount();
            }
        }
        return null;
    }

    private static Double scenarioTerminalRevenue(ProspectusFinancialPacket packet, ProspectusSegmentScenario segment) {
        Double explicitTargetRevenue = scenarioExplicitTargetRevenue(segment);
        return explicitTargetRevenue == null ? scenarioBaseRevenue(packet, segment) : explicitTargetRevenue;
    }

    private static Double scenarioExplicitTargetRevenue(ProspectusSegmentScenario segment) {
        if (segment == null) {
            return null;
        }
        if (positiveFinite(segment.targetRevenue())) {
            return segment.targetRevenue();
        }
        List<Double> projected = segment.projectedRevenuesOrEmpty();
        for (int i = projected.size() - 1; i >= 0; i--) {
            Double value = projected.get(i);
            if (positiveFinite(value)) {
                return value;
            }
        }
        return null;
    }

    private static double scenarioSegmentWeight(
            Double baseRevenue,
            Double terminalRevenue,
            double baseTotal,
            double targetTotal,
            int segmentCount) {
        if (positiveFinite(terminalRevenue) && targetTotal > 0.0) {
            return terminalRevenue / targetTotal;
        }
        if (positiveFinite(baseRevenue) && baseTotal > 0.0) {
            return baseRevenue / baseTotal;
        }
        return segmentCount > 0 ? 1.0 / segmentCount : 0.0;
    }

    private static Double firstPositive(Double first, Double second) {
        if (positiveFinite(first)) {
            return first;
        }
        return positiveFinite(second) ? second : null;
    }

    private static double latestRevenue(ProspectusFinancialPacket packet) {
        if (packet.getFinancials() == null || packet.getFinancials().getIncomeStatement() == null) {
            return 0.0;
        }
        return packet.getFinancials().getIncomeStatement().stream()
                .filter(Objects::nonNull)
                .filter(fact -> "revenue".equals(fact.getCanonicalField()))
                .sorted(Comparator.comparing(
                        ProspectusFact::getPeriodEnd,
                        Comparator.nullsFirst(String::compareTo)))
                .map(ProspectusFact::getNormalizedValue)
                .filter(SegmentEconomicAnchorService::positiveFinite)
                .reduce((first, second) -> second)
                .orElse(0.0);
    }

    private static boolean positiveFinite(Double value) {
        return value != null && Double.isFinite(value) && value > 0.0;
    }

    private static String blankToNull(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value;
    }

    private static String normalizeKey(String value) {
        String normalized = value == null ? "" : value.toLowerCase();
        return normalized.replaceAll("[^a-z0-9]+", "_").replaceAll("^_|_$", "");
    }

    private static double round2(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    private static double round6(double value) {
        return Math.round(value * 1_000_000.0) / 1_000_000.0;
    }

    private enum ValueKind {
        REVENUE_GROWTH_Q1,
        REVENUE_GROWTH_MEDIAN,
        REVENUE_GROWTH_Q3,
        MARGIN_Q1,
        MARGIN_MEDIAN,
        MARGIN_Q3,
        SALES_TO_CAPITAL_Q1,
        SALES_TO_CAPITAL_MEDIAN,
        SALES_TO_CAPITAL_Q3
    }

    private enum DriverQuantiles {
        REVENUE_GROWTH(ValueKind.REVENUE_GROWTH_Q1, ValueKind.REVENUE_GROWTH_MEDIAN, ValueKind.REVENUE_GROWTH_Q3),
        TARGET_OPERATING_MARGIN(ValueKind.MARGIN_Q1, ValueKind.MARGIN_MEDIAN, ValueKind.MARGIN_Q3),
        SALES_TO_CAPITAL(ValueKind.SALES_TO_CAPITAL_Q1, ValueKind.SALES_TO_CAPITAL_MEDIAN, ValueKind.SALES_TO_CAPITAL_Q3);

        private final ValueKind low;
        private final ValueKind base;
        private final ValueKind high;

        DriverQuantiles(ValueKind low, ValueKind base, ValueKind high) {
            this.low = low;
            this.base = base;
            this.high = high;
        }
    }

    private record SegmentStats(
            String segmentName,
            String sectorKey,
            String industry,
            String mappingConfidence,
            List<String> warnings,
            double weight,
            InputStatDistribution stats) {

        SegmentStats withWeight(double newWeight) {
            return new SegmentStats(segmentName, sectorKey, industry, mappingConfidence, warnings, newWeight, stats);
        }
    }
}
