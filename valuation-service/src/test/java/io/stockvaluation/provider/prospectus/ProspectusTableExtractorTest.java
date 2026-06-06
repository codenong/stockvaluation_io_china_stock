package io.stockvaluation.provider.prospectus;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;

class ProspectusTableExtractorTest {

    @Test
    void extractsHtmlTablesWithTitlesPeriodsUnitsScaleAndNormalizedValues() throws Exception {
        String html = Files.readString(Path.of("src/test/resources/prospectus/spacex_s1a_trimmed.html"));

        ProspectusRawTableSet tableSet = new ProspectusTableExtractor().extract(html);

        ProspectusRawTable operations = tableSet.tables().stream()
                .filter(table -> table.title().contains("Statements of Operations"))
                .findFirst()
                .orElseThrow();
        assertEquals("Consolidated Statements of Operations", operations.title());
        assertEquals("USD", operations.currency());
        assertEquals("millions", operations.scale());
        assertEquals("Year Ended December 31, 2025", operations.columns().get(0));

        ProspectusRawRow revenue = operations.rows().stream()
                .filter(row -> row.label().startsWith("Revenue"))
                .findFirst()
                .orElseThrow();
        assertEquals("$ 18,674", revenue.cells().get(0).rawValue());
        assertEquals(18_674_000_000.0, revenue.cells().get(0).normalizedValue());

        ProspectusRawRow operatingLoss = operations.rows().stream()
                .filter(row -> row.label().startsWith("Income (loss) from operations"))
                .findFirst()
                .orElseThrow();
        assertEquals(466_000_000.0, operatingLoss.cells().get(1).normalizedValue());
        assertNotNull(operations.sourceAnchor());
    }

    @Test
    void parsesCurrencyWrappedParenthesesAsNegative() {
        assertEquals(-657.0, ProspectusTableExtractor.parseNumber("$(657)"));
        assertEquals(-2_589.0, ProspectusTableExtractor.parseNumber("$ (2,589)"));
        assertEquals(-1_561.0, ProspectusTableExtractor.parseNumber("(1,561)"));
    }

    @Test
    void stillParsesPositiveCurrencyAndBlankCells() {
        assertEquals(4_423.0, ProspectusTableExtractor.parseNumber("$4,423"));
        assertEquals(466.0, ProspectusTableExtractor.parseNumber("466"));
        assertNull(ProspectusTableExtractor.parseNumber("-"));
        assertNull(ProspectusTableExtractor.parseNumber("—"));
    }
}
