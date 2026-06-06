package io.stockvaluation.provider.prospectus;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

@Component
public class ProspectusTableExtractor {

    public ProspectusRawTableSet extract(String html) {
        Document document = Jsoup.parse(html == null ? "" : html);
        List<ProspectusRawTable> tables = new ArrayList<>();
        int index = 1;
        for (Element table : document.select("table")) {
            ProspectusRawTable rawTable = toRawTable(table, index);
            if (!rawTable.rows().isEmpty()) {
                tables.add(rawTable);
            }
            index++;
        }
        return new ProspectusRawTableSet(tables);
    }

    private ProspectusRawTable toRawTable(Element table, int index) {
        String tableText = clean(table.text());
        String contextText = nearbyContext(table);
        String title = tableTitle(table, tableText, contextText);
        String scale = firstPresent(detectScale(title + " " + tableText), detectScale(contextText));
        String currency = detectCurrency(title + " " + tableText + " " + contextText);
        Elements rowElements = table.select("tr");
        List<List<String>> expandedRows = rowElements.stream()
                .map(ProspectusTableExtractor::expandedCells)
                .filter(cells -> cells.stream().anyMatch(cell -> !cell.isBlank()))
                .toList();
        List<List<String>> headerRows = new ArrayList<>();
        Set<Integer> valueColumnIndexes = new LinkedHashSet<>();
        boolean dataStarted = false;
        for (List<String> cells : expandedRows) {
            if (!dataStarted && looksLikeHeader(cells)) {
                if (!isScaleOnlyRow(cells)) {
                    headerRows.add(cells);
                }
                continue;
            }
            dataStarted = true;
            for (int i = 1; i < cells.size(); i++) {
                if (normalize(cells.get(i), scale) != null) {
                    valueColumnIndexes.add(i - 1);
                }
            }
        }
        if (valueColumnIndexes.isEmpty()) {
            valueColumnIndexes.add(0);
        }
        List<Integer> valueIndexes = new ArrayList<>(valueColumnIndexes);
        List<String> columns = valueIndexes.stream()
                .map(columnIndex -> columnLabel(headerRows, columnIndex))
                .toList();

        List<ProspectusRawRow> rows = new ArrayList<>();
        for (Element rowElement : rowElements) {
            List<String> cells = expandedCells(rowElement);
            if (cells.isEmpty() || cells.stream().allMatch(String::isBlank)) {
                continue;
            }
            if (looksLikeHeader(cells)) {
                continue;
            }
            String label = cleanLabel(cells.get(0));
            if (label.isBlank()) {
                continue;
            }
            List<ProspectusRawCell> valueCells = new ArrayList<>();
            for (Integer valueIndex : valueIndexes) {
                int cellIndex = valueIndex + 1;
                String raw = cellIndex < cells.size() ? clean(cells.get(cellIndex)) : "";
                valueCells.add(new ProspectusRawCell(raw, normalize(raw, scale)));
            }
            if (!valueCells.isEmpty()) {
                rows.add(new ProspectusRawRow(label, valueCells));
            }
        }
        return new ProspectusRawTable(
                title,
                currency,
                scale,
                columns,
                rows,
                "table-" + index);
    }

    private static List<String> expandedCells(Element rowElement) {
        List<String> cells = new ArrayList<>();
        for (Element cell : rowElement.select("th,td")) {
            String text = clean(cell.text());
            int colspan = parseColspan(cell);
            for (int i = 0; i < colspan; i++) {
                cells.add(text);
            }
        }
        return cells;
    }

    private static int parseColspan(Element cell) {
        String raw = cell.attr("colspan");
        if (raw == null || raw.isBlank()) {
            return 1;
        }
        try {
            return Math.max(1, Math.min(12, Integer.parseInt(raw)));
        } catch (NumberFormatException ignored) {
            return 1;
        }
    }

    private static boolean looksLikeHeader(List<String> cells) {
        if (cells.size() < 2) {
            return false;
        }
        String first = clean(cells.get(0));
        if (first.isBlank()) {
            return true;
        }
        String lower = first.toLowerCase(Locale.ROOT);
        return lower.startsWith("(in ") || lower.contains("unaudited");
    }

    private static boolean isScaleOnlyRow(List<String> cells) {
        String first = cells.isEmpty() ? "" : clean(cells.get(0)).toLowerCase(Locale.ROOT);
        return first.startsWith("(in ") || first.contains("unaudited");
    }

    private static String columnLabel(List<List<String>> headerRows, int columnIndex) {
        List<String> parts = new ArrayList<>();
        int cellIndex = columnIndex + 1;
        for (List<String> headerRow : headerRows) {
            if (cellIndex >= headerRow.size()) {
                continue;
            }
            String part = clean(headerRow.get(cellIndex));
            if (part.isBlank() || parts.contains(part)) {
                continue;
            }
            parts.add(part);
        }
        String label = clean(String.join(" ", parts))
                .replaceAll(",\\s+", ", ")
                .replaceAll("\\s+,", ",");
        return label.isBlank() ? "Value" : label;
    }

    private static String tableTitle(Element table, String tableText, String contextText) {
        Element caption = table.selectFirst("caption");
        if (caption != null && !clean(caption.text()).isBlank()) {
            return clean(caption.text());
        }
        String tableTitle = inferTableTitle(tableText);
        if (!"Untitled prospectus table".equals(tableTitle)) {
            return tableTitle;
        }
        Element previous = table.previousElementSibling();
        while (previous != null) {
            String tag = previous.tagName().toLowerCase(Locale.ROOT);
            if (tag.matches("h[1-6]")) {
                return clean(previous.text());
            }
            previous = previous.previousElementSibling();
        }
        return inferTableTitle(contextText);
    }

    private static String inferTableTitle(String tableText) {
        String lower = cleanLabel(tableText).toLowerCase(Locale.ROOT);
        if (lower.contains("class a common stock offered by us")
                && lower.contains("common stock outstanding immediately after this offering")) {
            return "Prospectus Summary Offering Facts";
        }
        if (lower.contains("revenue") && lower.contains("income (loss) from operations")) {
            return "Consolidated Statements of Operations";
        }
        if (lower.contains("cash and cash equivalents") && lower.contains("total assets")) {
            return "Consolidated Balance Sheets";
        }
        if (lower.contains("total debt") && lower.contains("principal")) {
            return "Debt Schedule";
        }
        if (lower.contains("net cash provided by operating activities")) {
            return "Consolidated Statements of Cash Flows";
        }
        if (lower.contains("note 10 - debt")) {
            return "Debt Schedule";
        }
        if (lower.contains("revenue disaggregated by type and segment")) {
            return "Segment Revenue";
        }
        if (lower.contains("consolidated balance sheets")) {
            return "Consolidated Balance Sheets";
        }
        if (lower.contains("consolidated statements of operations")) {
            return "Consolidated Statements of Operations";
        }
        if (lower.contains("consolidated statements of cash flows")) {
            return "Consolidated Statements of Cash Flows";
        }
        if (lower.contains("total capital expenditures")) {
            return "Capital Expenditures";
        }
        if (lower.contains("launch services") && lower.contains("connectivity") && lower.contains("ai")) {
            return "Segment Revenue";
        }
        return "Untitled prospectus table";
    }

    private static String nearbyContext(Element table) {
        List<String> parts = new ArrayList<>();
        Element current = table;
        while (current != null && parts.size() < 10) {
            Element previous = current.previousElementSibling();
            while (previous != null && parts.size() < 10) {
                String text = cleanLabel(previous.text());
                if (!text.isBlank()) {
                    parts.add(text);
                }
                previous = previous.previousElementSibling();
            }
            current = current.parent();
            if (current == null || "body".equalsIgnoreCase(current.tagName())) {
                break;
            }
        }
        return clean(String.join(" ", parts));
    }

    static String detectScale(String text) {
        String lower = text == null ? "" : text.toLowerCase(Locale.ROOT);
        int billion = indexOrMax(lower, "billion");
        int million = indexOrMax(lower, "million");
        int thousand = indexOrMax(lower, "thousand");
        int first = Math.min(billion, Math.min(million, thousand));
        if (first == Integer.MAX_VALUE) {
            return null;
        }
        if (first == billion) {
            return "billions";
        }
        if (first == million) {
            return "millions";
        }
        return "thousands";
    }

    static String detectCurrency(String text) {
        String lower = text == null ? "" : text.toLowerCase(Locale.ROOT);
        if (text != null && text.contains("$")) {
            return "USD";
        }
        if (lower.contains("usd") || lower.contains("u.s. dollars") || lower.contains("dollars")) {
            return "USD";
        }
        return null;
    }

    static Double normalize(String raw, String scale) {
        Double parsed = parseNumber(raw);
        if (parsed == null) {
            return null;
        }
        return parsed * scaleMultiplier(scale);
    }

    static Double parseNumber(String raw) {
        if (raw == null) {
            return null;
        }
        String value = raw.trim();
        if (value.isBlank() || value.equals("-") || value.equals("—")) {
            return null;
        }
        value = value.replaceAll("\\[[^]]*]", "");
        String signProbe = value.replaceAll("[\\s$€£¥]", "");
        boolean negative = signProbe.startsWith("(") && signProbe.endsWith(")");
        value = value.replaceAll("[^0-9.\\-]", "");
        if (value.isBlank() || value.equals("-")) {
            return null;
        }
        try {
            double parsed = Double.parseDouble(value);
            return negative ? -parsed : parsed;
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    static double scaleMultiplier(String scale) {
        if (scale == null) {
            return 1.0;
        }
        return switch (scale.toLowerCase(Locale.ROOT)) {
            case "thousands" -> 1_000.0;
            case "millions" -> 1_000_000.0;
            case "billions" -> 1_000_000_000.0;
            default -> 1.0;
        };
    }

    static String clean(String text) {
        return text == null
                ? ""
                : text.replace('\u00a0', ' ')
                        .replaceAll("\\s+", " ")
                        .trim();
    }

    static String cleanLabel(String text) {
        return clean(text).replaceAll("\\s*\\.{3,}\\s*", " ").trim();
    }

    private static int indexOrMax(String text, String pattern) {
        int index = text.indexOf(pattern);
        return index < 0 ? Integer.MAX_VALUE : index;
    }

    private static String firstPresent(String first, String second) {
        return first == null || first.isBlank() ? second : first;
    }
}
