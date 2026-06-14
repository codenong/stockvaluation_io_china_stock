package io.stockvaluation.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.stockvaluation.domain.SectorMapping;
import io.stockvaluation.provider.prospectus.ProspectusExtractionIssue;
import io.stockvaluation.provider.prospectus.ProspectusFact;
import io.stockvaluation.provider.prospectus.ProspectusFinancialPacket;
import io.stockvaluation.provider.prospectus.ProspectusRawCell;
import io.stockvaluation.provider.prospectus.ProspectusRawRow;
import io.stockvaluation.provider.prospectus.ProspectusRawTable;
import io.stockvaluation.provider.prospectus.ProspectusSegmentFact;
import io.stockvaluation.repository.SectorMappingRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Pattern;

@Service
@RequiredArgsConstructor
public class SegmentMappingProposalService {

    private static final double LOW_CONFIDENCE_MIN_SCORE = 0.30;
    private static final double MEDIUM_CONFIDENCE_MIN_SCORE = 0.55;
    private static final double HIGH_CONFIDENCE_MIN_SCORE = 0.75;
    private static final double HIGH_CONFIDENCE_MIN_MARGIN = 0.25;
    private static final double MIN_CLEAN_COVERAGE = 0.80;
    private static final double MAX_CLEAN_COVERAGE = 1.20;
    private static final double SUBTOTAL_TOLERANCE = 0.01;
    private static final Pattern NON_TOKEN = Pattern.compile("[^a-z0-9]+");
    private static final Set<String> STOP_TOKENS = Set.of(
            "and", "the", "services", "service", "segment", "business", "revenue", "products", "product");
    private static final Set<String> CONTEXT_SENSITIVE_TERMS = Set.of("network");
    private static final Map<String, Set<String>> CONTEXT_CONFIRMING_TOKENS = Map.of(
            "network", Set.of(
                    "telecom",
                    "telecommunications",
                    "wireless",
                    "broadband",
                    "connectivity",
                    "carrier",
                    "mobile",
                    "fiber",
                    "fibre",
                    "internet"));
    private static final Set<String> GEOGRAPHY_LABELS = Set.of(
            "united states", "u s", "us", "usa", "domestic", "international", "americas", "north america",
            "latin america", "emea", "europe", "middle east", "africa", "apac", "asia pacific", "asia",
            "china", "japan", "canada", "mexico", "india", "germany", "france", "uk", "united kingdom",
            "australia", "rest of world", "foreign");
    private static final Map<String, List<String>> SECTOR_SYNONYMS = loadSynonyms();

    private final SectorMappingRepository sectorMappingRepository;

    public SegmentMappingProposalResult proposeMappings(List<SegmentMappingInput> inputs, double consolidatedRevenue) {
        if (inputs == null || inputs.isEmpty()) {
            return new SegmentMappingProposalResult(List.of(), 0.0, false, List.of());
        }
        List<WeightedCandidate> candidates = inputs.stream()
                .map(input -> weightedCandidate(input, consolidatedRevenue))
                .filter(Objects::nonNull)
                .toList();
        if (candidates.isEmpty()) {
            return new SegmentMappingProposalResult(List.of(), 0.0, false, List.of());
        }

        double coverage = candidates.stream().mapToDouble(WeightedCandidate::revenueWeight).sum();
        List<String> globalWarnings = new ArrayList<>();
        if (coverage < MIN_CLEAN_COVERAGE || coverage > MAX_CLEAN_COVERAGE) {
            globalWarnings.add("Segment candidate table covers "
                    + pct(coverage)
                    + " of consolidated revenue; review missing or duplicate segment rows.");
        }
        SectorMappingLoad mappingLoad = sectorMappings();
        if (mappingLoad.warning() != null) {
            globalWarnings.add(mappingLoad.warning());
        }

        List<SegmentMappingProposal> proposals = new ArrayList<>();
        for (WeightedCandidate weighted : candidates) {
            MappingChoice choice = bestMapping(weighted.candidate(), mappingLoad.mappings());
            List<String> warnings = new ArrayList<>(weighted.candidate().warnings());
            warnings.addAll(choice.warnings());
            warnings.addAll(globalWarnings);
            proposals.add(new SegmentMappingProposal(
                    weighted.candidate().label(),
                    weighted.revenueAmount(),
                    weighted.revenueWeight(),
                    choice.sectorKey(),
                    choice.mappedIndustry(),
                    choice.confidence(),
                    choice.score(),
                    choice.margin(),
                    choice.rationale(),
                    weighted.candidate().components(),
                    weighted.candidate().rowRole(),
                    dedupe(warnings),
                    weighted.candidate().tableTitle()));
        }

        boolean materialGap = proposals.stream().anyMatch(SegmentMappingProposalService::materialGap);
        return new SegmentMappingProposalResult(proposals, round2(coverage * 100.0), materialGap, dedupe(globalWarnings));
    }

    public void applyProposedMappings(ProspectusFinancialPacket packet) {
        if (packet == null || packet.getSegments() == null || !packet.getSegments().isEmpty()) {
            return;
        }
        double consolidatedRevenue = latestRevenue(packet);
        if (consolidatedRevenue <= 0.0 || packet.getSegmentCandidateTables() == null
                || packet.getSegmentCandidateTables().isEmpty()) {
            return;
        }

        CandidateSet candidateSet = bestCandidateSet(packet.getSegmentCandidateTables(), consolidatedRevenue);
        if (candidateSet.candidates().isEmpty()) {
            return;
        }

        SegmentMappingProposalResult result = proposeMappings(candidateSet.candidates().stream()
                .map(SegmentMappingProposalService::input)
                .toList(), consolidatedRevenue);
        result.warnings().stream()
                .filter(warning -> warning.contains("sector mapping lookup failed"))
                .findFirst()
                .ifPresent(warning -> addExtractionIssue(
                        packet,
                        "segment_mapping_repository_failure",
                        "warning",
                        "segments",
                        warning));

        List<ProspectusSegmentFact> segments = new ArrayList<>();
        for (SegmentMappingProposal proposal : result.proposals()) {
            ProspectusSegmentFact segment = new ProspectusSegmentFact();
            segment.setSegmentName(proposal.name());
            segment.setRevenueAmount(proposal.revenueAmount());
            segment.setRevenueWeight(proposal.revenueWeight());
            segment.setSectorKey(proposal.sectorKey());
            segment.setMappedIndustry(proposal.mappedIndustry());
            segment.setMappingConfidence(proposal.mappingConfidence());
            segment.setMappingScore(proposal.mappingScore());
            segment.setMappingScoreMargin(proposal.mappingScoreMargin());
            segment.setRationale(proposal.rationale());
            segment.setComponents(proposal.components());
            segment.setRowRole(proposal.rowRole());
            segment.setWarnings(proposal.warnings());
            segment.setSourceRowLabel(proposal.name());
            segment.setTableTitle(proposal.tableTitle());
            segment.setPeriodEnd(packet.getSourceProvenance() == null ? null : packet.getSourceProvenance().getPeriodEnd());
            segment.setSourceProvenance(packet.getSourceProvenance());
            segments.add(segment);
        }
        packet.setSegments(segments);
    }

    private static SegmentMappingInput input(SegmentCandidate candidate) {
        return new SegmentMappingInput(
                candidate.label(),
                candidate.amount(),
                null,
                candidate.components(),
                candidate.rowRole(),
                candidate.tableTitle(),
                candidate.warnings());
    }

    private SectorMappingLoad sectorMappings() {
        try {
            List<SectorMapping> mappings = sectorMappingRepository.findUsableForSegmentValuation();
            if (mappings == null || mappings.isEmpty()) {
                return new SectorMappingLoad(List.of(), "no usable sector mapping rows were available for segment valuation.");
            }
            return new SectorMappingLoad(mappings.stream()
                    .filter(mapping -> mapping != null
                            && !isBlank(mapping.getYahooIndustryKey())
                            && !isBlank(mapping.getIndustryAsPerExcel()))
                    .toList(), null);
        } catch (RuntimeException exception) {
            return new SectorMappingLoad(
                    List.of(),
                    "sector mapping lookup failed: " + defaultString(exception.getMessage(), exception.getClass().getSimpleName()));
        }
    }

    private static double latestRevenue(ProspectusFinancialPacket packet) {
        if (packet.getFinancials() == null || packet.getFinancials().getIncomeStatement() == null) {
            return 0.0;
        }
        return packet.getFinancials().getIncomeStatement().stream()
                .filter(fact -> "revenue".equals(fact.getCanonicalField()))
                .map(ProspectusFact::getNormalizedValue)
                .filter(Objects::nonNull)
                .filter(Double::isFinite)
                .findFirst()
                .orElse(0.0);
    }

    private static CandidateSet bestCandidateSet(List<ProspectusRawTable> tables, double consolidatedRevenue) {
        return tables.stream()
                .map(table -> candidateSet(table, consolidatedRevenue))
                .filter(candidateSet -> candidateSet.candidates().size() >= 2)
                .min(Comparator
                        .comparing((CandidateSet candidateSet) -> candidateSet.geographyOnly() ? 1 : 0)
                        .thenComparingDouble(candidateSet -> Math.abs(1.0 - candidateSet.coverage()))
                        .thenComparing(candidateSet -> -candidateSet.candidates().size()))
                .orElse(new CandidateSet(List.of(), 0.0, false));
    }

    private static CandidateSet candidateSet(ProspectusRawTable table, double consolidatedRevenue) {
        List<RowValue> rows = dedupeRows(rowValues(table));
        List<SegmentCandidate> candidates = candidatesFromRows(table, rows);
        double total = candidates.stream().mapToDouble(SegmentCandidate::amount).sum();
        double coverage = consolidatedRevenue > 0.0 ? total / consolidatedRevenue : 0.0;
        boolean geographyOnly = !candidates.isEmpty()
                && candidates.stream().allMatch(candidate -> "geography".equals(candidate.rowRole()));
        return new CandidateSet(candidates, coverage, geographyOnly);
    }

    private static List<RowValue> rowValues(ProspectusRawTable table) {
        if (table == null || table.rows() == null) {
            return List.of();
        }
        List<RowValue> rows = new ArrayList<>();
        for (ProspectusRawRow row : table.rows()) {
            Double amount = firstAmount(row);
            String label = cleanLabel(row == null ? null : row.label());
            if (amount != null && amount > 0.0 && !label.isBlank()) {
                rows.add(new RowValue(label, amount, rowRole(label), new ArrayList<>()));
            }
        }
        return rows;
    }

    private static List<RowValue> dedupeRows(List<RowValue> rows) {
        Map<String, RowValue> seen = new LinkedHashMap<>();
        for (RowValue row : rows) {
            String key = normalize(row.label()) + "|" + round2(row.amount());
            RowValue previous = seen.get(key);
            if (previous == null) {
                seen.put(key, row);
            } else {
                previous.warnings().add("duplicate segment row ignored: " + row.label());
            }
        }
        return new ArrayList<>(seen.values());
    }

    private static List<SegmentCandidate> candidatesFromRows(ProspectusRawTable table, List<RowValue> rows) {
        List<SegmentCandidate> candidates = new ArrayList<>();
        List<RowValue> group = new ArrayList<>();
        for (int index = 0; index < rows.size(); index++) {
            RowValue row = rows.get(index);
            if (isGrandTotal(row, rows, index)) {
                flushGroup(table, candidates, group);
                continue;
            }
            if ("residual".equals(row.rowRole()) || "geography".equals(row.rowRole())) {
                flushGroup(table, candidates, group);
                candidates.add(candidate(table, row, List.of(), row.rowRole()));
                continue;
            }
            double groupTotal = group.stream().mapToDouble(RowValue::amount).sum();
            if (group.size() >= 2 && closeTo(row.amount(), groupTotal) && !isTotalLabel(row.label())) {
                candidates.add(candidate(
                        table,
                        row,
                        group.stream().map(RowValue::label).toList(),
                        "reportable_segment"));
                group.clear();
                continue;
            }
            group.add(row);
        }
        flushGroup(table, candidates, group);
        return candidates;
    }

    private static void flushGroup(ProspectusRawTable table, List<SegmentCandidate> candidates, List<RowValue> group) {
        if (group.isEmpty()) {
            return;
        }
        for (RowValue row : group) {
            candidates.add(candidate(table, row, List.of(), "reportable_segment"));
        }
        group.clear();
    }

    private static SegmentCandidate candidate(
            ProspectusRawTable table,
            RowValue row,
            List<String> components,
            String rowRole) {
        return new SegmentCandidate(
                row.label(),
                row.amount(),
                components,
                table == null ? null : table.title(),
                rowRole,
                List.copyOf(row.warnings()));
    }

    private static Double firstAmount(ProspectusRawRow row) {
        if (row == null || row.cells() == null) {
            return null;
        }
        return row.cells().stream()
                .map(ProspectusRawCell::normalizedValue)
                .filter(Objects::nonNull)
                .findFirst()
                .orElse(null);
    }

    private static WeightedCandidate weightedCandidate(SegmentMappingInput input, double consolidatedRevenue) {
        if (input == null || isBlank(input.name())) {
            return null;
        }
        Double weight = normalizedWeight(input.revenueWeight());
        Double amount = input.revenueAmount();
        if ((weight == null || weight <= 0.0) && amount != null && amount > 0.0 && consolidatedRevenue > 0.0) {
            weight = amount / consolidatedRevenue;
        }
        if ((amount == null || amount <= 0.0) && weight != null && weight > 0.0 && consolidatedRevenue > 0.0) {
            amount = weight * consolidatedRevenue;
        }
        if (weight == null || weight <= 0.0 || !Double.isFinite(weight)) {
            return null;
        }
        String role = isBlank(input.rowRole()) || "unknown".equals(input.rowRole())
                ? rowRole(input.name())
                : input.rowRole();
        if ("unknown".equals(role)) {
            role = "reportable_segment";
        }
        SegmentCandidate candidate = new SegmentCandidate(
                input.name(),
                amount == null ? 0.0 : amount,
                safeList(input.components()),
                input.tableTitle(),
                role,
                safeList(input.warnings()));
        return new WeightedCandidate(candidate, amount == null ? null : round2(amount), round6(weight));
    }

    private static MappingChoice bestMapping(SegmentCandidate candidate, List<SectorMapping> mappings) {
        if ("residual".equals(candidate.rowRole())) {
            return new MappingChoice(
                    null,
                    null,
                    "unmapped",
                    0.0,
                    0.0,
                    "Residual bucket left unmapped for review.",
                    List.of("residual bucket; materiality review required"));
        }
        if ("geography".equals(candidate.rowRole())) {
            return new MappingChoice(
                    null,
                    null,
                    "unmapped",
                    0.0,
                    0.0,
                    "Geographic rows are not operating segment industry mappings.",
                    List.of("geography disclosure cannot be mapped to an industry without operating segment evidence."));
        }
        if (mappings == null || mappings.isEmpty()) {
            return new MappingChoice(
                    null,
                    null,
                    "unmapped",
                    0.0,
                    0.0,
                    "No usable sector mapping rows were available.",
                    List.of("No reliable sector mapping proposal; correct or leave unmapped at the review gate."));
        }

        ScoredMapping best = null;
        ScoredMapping second = null;
        for (SectorMapping mapping : mappings) {
            ScoredMapping scored = score(candidate, mapping);
            if (best == null || scored.score() > best.score()) {
                second = best;
                best = scored;
            } else if (second == null || scored.score() > second.score()) {
                second = scored;
            }
        }
        if (best == null || best.score() < LOW_CONFIDENCE_MIN_SCORE) {
            return new MappingChoice(
                    null,
                    null,
                    "unmapped",
                    best == null ? 0.0 : round4(best.score()),
                    0.0,
                    "No reliable sector mapping proposal.",
                    List.of("No reliable sector mapping proposal; correct or leave unmapped at the review gate."));
        }

        double margin = second == null ? best.score() : best.score() - second.score();
        String confidence = confidence(best.score(), margin);
        List<String> warnings = new ArrayList<>();
        if (isShortAcronym(candidate.label())) {
            confidence = "low";
            warnings.add("short acronym segment label; mapping is capped at low confidence until reviewed.");
        }
        if ("medium".equals(confidence)) {
            warnings.add("medium-confidence mapping proposal; confirm before use.");
        } else if ("low".equals(confidence)) {
            warnings.add("low-confidence mapping proposal; material rows require review before valuation.");
        }
        return new MappingChoice(
                best.mapping().getYahooIndustryKey(),
                best.mapping().getIndustryAsPerExcel(),
                confidence,
                round4(best.score()),
                round4(Math.max(0.0, margin)),
                rationale(best),
                warnings);
    }

    private static ScoredMapping score(SegmentCandidate candidate, SectorMapping mapping) {
        String normalizedLabel = normalize(candidate.label());
        String normalizedText = normalize(candidate.label() + " " + String.join(" ", candidate.components()));
        Set<String> labelTokens = tokens(normalizedLabel);
        Set<String> queryTokens = tokens(normalizedText);
        Set<String> mappingTokens = tokens(normalize(mapping.getYahooIndustryKey() + " "
                + mapping.getYahooSector() + " " + mapping.getIndustryAsPerExcel()));
        List<String> aliases = SECTOR_SYNONYMS.getOrDefault(mapping.getYahooIndustryKey(), List.of());
        for (String alias : aliases) {
            mappingTokens.addAll(tokens(normalize(alias)));
        }

        double score = 0.0;
        List<String> matchedTerms = new ArrayList<>();
        for (String token : queryTokens) {
            if (!STOP_TOKENS.contains(token)
                    && mappingTokens.contains(token)
                    && shouldCountTerm(token, queryTokens)) {
                score += 1.0;
                matchedTerms.add(token);
            }
        }
        for (String alias : aliases) {
            String normalizedAlias = normalize(alias);
            if (!normalizedAlias.isBlank()
                    && containsPhrase(normalizedText, normalizedAlias)
                    && shouldCountAlias(normalizedAlias, queryTokens)) {
                score += 2.0;
                matchedTerms.add(alias);
            }
        }
        int componentTokenCount = Math.max(0, queryTokens.size() - labelTokens.size());
        double denominator = Math.max(2.0, Math.min(6.0, labelTokens.size() * 2.0 + componentTokenCount * 0.5));
        return new ScoredMapping(mapping, Math.min(1.0, score / denominator), dedupe(matchedTerms));
    }

    private static boolean shouldCountAlias(String normalizedAlias, Set<String> queryTokens) {
        return !CONTEXT_SENSITIVE_TERMS.contains(normalizedAlias)
                || hasConfirmingContext(normalizedAlias, queryTokens);
    }

    private static boolean shouldCountTerm(String token, Set<String> queryTokens) {
        return !CONTEXT_SENSITIVE_TERMS.contains(token)
                || hasConfirmingContext(token, queryTokens);
    }

    private static boolean hasConfirmingContext(String term, Set<String> queryTokens) {
        Set<String> confirmingTokens = CONTEXT_CONFIRMING_TOKENS.getOrDefault(term, Set.of());
        return queryTokens.stream()
                .filter(token -> !term.equals(token))
                .anyMatch(confirmingTokens::contains);
    }

    private static String confidence(double score, double margin) {
        if (score >= HIGH_CONFIDENCE_MIN_SCORE && margin >= HIGH_CONFIDENCE_MIN_MARGIN) {
            return "high";
        }
        if (score >= MEDIUM_CONFIDENCE_MIN_SCORE) {
            return "medium";
        }
        return "low";
    }

    private static String rationale(ScoredMapping mapping) {
        String matched = mapping.matchedTerms().isEmpty()
                ? "segment label tokens"
                : String.join(", ", mapping.matchedTerms());
        return "Matched " + matched + " to " + mapping.mapping().getYahooIndustryKey() + ".";
    }

    private static String rowRole(String label) {
        String normalized = normalize(label);
        if (isResidualLabel(normalized)) {
            return "residual";
        }
        if (isGeographyLabel(normalized)) {
            return "geography";
        }
        if (isTotalLabel(normalized)) {
            return "grand_total";
        }
        return "unknown";
    }

    private static boolean isGrandTotal(RowValue row, List<RowValue> rows, int index) {
        if (!"grand_total".equals(row.rowRole()) && !isTotalLabel(row.label())) {
            return false;
        }
        double priorSum = rows.subList(0, index).stream()
                .filter(prior -> !"grand_total".equals(prior.rowRole()))
                .mapToDouble(RowValue::amount)
                .sum();
        return index == rows.size() - 1 || closeTo(row.amount(), priorSum);
    }

    private static boolean isResidualLabel(String normalizedLabel) {
        return normalizedLabel.equals("other")
                || normalizedLabel.equals("all other")
                || normalizedLabel.contains("corporate")
                || normalizedLabel.contains("elimination")
                || normalizedLabel.contains("unallocated")
                || normalizedLabel.contains("reconciliation");
    }

    private static boolean isGeographyLabel(String normalizedLabel) {
        return GEOGRAPHY_LABELS.contains(normalizedLabel);
    }

    private static boolean isTotalLabel(String label) {
        String normalized = normalize(label);
        return normalized.equals("total")
                || normalized.contains("total revenue")
                || normalized.contains("total revenues")
                || normalized.contains("consolidated");
    }

    private static boolean isShortAcronym(String label) {
        String normalized = normalize(label);
        return normalized.length() <= 3 && normalized.chars().allMatch(Character::isLetterOrDigit);
    }

    private static boolean containsPhrase(String normalizedText, String normalizedPhrase) {
        return (" " + normalizedText + " ").contains(" " + normalizedPhrase + " ");
    }

    private static boolean materialGap(SegmentMappingProposal proposal) {
        double weight = proposal.revenueWeight() == null ? 0.0 : proposal.revenueWeight();
        if (weight > 1.5) {
            weight = weight / 100.0;
        }
        boolean unmapped = isBlank(proposal.sectorKey()) || isBlank(proposal.mappedIndustry());
        if (unmapped && weight > 0.10) {
            return true;
        }
        String confidence = proposal.mappingConfidence() == null
                ? ""
                : proposal.mappingConfidence().toLowerCase(Locale.ROOT);
        return Set.of("low", "unmapped", "unknown").contains(confidence) && weight > 0.05;
    }

    private static boolean closeTo(double value, double expected) {
        return value > 0.0 && Math.abs(value - expected) / value <= SUBTOTAL_TOLERANCE;
    }

    private static String normalize(String value) {
        return NON_TOKEN.matcher(value == null ? "" : value.toLowerCase(Locale.ROOT)).replaceAll(" ").trim();
    }

    private static Set<String> tokens(String normalizedText) {
        Set<String> tokens = new LinkedHashSet<>();
        for (String token : normalizedText.split("\\s+")) {
            if (token.length() >= 2) {
                tokens.add(token);
            }
        }
        return tokens;
    }

    private static String cleanLabel(String label) {
        return label == null
                ? ""
                : label.replaceAll("\\(\\d+\\)", "")
                        .replace('.', ' ')
                        .replaceAll("\\s+", " ")
                        .trim();
    }

    private static void addExtractionIssue(
            ProspectusFinancialPacket packet,
            String code,
            String severity,
            String field,
            String message) {
        if (packet.getExtractionIssues() == null) {
            packet.setExtractionIssues(new ArrayList<>());
        }
        packet.getExtractionIssues().add(new ProspectusExtractionIssue(code, severity, message, field));
    }

    private static Map<String, List<String>> loadSynonyms() {
        try (InputStream input = SegmentMappingProposalService.class.getResourceAsStream("/data/sector_key_synonyms.json")) {
            if (input == null) {
                return Map.of();
            }
            Map<String, List<String>> raw = new ObjectMapper().readValue(
                    input,
                    new TypeReference<Map<String, List<String>>>() {
                    });
            Map<String, List<String>> normalized = new HashMap<>();
            for (Map.Entry<String, List<String>> entry : raw.entrySet()) {
                if (entry.getKey() == null || entry.getValue() == null) {
                    continue;
                }
                normalized.put(entry.getKey(), entry.getValue().stream()
                        .filter(value -> value != null && !value.isBlank())
                        .toList());
            }
            return normalized;
        } catch (IOException exception) {
            return Map.of();
        }
    }

    private static List<String> dedupe(List<String> values) {
        return values.stream()
                .filter(value -> value != null && !value.isBlank())
                .distinct()
                .toList();
    }

    private static String pct(double value) {
        return String.format(Locale.ROOT, "%.2f%%", value * 100.0);
    }

    private static String defaultString(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private static List<String> safeList(List<String> values) {
        return values == null ? List.of() : values.stream()
                .filter(value -> value != null && !value.isBlank())
                .toList();
    }

    private static Double normalizedWeight(Double value) {
        if (value == null || !Double.isFinite(value) || value <= 0.0) {
            return null;
        }
        return value > 1.5 ? value / 100.0 : value;
    }

    private static double round2(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    private static double round4(double value) {
        return Math.round(value * 10_000.0) / 10_000.0;
    }

    private static double round6(double value) {
        return Math.round(value * 1_000_000.0) / 1_000_000.0;
    }

    private record SectorMappingLoad(List<SectorMapping> mappings, String warning) {
    }

    public record SegmentMappingInput(
            String name,
            Double revenueAmount,
            Double revenueWeight,
            List<String> components,
            String rowRole,
            String tableTitle,
            List<String> warnings) {
    }

    public record SegmentMappingProposalResult(
            List<SegmentMappingProposal> proposals,
            double revenueCoveragePct,
            boolean materialGap,
            List<String> warnings) {
    }

    public record SegmentMappingProposal(
            String name,
            Double revenueAmount,
            Double revenueWeight,
            String sectorKey,
            String mappedIndustry,
            String mappingConfidence,
            double mappingScore,
            double mappingScoreMargin,
            String rationale,
            List<String> components,
            String rowRole,
            List<String> warnings,
            String tableTitle) {
    }

    private record RowValue(String label, double amount, String rowRole, List<String> warnings) {
    }

    private record WeightedCandidate(SegmentCandidate candidate, Double revenueAmount, Double revenueWeight) {
    }

    private record SegmentCandidate(
            String label,
            double amount,
            List<String> components,
            String tableTitle,
            String rowRole,
            List<String> warnings) {
    }

    private record CandidateSet(List<SegmentCandidate> candidates, double coverage, boolean geographyOnly) {
    }

    private record ScoredMapping(SectorMapping mapping, double score, List<String> matchedTerms) {
    }

    private record MappingChoice(
            String sectorKey,
            String mappedIndustry,
            String confidence,
            double score,
            double margin,
            String rationale,
            List<String> warnings) {
    }
}
