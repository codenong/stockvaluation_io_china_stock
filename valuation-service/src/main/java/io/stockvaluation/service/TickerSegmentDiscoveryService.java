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
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class TickerSegmentDiscoveryService {

    private static final double MIN_MAPPED_COVERAGE = 0.80;
    private static final double MAX_TOTAL_REVENUE_DISTANCE = 0.35;
    private static final double MAX_SEGMENT_SUM_GAP = 0.08;

    private static final Map<String, Map<String, SegmentMappingOverride>> CURATED_MAPPINGS = Map.of(
            "AMZN", Map.of(
                    key("North America"), mapping("internet-retail", "Retail (General)"),
                    key("International"), mapping("internet-retail", "Retail (General)"),
                    key("AWS"), mapping("software-infrastructure", "Software (System & Application)")),
            "MSFT", Map.of(
                    key("Productivity and Business Processes"), mapping("software-application", "Software (System & Application)"),
                    key("Intelligent Cloud"), mapping("software-infrastructure", "Software (System & Application)"),
                    key("More Personal Computing"), mapping("consumer-electronics", "Electronics (Consumer & Office)")),
            "GOOGL", Map.of(
                    key("Google Services"), mapping("internet-content-information", "Software (Internet)"),
                    key("Google Cloud"), mapping("software-infrastructure", "Software (System & Application)")),
            "META", Map.of(
                    key("Family of Apps"), mapping("advertising-agencies", "Advertising"),
                    key("Reality Labs"), mapping("consumer-electronics", "Electronics (Consumer & Office)")),
            "DIS", Map.of(
                    key("Entertainment"), mapping("entertainment", "Entertainment"),
                    key("Sports"), mapping("broadcasting", "Broadcasting"),
                    key("Experiences"), mapping("entertainment", "Entertainment")));

    private final SecTickerCikResolver cikResolver;
    private final SecEdgarHttpClient secClient;
    private final SecEdgarProviderProperties secProperties;
    private final ProspectusDocumentClient documentClient;
    private final ProspectusTableExtractor tableExtractor;
    private final SegmentMappingProposalService proposalService;

    public Optional<SegmentResponseDTO> discoverSegments(String ticker, CompanyDataDTO companyData) {
        String normalizedTicker = normalizeTicker(ticker);
        if (normalizedTicker.isBlank()) {
            return Optional.empty();
        }
        try {
            Optional<LatestFiling> filing = latestAnnualFiling(normalizedTicker);
            if (filing.isEmpty()) {
                return Optional.empty();
            }
            ProspectusDocument document = documentClient.fetch(filing.get().url());
            ProspectusRawTableSet tableSet = tableExtractor.extract(document.html());
            Optional<SegmentTableCandidate> candidate =
                    bestSegmentTable(normalizedTicker, tableSet, expectedRevenue(companyData));
            if (candidate.isEmpty()) {
                log.info("No validated segment revenue table discovered for {}", normalizedTicker);
                return Optional.empty();
            }
            Optional<SegmentResponseDTO> mapped = mappedSegments(normalizedTicker, candidate.get());
            mapped.ifPresent(segments -> log.info(
                    "Discovered {} segment row(s) for {} from {}",
                    segments.getSegments().size(),
                    normalizedTicker,
                    filing.get().url()));
            return mapped;
        } catch (RuntimeException exception) {
            log.warn("Segment discovery failed for {}: {}", normalizedTicker, exception.getMessage());
            return Optional.empty();
        }
    }

    private Optional<LatestFiling> latestAnnualFiling(String ticker) {
        Optional<String> cik = cikResolver.resolveCik(ticker);
        if (cik.isEmpty()) {
            return Optional.empty();
        }
        Map<String, Object> submissions = secClient.getJson(dataUrl("/submissions/CIK" + cik.get() + ".json"));
        Object filingsObject = submissions.get("filings");
        if (!(filingsObject instanceof Map<?, ?> filings)) {
            return Optional.empty();
        }
        Object recentObject = filings.get("recent");
        if (!(recentObject instanceof Map<?, ?> recent)) {
            return Optional.empty();
        }
        List<?> forms = list(recent.get("form"));
        List<?> filingDates = list(recent.get("filingDate"));
        List<?> accessions = list(recent.get("accessionNumber"));
        List<?> documents = list(recent.get("primaryDocument"));
        LatestFiling best = null;
        for (int i = 0; i < forms.size(); i++) {
            String form = string(forms.get(i));
            if (!"10-K".equals(form)) {
                continue;
            }
            if (i >= accessions.size() || i >= documents.size()) {
                continue;
            }
            String filingDate = i < filingDates.size() ? string(filingDates.get(i)) : "";
            String accession = string(accessions.get(i));
            String document = string(documents.get(i));
            if (accession.isBlank() || document.isBlank()) {
                continue;
            }
            LatestFiling candidate = new LatestFiling(filingDate, archiveUrl(cik.get(), accession, document));
            if (best == null || candidate.filingDate().compareTo(best.filingDate()) > 0) {
                best = candidate;
            }
        }
        return Optional.ofNullable(best);
    }

    private Optional<SegmentTableCandidate> bestSegmentTable(
            String ticker,
            ProspectusRawTableSet tableSet,
            Double expectedRevenue) {
        if (tableSet == null || tableSet.tables() == null) {
            return Optional.empty();
        }
        return tableSet.tables().stream()
                .map(table -> candidateFromTable(ticker, table, expectedRevenue))
                .flatMap(Optional::stream)
                .min(Comparator.comparingDouble(SegmentTableCandidate::score));
    }

    private Optional<SegmentTableCandidate> candidateFromTable(
            String ticker,
            ProspectusRawTable table,
            Double expectedRevenue) {
        int valueColumnCount = valueColumnCount(table);
        SegmentTableCandidate best = null;
        for (int columnIndex = 0; columnIndex < valueColumnCount; columnIndex++) {
            List<RowAmount> rows = rowAmounts(table, columnIndex);
            for (int i = 0; i < rows.size(); i++) {
                RowAmount total = rows.get(i);
                if (!isConsolidatedTotalLabel(total.label())) {
                    continue;
                }
                List<RowAmount> priorRows = rows.subList(0, i).stream()
                        .filter(row -> isUsableSegmentLabel(row.label()))
                        .toList();
                Optional<SegmentSelection> selection = segmentSelection(ticker, priorRows, total.amount());
                if (selection.isEmpty()) {
                    continue;
                }
                double revenueDistance = expectedRevenue != null && expectedRevenue > 0.0
                        ? relativeDistance(total.amount(), expectedRevenue)
                        : 0.0;
                if (expectedRevenue != null && expectedRevenue > 0.0 && revenueDistance > MAX_TOTAL_REVENUE_DISTANCE) {
                    continue;
                }
                double score = revenueDistance
                        + selection.get().segmentSumGap()
                        + (selection.get().curated() ? 0.0 : 0.25)
                        + (columnIndex * 0.001);
                SegmentTableCandidate candidate =
                        new SegmentTableCandidate(table.title(), total.amount(), selection.get().rows(), score);
                if (best == null || candidate.score() < best.score()) {
                    best = candidate;
                }
            }
        }
        return Optional.ofNullable(best);
    }

    private Optional<SegmentSelection> segmentSelection(String ticker, List<RowAmount> rows, double totalAmount) {
        if (rows.size() < 2) {
            return Optional.empty();
        }
        Optional<SegmentSelection> curated = curatedSegmentSelection(ticker, rows, totalAmount);
        if (curated.isPresent()) {
            return curated;
        }
        return subsetSegmentSelection(rows, totalAmount);
    }

    private Optional<SegmentSelection> curatedSegmentSelection(String ticker, List<RowAmount> rows, double totalAmount) {
        Map<String, SegmentMappingOverride> mappings = CURATED_MAPPINGS.getOrDefault(ticker, Map.of());
        if (mappings.isEmpty()) {
            return Optional.empty();
        }
        List<RowAmount> curatedRows = rows.stream()
                .filter(row -> mappings.containsKey(key(row.label())))
                .toList();
        if (curatedRows.size() < 2) {
            return Optional.empty();
        }
        double segmentSum = curatedRows.stream().mapToDouble(RowAmount::amount).sum();
        double gap = relativeDistance(segmentSum, totalAmount);
        if (gap > MAX_SEGMENT_SUM_GAP) {
            return Optional.empty();
        }
        return Optional.of(new SegmentSelection(curatedRows, gap, true));
    }

    private Optional<SegmentSelection> subsetSegmentSelection(List<RowAmount> rows, double totalAmount) {
        List<RowAmount> candidates = rows.size() > 12 ? rows.subList(rows.size() - 12, rows.size()) : rows;
        SegmentSelection best = null;
        int combinations = 1 << candidates.size();
        for (int mask = 1; mask < combinations; mask++) {
            List<RowAmount> selected = new ArrayList<>();
            double sum = 0.0;
            for (int i = 0; i < candidates.size(); i++) {
                if ((mask & (1 << i)) == 0) {
                    continue;
                }
                RowAmount row = candidates.get(i);
                selected.add(row);
                sum += row.amount();
            }
            if (selected.size() < 2 || selected.size() > 6) {
                continue;
            }
            double gap = relativeDistance(sum, totalAmount);
            if (gap > MAX_SEGMENT_SUM_GAP) {
                continue;
            }
            SegmentSelection selection = new SegmentSelection(selected, gap, false);
            if (best == null
                    || selection.segmentSumGap() < best.segmentSumGap()
                    || (selection.segmentSumGap() == best.segmentSumGap()
                            && selection.rows().size() < best.rows().size())) {
                best = selection;
            }
        }
        return Optional.ofNullable(best);
    }

    private Optional<SegmentResponseDTO> mappedSegments(String ticker, SegmentTableCandidate candidate) {
        List<SegmentMappingProposalService.SegmentMappingInput> proposalInputs = candidate.rows().stream()
                .map(row -> new SegmentMappingProposalService.SegmentMappingInput(
                        row.label(),
                        row.amount(),
                        null,
                        List.of(row.label()),
                        "reportable_segment",
                        candidate.tableTitle(),
                        List.of()))
                .toList();
        SegmentMappingProposalService.SegmentMappingProposalResult proposals =
                proposalService.proposeMappings(proposalInputs, candidate.consolidatedRevenue());
        Map<String, SegmentMappingProposalService.SegmentMappingProposal> proposalByName = proposals.proposals().stream()
                .collect(Collectors.toMap(
                        proposal -> key(proposal.name()),
                        proposal -> proposal,
                        (left, right) -> left,
                        LinkedHashMap::new));

        List<SegmentResponseDTO.Segment> segments = new ArrayList<>();
        double mappedWeight = 0.0;
        for (RowAmount row : candidate.rows()) {
            double revenueShare = round6(row.amount() / candidate.consolidatedRevenue());
            SegmentMappingOverride override = mappingOverride(ticker, row.label()).orElse(null);
            SegmentMappingProposalService.SegmentMappingProposal proposal = proposalByName.get(key(row.label()));
            String sector = override != null ? override.sectorKey() : acceptableSector(proposal);
            String industry = override != null ? override.mappedIndustry() : acceptableIndustry(proposal);
            Double score = override != null ? 1.0 : proposal == null ? null : proposal.mappingScore();
            if (sector != null && !sector.isBlank()) {
                mappedWeight += revenueShare;
            }
            segments.add(new SegmentResponseDTO.Segment(
                    sector,
                    industry,
                    List.of(row.label()),
                    score,
                    revenueShare,
                    null));
        }
        if (mappedWeight < MIN_MAPPED_COVERAGE || segments.stream().filter(segment -> segment.getSector() != null).count() < 2) {
            log.info(
                    "Ticker segment discovery did not clear mapped coverage gate: mappedCoverage={}%, table={}",
                    round2(mappedWeight * 100.0),
                    candidate.tableTitle());
        }
        return Optional.of(new SegmentResponseDTO(segments));
    }

    private Optional<SegmentMappingOverride> mappingOverride(String ticker, String label) {
        return Optional.ofNullable(CURATED_MAPPINGS.getOrDefault(ticker, Map.of()).get(key(label)));
    }

    private static String acceptableSector(SegmentMappingProposalService.SegmentMappingProposal proposal) {
        if (proposal == null || proposal.sectorKey() == null || "low".equalsIgnoreCase(proposal.mappingConfidence())) {
            return null;
        }
        return proposal.sectorKey();
    }

    private static String acceptableIndustry(SegmentMappingProposalService.SegmentMappingProposal proposal) {
        return acceptableSector(proposal) == null ? null : proposal.mappedIndustry();
    }

    private List<RowAmount> rowAmounts(ProspectusRawTable table, int columnIndex) {
        if (table == null || table.rows() == null) {
            return List.of();
        }
        List<RowAmount> rows = new ArrayList<>();
        for (ProspectusRawRow row : table.rows()) {
            Double amount = amountAt(row, columnIndex);
            String label = cleanLabel(row == null ? null : row.label());
            if (amount != null && !label.isBlank()) {
                rows.add(new RowAmount(label, amount));
            }
        }
        return rows;
    }

    private static int valueColumnCount(ProspectusRawTable table) {
        if (table == null || table.rows() == null) {
            return 1;
        }
        return table.rows().stream()
                .filter(Objects::nonNull)
                .map(ProspectusRawRow::cells)
                .filter(Objects::nonNull)
                .mapToInt(List::size)
                .max()
                .orElse(1);
    }

    private static Double amountAt(ProspectusRawRow row, int columnIndex) {
        if (row == null || row.cells() == null) {
            return null;
        }
        if (columnIndex < 0 || columnIndex >= row.cells().size()) {
            return null;
        }
        ProspectusRawCell cell = row.cells().get(columnIndex);
        Double value = cell == null ? null : cell.normalizedValue();
        return value != null && Double.isFinite(value) && value > 0.0 ? value : null;
    }

    private Double expectedRevenue(CompanyDataDTO companyData) {
        FinancialDataDTO financial = companyData == null ? null : companyData.getFinancialDataDTO();
        if (financial == null) {
            return null;
        }
        if (positive(financial.getRevenueLTM())) {
            return financial.getRevenueLTM();
        }
        if (positive(financial.getRevenueTTM())) {
            return financial.getRevenueTTM();
        }
        return null;
    }

    private static boolean positive(Double value) {
        return value != null && Double.isFinite(value) && value > 0.0;
    }

    private static boolean isConsolidatedTotalLabel(String label) {
        String key = key(label);
        if (key.equals("consolidated")
                || key.equals("total")
                || key.equals("totalrevenue")
                || key.equals("totalrevenues")
                || key.equals("totalnetsales")
                || key.equals("totalsegmentrevenues")
                || key.equals("consolidatednetrevenue")
                || key.equals("consolidatednetsales")) {
            return true;
        }
        return key.startsWith("consolidated") && !nonRevenueTotal(label);
    }

    private static boolean isUsableSegmentLabel(String label) {
        String key = key(label);
        if (key.isBlank() || isConsolidatedTotalLabel(label) || nonRevenueTotal(label)) {
            return false;
        }
        return !key.contains("percentage")
                && !key.contains("weightedaverage")
                && !key.contains("interestrate")
                && !key.contains("operatingactivities")
                && !key.contains("investingactivities")
                && !key.contains("financingactivities");
    }

    private static boolean nonRevenueTotal(String label) {
        String key = key(label);
        return key.contains("expense")
                || key.contains("expenses")
                || key.contains("asset")
                || key.contains("liabilit")
                || key.contains("debt")
                || key.contains("income")
                || key.contains("cashflow")
                || key.contains("cashprovided");
    }

    private static double relativeDistance(double actual, double expected) {
        if (expected == 0.0) {
            return Double.POSITIVE_INFINITY;
        }
        return Math.abs(actual - expected) / Math.abs(expected);
    }

    private String dataUrl(String path) {
        return trimTrailingSlash(secProperties.getDataBaseUrl()) + path;
    }

    private String archiveUrl(String cik, String accession, String document) {
        String cikNoLeadingZeros = cik.replaceFirst("^0+", "");
        String accessionNoDashes = accession.replace("-", "");
        return trimTrailingSlash(secProperties.getSecBaseUrl())
                + "/Archives/edgar/data/"
                + cikNoLeadingZeros
                + "/"
                + accessionNoDashes
                + "/"
                + document;
    }

    private static List<?> list(Object value) {
        return value instanceof List<?> list ? list : List.of();
    }

    private static String string(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private static String cleanLabel(String label) {
        return label == null ? "" : label.trim().replaceAll("\\s+", " ");
    }

    private static String normalizeTicker(String ticker) {
        return ticker == null ? "" : ticker.trim().toUpperCase(Locale.ROOT).replace('.', '-');
    }

    private static String key(String value) {
        return value == null ? "" : value.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]+", "");
    }

    private static String trimTrailingSlash(String value) {
        if (value == null || value.isBlank()) {
            return "";
        }
        return value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }

    private static SegmentMappingOverride mapping(String sectorKey, String mappedIndustry) {
        return new SegmentMappingOverride(sectorKey, mappedIndustry);
    }

    private static double round2(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    private static double round6(double value) {
        return Math.round(value * 1_000_000.0) / 1_000_000.0;
    }

    private record LatestFiling(String filingDate, String url) {
    }

    private record RowAmount(String label, double amount) {
    }

    private record SegmentTableCandidate(
            String tableTitle,
            double consolidatedRevenue,
            List<RowAmount> rows,
            double score) {
    }

    private record SegmentSelection(List<RowAmount> rows, double segmentSumGap, boolean curated) {
    }

    private record SegmentMappingOverride(String sectorKey, String mappedIndustry) {
    }
}
