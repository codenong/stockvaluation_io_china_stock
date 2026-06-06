package io.stockvaluation.provider.prospectus;

import io.stockvaluation.provider.SourceProvenance;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeFormatterBuilder;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Component
public class ProspectusFinancialExtractor {

    private static final Pattern FORM_PATTERN = Pattern.compile("\\bForm\\s+((?:S-1/A)|(?:S-1)|(?:424B[345]))\\b", Pattern.CASE_INSENSITIVE);
    private static final Pattern STANDALONE_FORM_PATTERN = Pattern.compile("\\b((?:S-1/A)|(?:S-1)|(?:424B[345]))\\b", Pattern.CASE_INSENSITIVE);
    private static final Pattern CIK_PATTERN = Pattern.compile("\\bCIK\\s+([0-9]{7,10})\\b", Pattern.CASE_INSENSITIVE);
    private static final Pattern ACCESSION_PATTERN = Pattern.compile("\\bAccession\\s+([0-9]{10}-[0-9]{2}-[0-9]{6})\\b", Pattern.CASE_INSENSITIVE);
    private static final Pattern FILING_DATE_PATTERN = Pattern.compile("\\bFiling Date\\s+([0-9]{4}-[0-9]{2}-[0-9]{2})\\b", Pattern.CASE_INSENSITIVE);
    private static final Pattern AS_FILED_DATE_PATTERN = Pattern.compile("\\bAs filed\\b.{0,140}\\bon\\s+([A-Z][a-z]+\\s+[0-9]{1,2},\\s+[0-9]{4})", Pattern.CASE_INSENSITIVE);
    private static final Pattern SEC_ARCHIVE_URL_PATTERN = Pattern.compile("/data/([0-9]{1,10})/([0-9]{18})/");
    private static final Pattern NUMBER_TOKEN_PATTERN = Pattern.compile("([0-9][0-9,]*(?:\\.[0-9]+)?)");
    private static final Pattern OFFERING_PRICE_PATTERN = Pattern.compile("offering price[^$]{0,80}\\$\\s*([0-9,.]+)", Pattern.CASE_INSENSITIVE);
    private static final Pattern POST_OFFERING_SHARES_PATTERN = Pattern.compile("([0-9][0-9,]+)\\s+shares[^.]{0,120}(?:outstanding|after this offering|pro forma)", Pattern.CASE_INSENSITIVE);
    private static final DateTimeFormatter SEC_TEXT_DATE = new DateTimeFormatterBuilder()
            .parseCaseInsensitive()
            .appendPattern("MMMM d, yyyy")
            .toFormatter(Locale.US);

    public ProspectusFinancialPacket extract(ProspectusDocument document, ProspectusRawTableSet tableSet) {
        Document parsed = Jsoup.parse(document.html());
        String text = ProspectusTableExtractor.clean(parsed.text());
        String filingDate = filingDate(text);
        String periodEnd = latestPeriodEnd(tableSet);
        SourceProvenance provenance = SourceProvenance.primaryFiling(
                "sec-edgar-prospectus",
                filingDate,
                periodEnd);

        ProspectusFinancialPacket packet = new ProspectusFinancialPacket();
        packet.setSourceUrl(document.sourceUrl());
        packet.setSourceProvenance(provenance);
        packet.setReviewStatus("review_required");
        packet.setCompany(new ProspectusCompanyIdentity(
                legalName(parsed),
                null,
                "United States",
                "USD",
                null));
        String form = form(text, parsed.title());
        packet.setFiling(new ProspectusFilingMetadata(
                form,
                firstPresent(firstMatch(CIK_PATTERN, text), cikFromUrl(document.sourceUrl())),
                firstPresent(firstMatch(ACCESSION_PATTERN, text), accessionFromUrl(document.sourceUrl())),
                filingDate));
        packet.setOffering(offeringFacts(text));

        for (ProspectusRawTable table : tableSet.tables()) {
            String title = lower(table.title());
            if (isIncomeTable(title)) {
                extractIncomeStatement(packet, table, provenance);
            } else if (isBalanceTable(title) || isDebtTable(title)) {
                extractBalanceSheet(packet, table, provenance);
            }
            if (isCashFlowOrCapexTable(title)) {
                extractCashFlowOrCapex(packet, table, provenance);
            }
            if (isOfferingOrCapitalizationTable(title)) {
                extractOfferingAndShares(packet, table, provenance);
            }
            if (title.contains("segment") || title.contains("business line")) {
                extractSegments(packet, table, provenance);
            }
        }

        if (!packet.getShareCounts().isEmpty()) {
            packet.getOffering().setPostOfferingShares(packet.getShareCounts().get(0).getNormalizedValue());
        }
        if (!packet.getShareCounts().isEmpty()) {
            packet.getOffering().setShareCountBasis(packet.getShareCounts().get(0).getBasis());
        }
        addExtractionIssues(packet);
        return packet;
    }

    private static void extractIncomeStatement(
            ProspectusFinancialPacket packet,
            ProspectusRawTable table,
            SourceProvenance provenance) {
        for (ProspectusRawRow row : table.rows()) {
            String canonical = incomeField(row.label());
            if (canonical == null) {
                continue;
            }
            boolean firstAcceptedValue = true;
            for (int i = 0; i < row.cells().size() && i < table.columns().size(); i++) {
                if (!isUsableIncomeColumn(table, i)) {
                    continue;
                }
                ProspectusRawCell cell = row.cells().get(i);
                if (cell.normalizedValue() == null) {
                    continue;
                }
                String field = firstAcceptedValue ? canonical : "revenue".equals(canonical) ? "prior_revenue" : canonical;
                packet.getFinancials().getIncomeStatement().add(fact(
                        field,
                        row.label(),
                        table.columns().get(i),
                        table,
                        cell,
                        provenance));
                firstAcceptedValue = false;
            }
        }
    }

    private static void extractBalanceSheet(
            ProspectusFinancialPacket packet,
            ProspectusRawTable table,
            SourceProvenance provenance) {
        for (ProspectusRawRow row : table.rows()) {
            String canonical = balanceField(row.label());
            if (canonical == null || row.cells().isEmpty()) {
                continue;
            }
            ValueCell value = firstUsableFinancialCell(table, row);
            if (value == null) {
                continue;
            }
            packet.getFinancials().getBalanceSheet().add(fact(
                    canonical,
                    row.label(),
                    value.columnLabel(),
                    table,
                    value.cell(),
                    provenance));
        }
    }

    private static void extractCashFlowOrCapex(
            ProspectusFinancialPacket packet,
            ProspectusRawTable table,
            SourceProvenance provenance) {
        for (ProspectusRawRow row : table.rows()) {
            String canonical = cashFlowOrCapexField(row.label());
            if (canonical == null || row.cells().isEmpty()) {
                continue;
            }
            ValueCell value = firstUsableSegmentCell(table, row);
            if (value == null) {
                continue;
            }
            packet.getFinancials().getCashFlowOrCapex().add(fact(
                    canonical,
                    row.label(),
                    value.columnLabel(),
                    table,
                    value.cell(),
                    provenance));
        }
    }

    private static void extractOfferingAndShares(
            ProspectusFinancialPacket packet,
            ProspectusRawTable table,
            SourceProvenance provenance) {
        Map<String, ShareRow> postOfferingClassShares = new LinkedHashMap<>();
        for (ProspectusRawRow row : table.rows()) {
            String label = row.label();
            String lower = lower(label);
            String rowText = rowText(row);
            Double value = firstNumberInText(rowText);
            if (value == null) {
                continue;
            }
            if (packet.getOffering().getSharesOffered() == null
                    && lower.contains("common stock offered")) {
                packet.getOffering().setSharesOffered(value);
            }
            if (packet.getOffering().getNetProceeds() == null
                    && lower.contains("net proceeds")
                    && (lower.contains("to us") || lower.contains("from this offering"))) {
                Double proceeds = firstNormalizedValue(row);
                if (proceeds != null && proceeds > 0.0) {
                    packet.getOffering().setNetProceeds(proceeds);
                    packet.getOffering().setProceedsBasis("net_proceeds_disclosed");
                }
            }
            if (lower.contains("common stock outstanding") && lower.contains("after this offering")) {
                if (lower.contains("class a")) {
                    postOfferingClassShares.put("class_a", new ShareRow(label, value));
                } else if (lower.contains("class b")) {
                    postOfferingClassShares.put("class_b", new ShareRow(label, value));
                } else if (packet.getShareCounts().isEmpty()) {
                    addShareCount(packet, table, provenance, label, value);
                }
            }
        }
        if (packet.getShareCounts().isEmpty() && !postOfferingClassShares.isEmpty()) {
            double total = postOfferingClassShares.values().stream()
                    .mapToDouble(ShareRow::value)
                    .sum();
            String label = postOfferingClassShares.values().stream()
                    .map(ShareRow::label)
                    .reduce((left, right) -> left + " + " + right)
                    .orElse("Common stock outstanding immediately after this offering");
            addShareCount(packet, table, provenance, label, total);
        }
    }

    private static void addShareCount(
            ProspectusFinancialPacket packet,
            ProspectusRawTable table,
            SourceProvenance provenance,
            String label,
            Double value) {
        ProspectusShareCountFact share = new ProspectusShareCountFact();
        share.setBasis("pro_forma_post_offering");
        share.setSourceRowLabel(label);
        share.setOriginalColumnLabel(firstColumn(table));
        share.setTableTitle(table.title());
        share.setRawValue(String.valueOf(value));
        share.setNormalizedValue(value);
        share.setConfidence(0.9);
        share.setSourceProvenance(provenance);
        packet.getShareCounts().add(share);
    }

    private static void extractSegments(
            ProspectusFinancialPacket packet,
            ProspectusRawTable table,
            SourceProvenance provenance) {
        List<ProspectusSegmentFact> segments = new ArrayList<>();
        for (ProspectusRawRow row : table.rows()) {
            if (!isTopLevelSegmentRow(table, row)) {
                continue;
            }
            ValueCell value = firstUsableIncomeCell(table, row);
            if (value == null) {
                continue;
            }
            ProspectusSegmentFact segment = new ProspectusSegmentFact();
            segment.setSegmentName(row.label());
            segment.setRevenueAmount(value.cell().normalizedValue());
            segment.setSourceRowLabel(row.label());
            segment.setTableTitle(table.title());
            segment.setPeriodEnd(periodEnd(value.columnLabel()));
            segment.setSourceProvenance(provenance);
            applySegmentMapping(segment);
            segments.add(segment);
        }
        double total = segments.stream()
                .map(ProspectusSegmentFact::getRevenueAmount)
                .filter(Objects::nonNull)
                .mapToDouble(Double::doubleValue)
                .sum();
        if (total > 0) {
            segments.forEach(segment -> segment.setRevenueWeight(segment.getRevenueAmount() / total));
        }
        packet.getSegments().addAll(segments);
    }

    private static ProspectusFact fact(
            String canonicalField,
            String rowLabel,
            String columnLabel,
            ProspectusRawTable table,
            ProspectusRawCell cell,
            SourceProvenance provenance) {
        ProspectusFact fact = new ProspectusFact();
        fact.setCanonicalField(canonicalField);
        fact.setSourceRowLabel(rowLabel);
        fact.setOriginalColumnLabel(columnLabel);
        fact.setTableTitle(table.title());
        fact.setPeriodEnd(periodEnd(columnLabel));
        fact.setPeriodType(columnLabel != null && columnLabel.toLowerCase(Locale.ROOT).contains("year ended")
                ? "annual"
                : "point_in_time");
        fact.setUnit(table.currency());
        fact.setScale(table.scale());
        fact.setRawValue(cell.rawValue());
        fact.setNormalizedValue(cell.normalizedValue());
        fact.setSourceAnchor(table.sourceAnchor());
        fact.setConfidence(0.9);
        fact.setSourceProvenance(provenance);
        return fact;
    }

    private static ProspectusOfferingFacts offeringFacts(String text) {
        ProspectusOfferingFacts offering = new ProspectusOfferingFacts();
        Double offeringPrice = parseFirstNumber(OFFERING_PRICE_PATTERN, text);
        offering.setOfferingPrice(offeringPrice);
        offering.setOfferingPriceBasis(offeringPrice == null ? null : "offering_price");
        Double shares = parseFirstNumber(POST_OFFERING_SHARES_PATTERN, text);
        offering.setPostOfferingShares(shares);
        offering.setShareCountBasis(shares == null ? null : "pro_forma_post_offering");
        return offering;
    }

    private static void applySegmentMapping(ProspectusSegmentFact segment) {
        String name = lower(segment.getSegmentName());
        if (name.contains("launch") || name.contains("spacecraft") || name.contains("aerospace")) {
            segment.setSectorKey("aerospace-defense");
            segment.setMappedIndustry("Aerospace/Defense");
            segment.setMappingConfidence("medium");
        } else if (name.equals("space")) {
            segment.setSectorKey("aerospace-defense");
            segment.setMappedIndustry("Aerospace/Defense");
            segment.setMappingConfidence("medium");
        } else if (name.contains("starlink") || name.contains("connectivity") || name.contains("telecom")) {
            segment.setSectorKey("telecom-services");
            segment.setMappedIndustry("Telecom. Services");
            segment.setMappingConfidence("medium");
        } else {
            segment.setSectorKey(null);
            segment.setMappedIndustry(null);
            segment.setMappingConfidence("low");
        }
    }

    private static String incomeField(String label) {
        String lower = lower(label);
        if (lower.contains("segment")) {
            return null;
        }
        if (lower.matches(".*\\brevenue\\b.*")) {
            return "revenue";
        }
        if (lower.contains("operating income")
                || lower.contains("operating loss")
                || lower.contains("income (loss) from operations")) {
            return "operating_income";
        }
        if (lower.contains("research") && lower.contains("development")) {
            return "research_and_development";
        }
        return null;
    }

    private static String balanceField(String label) {
        String lower = lower(label);
        if (lower.contains("cash") && (lower.contains("equivalent") || lower.contains("short-term"))) {
            return "cash_and_short_term_investments";
        }
        if (lower.equals("total debt") || (lower.contains("total debt") && !lower.contains("finance leases"))) {
            return "total_debt";
        }
        if ((lower.contains("stockholders") || lower.contains("shareholders")) && lower.contains("equity")) {
            return "book_value_equity";
        }
        return null;
    }

    private static String cashFlowOrCapexField(String label) {
        String lower = lower(label);
        if (lower.contains("net cash provided by operating activities")
                || lower.contains("net cash from operating activities")) {
            return "operating_cash_flow";
        }
        if (lower.contains("total capital expenditures")
                || lower.equals("capital expenditures")) {
            return "capital_expenditures";
        }
        return null;
    }

    private static String periodEnd(String label) {
        if (label == null) {
            return null;
        }
        Matcher monthMatcher = Pattern.compile("\\b(january|february|march|april|may|june|july|august|september|october|november|december)\\s+([0-9]{1,2}),?\\s+(20[0-9]{2})\\b", Pattern.CASE_INSENSITIVE)
                .matcher(label);
        if (monthMatcher.find()) {
            int month = switch (monthMatcher.group(1).toLowerCase(Locale.ROOT)) {
                case "january" -> 1;
                case "february" -> 2;
                case "march" -> 3;
                case "april" -> 4;
                case "may" -> 5;
                case "june" -> 6;
                case "july" -> 7;
                case "august" -> 8;
                case "september" -> 9;
                case "october" -> 10;
                case "november" -> 11;
                case "december" -> 12;
                default -> 12;
            };
            return "%s-%02d-%02d".formatted(monthMatcher.group(3), month, Integer.parseInt(monthMatcher.group(2)));
        }
        Matcher matcher = Pattern.compile("(20[0-9]{2})").matcher(label);
        String lower = lower(label);
        if ((lower.contains("year ended") || label.matches("\\s*20[0-9]{2}\\s*")) && matcher.find()) {
            return matcher.group(1) + "-12-31";
        }
        return null;
    }

    private static String latestPeriodEnd(ProspectusRawTableSet tableSet) {
        return tableSet.tables().stream()
                .flatMap(table -> table.columns().stream())
                .map(ProspectusFinancialExtractor::periodEnd)
                .filter(Objects::nonNull)
                .max(Comparator.naturalOrder())
                .orElse(null);
    }

    private static String legalName(Document parsed) {
        String h1 = parsed.select("h1").stream()
                .map(element -> ProspectusTableExtractor.clean(element.text()))
                .filter(text -> !text.isBlank())
                .findFirst()
                .orElse(null);
        return h1 == null ? "Prospectus issuer" : h1;
    }

    private static String firstColumn(ProspectusRawTable table) {
        return table.columns().isEmpty() ? null : table.columns().get(0);
    }

    private static String firstMatch(Pattern pattern, String text) {
        Matcher matcher = pattern.matcher(text == null ? "" : text);
        return matcher.find() ? matcher.group(1) : null;
    }

    private static Double parseFirstNumber(Pattern pattern, String text) {
        String match = firstMatch(pattern, text);
        return ProspectusTableExtractor.parseNumber(match);
    }

    private static String firstPresent(String first, String second) {
        return first == null || first.isBlank() ? second : first;
    }

    private static String form(String text, String title) {
        String source = (title == null ? "" : title) + " " + (text == null ? "" : text);
        String standalone = firstMatch(STANDALONE_FORM_PATTERN, source);
        if ("S-1/A".equalsIgnoreCase(standalone)) {
            return "S-1/A";
        }
        return firstPresent(firstMatch(FORM_PATTERN, source), standalone);
    }

    private static String filingDate(String text) {
        String exact = firstMatch(FILING_DATE_PATTERN, text);
        if (exact != null) {
            return exact;
        }
        String asFiled = firstMatch(AS_FILED_DATE_PATTERN, text);
        if (asFiled == null) {
            return null;
        }
        try {
            return LocalDate.parse(asFiled, SEC_TEXT_DATE).toString();
        } catch (DateTimeParseException ignored) {
            return null;
        }
    }

    private static String cikFromUrl(String sourceUrl) {
        Matcher matcher = SEC_ARCHIVE_URL_PATTERN.matcher(sourceUrl == null ? "" : sourceUrl);
        if (!matcher.find()) {
            return null;
        }
        return String.format("%010d", Long.parseLong(matcher.group(1)));
    }

    private static String accessionFromUrl(String sourceUrl) {
        Matcher matcher = SEC_ARCHIVE_URL_PATTERN.matcher(sourceUrl == null ? "" : sourceUrl);
        if (!matcher.find()) {
            return null;
        }
        String compact = matcher.group(2);
        return compact.substring(0, 10) + "-" + compact.substring(10, 12) + "-" + compact.substring(12);
    }

    private static Double firstNumberInText(String text) {
        Matcher matcher = NUMBER_TOKEN_PATTERN.matcher(text == null ? "" : text);
        return matcher.find() ? ProspectusTableExtractor.parseNumber(matcher.group(1)) : null;
    }

    private static Double firstNormalizedValue(ProspectusRawRow row) {
        if (row == null || row.cells() == null) {
            return null;
        }
        return row.cells().stream()
                .map(ProspectusRawCell::normalizedValue)
                .filter(Objects::nonNull)
                .findFirst()
                .orElse(null);
    }

    private static String rowText(ProspectusRawRow row) {
        StringBuilder builder = new StringBuilder(row.label());
        for (ProspectusRawCell cell : row.cells()) {
            if (cell.rawValue() != null && !cell.rawValue().isBlank()) {
                builder.append(' ').append(cell.rawValue());
            }
        }
        return builder.toString();
    }

    private static boolean isIncomeTable(String title) {
        return title.contains("statement") && title.contains("operation");
    }

    private static boolean isBalanceTable(String title) {
        return title.contains("balance sheet");
    }

    private static boolean isDebtTable(String title) {
        return title.contains("debt schedule");
    }

    private static boolean isCashFlowOrCapexTable(String title) {
        return title.contains("cash flow") || title.contains("capital expenditure");
    }

    private static boolean isOfferingOrCapitalizationTable(String title) {
        return title.contains("offering facts") || title.contains("capitalization");
    }

    private static boolean shouldSkipInterimColumn(ProspectusRawTable table, int index) {
        if (table.columns().stream().noneMatch(column -> lower(column).contains("year ended"))) {
            return false;
        }
        return index < table.columns().size()
                && lower(table.columns().get(index)).contains("three months");
    }

    private static boolean isUsableIncomeColumn(ProspectusRawTable table, int index) {
        return hasScale(table)
                && index < table.columns().size()
                && periodEnd(table.columns().get(index)) != null
                && isAnnualIncomeColumn(table.columns().get(index))
                && !isComparisonColumn(table.columns().get(index))
                && !shouldSkipInterimColumn(table, index);
    }

    private static boolean isAnnualIncomeColumn(String column) {
        String lower = lower(column);
        return lower.contains("year ended") || column.matches("\\s*20[0-9]{2}\\s*");
    }

    private static boolean isUsableFinancialColumn(ProspectusRawTable table, int index) {
        return hasScale(table)
                && index < table.columns().size()
                && periodEnd(table.columns().get(index)) != null
                && !isComparisonColumn(table.columns().get(index));
    }

    private static boolean isComparisonColumn(String column) {
        String lower = lower(column);
        return lower.contains("change") || lower.contains(" vs.") || lower.contains(" vs ");
    }

    private static boolean hasScale(ProspectusRawTable table) {
        return table.scale() != null && !table.scale().isBlank();
    }

    private static ValueCell firstUsableIncomeCell(ProspectusRawTable table, ProspectusRawRow row) {
        for (int i = 0; i < row.cells().size() && i < table.columns().size(); i++) {
            if (!isUsableIncomeColumn(table, i)) {
                continue;
            }
            ProspectusRawCell cell = row.cells().get(i);
            if (cell.normalizedValue() != null) {
                return new ValueCell(cell, table.columns().get(i));
            }
        }
        return null;
    }

    private static ValueCell firstUsableFinancialCell(ProspectusRawTable table, ProspectusRawRow row) {
        for (int i = 0; i < row.cells().size() && i < table.columns().size(); i++) {
            if (!isUsableFinancialColumn(table, i)) {
                continue;
            }
            ProspectusRawCell cell = row.cells().get(i);
            if (cell.normalizedValue() != null) {
                return new ValueCell(cell, table.columns().get(i));
            }
        }
        return null;
    }

    private static boolean isTopLevelSegmentRow(ProspectusRawTable table, ProspectusRawRow row) {
        String label = lower(row.label());
        boolean hasTopLevelRows = table.rows().stream()
                .map(ProspectusRawRow::label)
                .map(ProspectusFinancialExtractor::lower)
                .anyMatch("space"::equals)
                && table.rows().stream()
                        .map(ProspectusRawRow::label)
                        .map(ProspectusFinancialExtractor::lower)
                        .anyMatch("connectivity"::equals)
                && table.rows().stream()
                        .map(ProspectusRawRow::label)
                        .map(ProspectusFinancialExtractor::lower)
                        .anyMatch("ai"::equals);
        if (hasTopLevelRows) {
            return (label.equals("space") || label.equals("connectivity") || label.equals("ai"))
                    && firstUsableSegmentCell(table, row) != null;
        }
        if ("segment revenue".equalsIgnoreCase(table.title())) {
            return false;
        }
        return !row.cells().isEmpty() && firstUsableSegmentCell(table, row) != null;
    }

    private static ValueCell firstUsableSegmentCell(ProspectusRawTable table, ProspectusRawRow row) {
        for (int i = 0; i < row.cells().size() && i < table.columns().size(); i++) {
            if (periodEnd(table.columns().get(i)) == null
                    || isComparisonColumn(table.columns().get(i))
                    || shouldSkipInterimColumn(table, i)) {
                continue;
            }
            ProspectusRawCell cell = row.cells().get(i);
            if (cell.normalizedValue() != null) {
                return new ValueCell(cell, table.columns().get(i));
            }
        }
        return null;
    }

    private static void addExtractionIssues(ProspectusFinancialPacket packet) {
        if (packet.getExtractionIssues() == null) {
            packet.setExtractionIssues(new ArrayList<>());
        }
        ProspectusFilingMetadata filing = packet.getFiling();
        if (isBlank(filing == null ? null : filing.getForm())) {
            addIssue(packet, "missing_form", "blocking", "filing.form", "SEC prospectus form could not be extracted.");
        }
        if (isBlank(filing == null ? null : filing.getCik())) {
            addIssue(packet, "missing_cik", "warning", "filing.cik", "SEC CIK could not be extracted from the filing or URL.");
        }
        if (isBlank(filing == null ? null : filing.getAccession())) {
            addIssue(packet, "missing_accession", "warning", "filing.accession", "SEC accession number could not be extracted from the filing or URL.");
        }
        if (isBlank(filing == null ? null : filing.getFilingDate())) {
            addIssue(packet, "missing_filing_date", "warning", "filing.filingDate", "SEC filing date could not be extracted.");
        }
        if (packet.getFinancials() == null || packet.getFinancials().allFacts().isEmpty()) {
            addIssue(packet, "parser_no_core_facts", "blocking", "financials", "No reviewable financial facts were extracted from the filing.");
        }
        if (!hasFact(packet, "revenue")) {
            addIssue(packet, "missing_revenue", "blocking", "financials.incomeStatement", "Revenue is required for prospectus valuation.");
        }
        if (!hasFact(packet, "operating_income")) {
            addIssue(packet, "missing_operating_income", "warning", "financials.incomeStatement", "Operating income or loss was not extracted.");
        }
        if (!hasFact(packet, "cash_and_short_term_investments")) {
            addIssue(packet, "missing_cash", "warning", "financials.balanceSheet", "Cash and cash equivalents were not extracted.");
        }
        if (!hasFact(packet, "total_debt")) {
            addIssue(packet, "missing_debt", "warning", "financials.balanceSheet", "Debt was not extracted.");
        }
        if (packet.getOffering() == null || packet.getOffering().getOfferingPrice() == null) {
            addIssue(packet, "missing_offering_price", "blocking", "offering.offeringPrice", "Offering price is required for prospectus valuation.");
        }
        if (packet.getShareCounts() == null || packet.getShareCounts().isEmpty()) {
            addIssue(packet, "missing_share_count", "blocking", "shareCounts", "A clear post-offering share count was not extracted.");
        }
        if (missingUnitsOrScale(packet)) {
            addIssue(packet, "missing_units_or_scale", "blocking", "financials", "Mapped financial facts must include unit and scale.");
        }
        if (packet.getSourceProvenance() == null || isBlank(packet.getSourceProvenance().getPeriodEnd())) {
            addIssue(packet, "missing_source_period", "blocking", "sourceProvenance.periodEnd", "No source financial period was extracted.");
        }
    }

    private static boolean hasFact(ProspectusFinancialPacket packet, String canonicalField) {
        return packet.getFinancials() != null
                && packet.getFinancials().allFacts().stream()
                        .anyMatch(fact -> canonicalField.equals(fact.getCanonicalField())
                                && fact.getNormalizedValue() != null
                                && Double.isFinite(fact.getNormalizedValue()));
    }

    private static boolean missingUnitsOrScale(ProspectusFinancialPacket packet) {
        if (packet.getFinancials() == null || packet.getFinancials().allFacts().isEmpty()) {
            return true;
        }
        return packet.getFinancials().allFacts().stream()
                .anyMatch(fact -> isBlank(fact.getUnit()) || isBlank(fact.getScale()));
    }

    private static void addIssue(
            ProspectusFinancialPacket packet,
            String code,
            String severity,
            String field,
            String message) {
        boolean exists = packet.getExtractionIssues().stream().anyMatch(issue -> code.equals(issue.code()));
        if (!exists) {
            packet.getExtractionIssues().add(new ProspectusExtractionIssue(code, severity, message, field));
        }
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private static String lower(String text) {
        return text == null ? "" : text.toLowerCase(Locale.ROOT);
    }

    private record ValueCell(ProspectusRawCell cell, String columnLabel) {
    }

    private record ShareRow(String label, double value) {
    }
}
