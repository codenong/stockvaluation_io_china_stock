package io.stockvaluation.provider.prospectus;

import io.stockvaluation.provider.SourceProvenance;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ProspectusPacketValidatorTest {

    private final ProspectusPacketValidator validator = new ProspectusPacketValidator();

    @Test
    void acceptsReviewedPacketWithRevenueScaleAndClearShareBasis() {
        ProspectusFinancialPacket packet = ProspectusTestPackets.reviewedPacket();

        ProspectusPacketValidationResult result = validator.validateForValuation(packet);

        assertEquals("accepted", result.status());
        assertTrue(result.blockingIssues().isEmpty());
    }

    @Test
    void acceptsReviewedSpaceXFixturePacketForDeterministicValuation() throws Exception {
        String filingUrl = "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm";
        String html = Files.readString(Path.of("src/test/resources/prospectus/spacex_s1a_trimmed.html"));
        ProspectusRawTableSet tableSet = new ProspectusTableExtractor().extract(html);
        ProspectusFinancialPacket packet = new ProspectusFinancialExtractor()
                .extract(new ProspectusDocument(filingUrl, html), tableSet);
        packet.setReviewStatus("reviewed");

        ProspectusPacketValidationResult result = validator.validateForValuation(packet);

        assertEquals("accepted", result.status());
        assertTrue(result.blockingIssues().isEmpty());
    }

    @Test
    void blocksMissingScaleAndAmbiguousShareCount() {
        ProspectusFinancialPacket packet = ProspectusTestPackets.reviewedPacket();
        packet.getFinancials().getIncomeStatement().get(0).setScale(null);
        packet.setShareCounts(List.of(
                ProspectusTestPackets.shareCount("weighted_average_eps_shares", 250_000_000.0),
                ProspectusTestPackets.shareCount("class_a_before_offering", 125_000_000.0)));

        ProspectusPacketValidationResult result = validator.validateForValuation(packet);

        assertEquals("blocked", result.status());
        assertTrue(result.blockingIssues().stream().anyMatch(issue -> "missing_units_or_scale".equals(issue.code())));
        assertTrue(result.blockingIssues().stream().anyMatch(issue -> "ambiguous_share_count".equals(issue.code())));
    }

    @Test
    void blocksUnreviewedAndUnsupportedFormPackets() {
        ProspectusFinancialPacket packet = ProspectusTestPackets.reviewedPacket();
        packet.setReviewStatus("review_required");
        packet.getFiling().setForm("F-1");

        ProspectusPacketValidationResult result = validator.validateForValuation(packet);

        assertEquals("blocked", result.status());
        assertTrue(result.blockingIssues().stream().anyMatch(issue -> "unreviewed_packet".equals(issue.code())));
        assertTrue(result.blockingIssues().stream().anyMatch(issue -> "unsupported_form".equals(issue.code())));
    }

    @Test
    void blocksMissingRevenueAndUnresolvedProFormaBasis() {
        ProspectusFinancialPacket packet = ProspectusTestPackets.reviewedPacket();
        packet.getFinancials().getIncomeStatement().removeIf(fact -> "revenue".equals(fact.getCanonicalField()));
        packet.getOffering().setShareCountBasis("pro_forma_basis_unresolved");

        ProspectusPacketValidationResult result = validator.validateForValuation(packet);

        assertEquals("blocked", result.status());
        assertTrue(result.blockingIssues().stream().anyMatch(issue -> "missing_revenue".equals(issue.code())));
        assertTrue(result.blockingIssues().stream().anyMatch(issue -> "unresolved_pro_forma_basis".equals(issue.code())));
    }

    @Test
    void blocksMissingOfferingPrice() {
        ProspectusFinancialPacket packet = ProspectusTestPackets.reviewedPacket();
        packet.getOffering().setOfferingPrice(null);

        ProspectusPacketValidationResult result = validator.validateForValuation(packet);

        assertEquals("blocked", result.status());
        assertTrue(result.blockingIssues().stream().anyMatch(issue -> "missing_offering_price".equals(issue.code())));
    }

    @Test
    void blocksReviewedPacketThatStillCarriesBlockingExtractionIssues() {
        ProspectusFinancialPacket packet = ProspectusTestPackets.reviewedPacket();
        packet.getExtractionIssues().add(new ProspectusExtractionIssue(
                "parser_no_core_facts",
                "blocking",
                "No reviewable financial facts were extracted from the filing.",
                "financials"));

        ProspectusPacketValidationResult result = validator.validateForValuation(packet);

        assertEquals("blocked", result.status());
        assertTrue(result.blockingIssues().stream().anyMatch(issue -> "parser_no_core_facts".equals(issue.code())));
    }

    @Test
    void preservesPrimaryFilingProvenanceOnPacketFacts() {
        ProspectusFinancialPacket packet = ProspectusTestPackets.reviewedPacket();

        ProspectusFact revenue = packet.getFinancials().getIncomeStatement().get(0);
        SourceProvenance provenance = revenue.getSourceProvenance();

        assertEquals(SourceProvenance.PRIMARY_FILING, provenance.getSourceClass());
        assertEquals("sec-edgar-prospectus", provenance.getProvider());
        assertEquals("primary_filing_used", provenance.getSourcePolicyStatus());
    }
}
