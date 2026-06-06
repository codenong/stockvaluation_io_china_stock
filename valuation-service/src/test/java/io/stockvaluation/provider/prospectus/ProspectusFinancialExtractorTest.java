package io.stockvaluation.provider.prospectus;

import io.stockvaluation.provider.SourceProvenance;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ProspectusFinancialExtractorTest {

    @Test
    void extractsSpaceXLikeS1AFinancialPacketWithOfferingAndRawSegmentCandidates() throws Exception {
        String html = Files.readString(Path.of("src/test/resources/prospectus/spacex_s1a_trimmed.html"));
        ProspectusDocument document = new ProspectusDocument(
                "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm",
                html);
        ProspectusRawTableSet tableSet = new ProspectusTableExtractor().extract(html);

        ProspectusFinancialPacket packet = new ProspectusFinancialExtractor().extract(document, tableSet);

        assertEquals("prospectus_financial_packet.v1", packet.getSchemaVersion());
        assertEquals("review_required", packet.getReviewStatus());
        assertEquals("Space Exploration Technologies Corp.", packet.getCompany().getLegalName());
        assertEquals("S-1/A", packet.getFiling().getForm());
        assertEquals("0001181412", packet.getFiling().getCik());
        assertEquals("0001628280-26-040364", packet.getFiling().getAccession());
        assertEquals("2026-06-03", packet.getFiling().getFilingDate());
        assertEquals(SourceProvenance.PRIMARY_FILING, packet.getSourceProvenance().getSourceClass());
        assertEquals("sec-edgar-prospectus", packet.getSourceProvenance().getProvider());

        assertFact(packet, "revenue", 18_674_000_000.0, "Revenue", "Consolidated Statements of Operations");
        assertFact(packet, "operating_income", -2_589_000_000.0, "Income (loss) from operations", "Consolidated Statements of Operations");
        assertFact(packet, "research_and_development", 8_643_000_000.0, "Research and development", "Consolidated Statements of Operations");
        assertFact(packet, "cash_and_short_term_investments", 24_747_000_000.0, "Cash and cash equivalents", "Consolidated Balance Sheets");
        assertFact(packet, "total_debt", 22_049_000_000.0, "Total debt", "Debt Schedule");
        assertFact(packet, "operating_cash_flow", 6_785_000_000.0, "Net cash provided by operating activities", "Consolidated Statements of Cash Flows");
        assertFact(packet, "capital_expenditures", 20_737_000_000.0, "Total Capital Expenditures", "Capital Expenditures");

        assertEquals(135.0, packet.getOffering().getOfferingPrice());
        assertEquals("offering_price", packet.getOffering().getOfferingPriceBasis());
        assertEquals(555_555_555.0, packet.getOffering().getSharesOffered());
        assertEquals("pro_forma_post_offering", packet.getOffering().getShareCountBasis());
        assertEquals(13_075_865_175.0, packet.getOffering().getPostOfferingShares());
        assertEquals(1, packet.getShareCounts().size());
        assertEquals(13_075_865_175.0, packet.getShareCounts().get(0).getNormalizedValue());
        assertTrue(packet.getShareCounts().get(0).getSourceRowLabel().contains("Class A common stock outstanding"));
        assertTrue(packet.getShareCounts().get(0).getSourceRowLabel().contains("Class B common stock outstanding"));
        assertTrue(packet.getExtractionIssues().isEmpty());

        assertTrue(packet.getSegments().isEmpty());
        assertFalse(packet.getSegmentCandidateTables().isEmpty());
        ProspectusRawTable candidate = packet.getSegmentCandidateTables().stream()
                .filter(table -> table.rows().stream().anyMatch(row -> "Launch Services".equals(row.label())))
                .findFirst()
                .orElseThrow();
        assertTrue(candidate.rows().stream().anyMatch(row -> "Launch Services".equals(row.label())));
        assertTrue(candidate.rows().stream().anyMatch(row -> "Space".equals(row.label())));
        assertTrue(candidate.rows().stream().anyMatch(row -> "Connectivity".equals(row.label())));
        assertTrue(candidate.rows().stream().anyMatch(row -> "AI".equals(row.label())));
        assertEquals(4_086_000_000.0, candidateRow(candidate, "Space").cells().get(0).normalizedValue());
        assertEquals(11_387_000_000.0, candidateRow(candidate, "Connectivity").cells().get(0).normalizedValue());
        assertEquals(3_201_000_000.0, candidateRow(candidate, "AI").cells().get(0).normalizedValue());
    }

    @Test
    void emptySpaceXLikeExtractionReturnsTypedIssuesInsteadOfSilentEmptyPacket() {
        String html = """
                <!doctype html>
                <html>
                <head><title>Space Exploration Technologies - S-1/A#2</title></head>
                <body>
                <div>S-1/A 1 spaceexplorationtechnologib.htm S-1/A Space Exploration Technologies - S-1/A#2</div>
                <p>As filed with the U.S. Securities and Exchange Commission on June 3, 2026</p>
                <table><tr><td>Risk factor</td><td>No mapped financial facts here.</td></tr></table>
                </body>
                </html>
                """;
        ProspectusDocument document = new ProspectusDocument(
                "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm",
                html);
        ProspectusRawTableSet tableSet = new ProspectusTableExtractor().extract(html);

        ProspectusFinancialPacket packet = new ProspectusFinancialExtractor().extract(document, tableSet);

        assertTrue(packet.getFinancials().allFacts().isEmpty());
        assertTrue(packet.getShareCounts().isEmpty());
        assertFalse(packet.getExtractionIssues().isEmpty());
        Set<String> codes = packet.getExtractionIssues().stream()
                .map(ProspectusExtractionIssue::code)
                .collect(Collectors.toSet());
        assertTrue(codes.contains("parser_no_core_facts"));
        assertTrue(codes.contains("missing_revenue"));
        assertTrue(codes.contains("missing_share_count"));
        assertTrue(codes.contains("missing_units_or_scale"));
        assertTrue(codes.contains("missing_source_period"));
        assertTrue(codes.contains("missing_cash"));
        assertTrue(codes.contains("missing_debt"));
    }

    @Test
    void extractsClearlyDisclosedNetOfferingProceeds() {
        String html = """
                <!doctype html>
                <html>
                <head><title>Space Exploration Technologies - S-1/A</title></head>
                <body>
                <div>S-1/A 1 example.htm S-1/A Space Exploration Technologies - S-1/A</div>
                <p>As filed with the U.S. Securities and Exchange Commission on June 3, 2026</p>
                <h1>Space Exploration Technologies Corp.</h1>
                <table>
                  <tr><td>(in millions, except share data)</td><td></td></tr>
                  <tr><td>Class A common stock offered by us</td><td>555,555,555 shares</td></tr>
                  <tr><td>Common stock outstanding immediately after this offering</td><td>13,075,865,175 shares</td></tr>
                  <tr><td>Net proceeds to us, after underwriting discounts and commissions</td><td>$ 74,000</td></tr>
                </table>
                </body>
                </html>
                """;
        ProspectusDocument document = new ProspectusDocument(
                "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm",
                html);
        ProspectusRawTableSet tableSet = new ProspectusTableExtractor().extract(html);

        ProspectusFinancialPacket packet = new ProspectusFinancialExtractor().extract(document, tableSet);

        assertEquals(74_000_000_000.0, packet.getOffering().getNetProceeds());
        assertEquals("net_proceeds_disclosed", packet.getOffering().getProceedsBasis());
    }

    private static void assertFact(
            ProspectusFinancialPacket packet,
            String canonicalField,
            double normalizedValue,
            String rowLabel,
            String tableTitle) {
        ProspectusFact fact = packet.getFinancials().allFacts().stream()
                .filter(candidate -> canonicalField.equals(candidate.getCanonicalField()))
                .findFirst()
                .orElseThrow();
        assertEquals(normalizedValue, fact.getNormalizedValue());
        assertEquals(rowLabel, fact.getSourceRowLabel());
        assertTrue(fact.getTableTitle().contains(tableTitle));
    }

    private static ProspectusRawRow candidateRow(ProspectusRawTable table, String label) {
        return table.rows().stream()
                .filter(row -> label.equals(row.label()))
                .findFirst()
                .orElseThrow();
    }
}
