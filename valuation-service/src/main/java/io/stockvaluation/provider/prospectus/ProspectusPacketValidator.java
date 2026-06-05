package io.stockvaluation.provider.prospectus;

import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

@Component
public class ProspectusPacketValidator {

    public ProspectusPacketValidationResult validateForValuation(ProspectusFinancialPacket packet) {
        List<ProspectusExtractionIssue> blocking = new ArrayList<>();
        if (packet == null) {
            blocking.add(issue("missing_packet", "packet", "Prospectus packet is required."));
            return new ProspectusPacketValidationResult("blocked", blocking, List.of());
        }
        if (!"reviewed".equalsIgnoreCase(nullToEmpty(packet.getReviewStatus()))) {
            blocking.add(issue("unreviewed_packet", "reviewStatus", "Prospectus packet must be reviewed before valuation."));
        }
        if (packet.getExtractionIssues() != null) {
            packet.getExtractionIssues().stream()
                    .filter(issue -> "blocking".equalsIgnoreCase(nullToEmpty(issue.severity())))
                    .forEach(blocking::add);
        }
        String form = packet.getFiling() == null ? null : packet.getFiling().getForm();
        if (!isSupportedForm(form)) {
            blocking.add(issue("unsupported_form", "filing.form", "Only SEC S-1, S-1/A, and 424B3/4/5 HTML prospectuses are supported."));
        }
        if (!hasFact(packet, "revenue")) {
            blocking.add(issue("missing_revenue", "financials.incomeStatement", "Revenue is required for prospectus valuation."));
        }
        Double offeringPrice = packet.getOffering() == null ? null : packet.getOffering().getOfferingPrice();
        if (offeringPrice == null || !Double.isFinite(offeringPrice) || offeringPrice <= 0.0) {
            blocking.add(issue("missing_offering_price", "offering.offeringPrice", "Offering price is required for prospectus valuation."));
        }
        if (requiredFacts(packet).stream().anyMatch(fact -> isBlank(fact.getUnit()) || isBlank(fact.getScale()))) {
            blocking.add(issue("missing_units_or_scale", "financials", "Every mapped financial fact must carry units and scale."));
        }
        if (hasUnresolvedProFormaBasis(packet)) {
            blocking.add(issue("unresolved_pro_forma_basis", "offering.shareCountBasis", "Pro forma share-count basis must be resolved before valuation."));
        }
        ShareStatus shareStatus = shareStatus(packet);
        if (shareStatus == ShareStatus.MISSING) {
            blocking.add(issue("missing_share_count", "shareCounts", "A clear share-count basis is required for per-share valuation."));
        } else if (shareStatus == ShareStatus.AMBIGUOUS) {
            blocking.add(issue("ambiguous_share_count", "shareCounts", "Multiple or weighted-average share-count candidates require review."));
        }
        String status = blocking.isEmpty() ? "accepted" : "blocked";
        return new ProspectusPacketValidationResult(status, blocking, List.of());
    }

    private static List<ProspectusFact> requiredFacts(ProspectusFinancialPacket packet) {
        if (packet.getFinancials() == null) {
            return List.of();
        }
        return packet.getFinancials().allFacts().stream()
                .filter(fact -> List.of(
                        "revenue",
                        "prior_revenue",
                        "operating_income",
                        "research_and_development",
                        "cash_and_short_term_investments",
                        "total_debt",
                        "book_value_equity").contains(fact.getCanonicalField()))
                .toList();
    }

    private static boolean hasFact(ProspectusFinancialPacket packet, String field) {
        return packet.getFinancials() != null
                && packet.getFinancials().allFacts().stream()
                        .anyMatch(fact -> field.equals(fact.getCanonicalField())
                                && fact.getNormalizedValue() != null
                                && Double.isFinite(fact.getNormalizedValue()));
    }

    private static boolean hasUnresolvedProFormaBasis(ProspectusFinancialPacket packet) {
        String basis = packet.getOffering() == null ? null : packet.getOffering().getShareCountBasis();
        return basis != null && basis.toLowerCase(Locale.ROOT).contains("unresolved");
    }

    private static ShareStatus shareStatus(ProspectusFinancialPacket packet) {
        List<ProspectusShareCountFact> shares = packet.getShareCounts() == null ? List.of() : packet.getShareCounts();
        List<ProspectusShareCountFact> positive = shares.stream()
                .filter(share -> share.getNormalizedValue() != null
                        && Double.isFinite(share.getNormalizedValue())
                        && share.getNormalizedValue() > 0.0)
                .toList();
        if (positive.isEmpty()) {
            Double postOfferingShares = packet.getOffering() == null ? null : packet.getOffering().getPostOfferingShares();
            return postOfferingShares != null && postOfferingShares > 0.0 ? ShareStatus.CLEAR : ShareStatus.MISSING;
        }
        if (positive.size() > 1) {
            return ShareStatus.AMBIGUOUS;
        }
        String basis = nullToEmpty(positive.get(0).getBasis()).toLowerCase(Locale.ROOT);
        if (basis.contains("weighted_average") || basis.contains("eps") || basis.contains("before_offering")) {
            return ShareStatus.AMBIGUOUS;
        }
        return ShareStatus.CLEAR;
    }

    private static boolean isSupportedForm(String form) {
        String normalized = nullToEmpty(form).toUpperCase(Locale.ROOT);
        return normalized.equals("S-1")
                || normalized.equals("S-1/A")
                || normalized.equals("424B3")
                || normalized.equals("424B4")
                || normalized.equals("424B5");
    }

    private static ProspectusExtractionIssue issue(String code, String field, String message) {
        return new ProspectusExtractionIssue(code, "blocking", message, field);
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private static String nullToEmpty(String value) {
        return value == null ? "" : value;
    }

    private enum ShareStatus {
        CLEAR,
        MISSING,
        AMBIGUOUS
    }
}
