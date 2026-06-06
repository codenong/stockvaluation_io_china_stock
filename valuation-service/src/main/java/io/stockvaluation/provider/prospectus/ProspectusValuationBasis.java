package io.stockvaluation.provider.prospectus;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public record ProspectusValuationBasis(
        String status,
        String valuationCaseStatus,
        String proceedsBasis,
        Double netProceeds,
        List<String> warnings) {

    public static ProspectusValuationBasis evaluate(ProspectusFinancialPacket packet) {
        ProspectusOfferingFacts offering = packet == null ? null : packet.getOffering();
        if (!usesPostOfferingShares(packet)) {
            return new ProspectusValuationBasis(
                    "clean_existing_cash_share_basis",
                    "clean_valuation_case",
                    null,
                    null,
                    List.of());
        }
        if (offering != null && isPositiveFinite(offering.getNetProceeds())) {
            String basis = blankToNull(offering.getProceedsBasis());
            if (basis != null && basis.toLowerCase(Locale.ROOT).contains("net")) {
                return new ProspectusValuationBasis(
                        "clean_pro_forma_basis",
                        "clean_valuation_case",
                        basis,
                        offering.getNetProceeds(),
                        List.of());
            }
        }
        if (offering != null && isPositiveFinite(offering.getSharesOffered()) && isPositiveFinite(offering.getOfferingPrice())) {
            return new ProspectusValuationBasis(
                    "gross_proceeds_estimate_only",
                    "challenged_valuation_case",
                    "gross_proceeds_estimate_only",
                    null,
                    List.of("post-offering shares require pro-forma cash. Only gross proceeds can be inferred, so the valuation basis is challenged."));
        }
        return new ProspectusValuationBasis(
                "pro_forma_cash_missing",
                "challenged_valuation_case",
                null,
                null,
                List.of("post-offering shares require pro-forma cash, but net offering proceeds were not extracted."));
    }

    public boolean clean() {
        return "clean_valuation_case".equals(valuationCaseStatus);
    }

    public List<String> warnings() {
        return warnings == null ? List.of() : new ArrayList<>(warnings);
    }

    private static boolean usesPostOfferingShares(ProspectusFinancialPacket packet) {
        ProspectusOfferingFacts offering = packet == null ? null : packet.getOffering();
        if (offering != null && isPositiveFinite(offering.getPostOfferingShares())) {
            return true;
        }
        String basis = offering == null ? null : offering.getShareCountBasis();
        if (basis != null && basis.toLowerCase(Locale.ROOT).contains("post")) {
            return true;
        }
        if (packet == null || packet.getShareCounts() == null) {
            return false;
        }
        return packet.getShareCounts().stream()
                .map(ProspectusShareCountFact::getBasis)
                .filter(value -> value != null)
                .map(value -> value.toLowerCase(Locale.ROOT))
                .anyMatch(value -> value.contains("post") || value.contains("pro_forma"));
    }

    private static boolean isPositiveFinite(Double value) {
        return value != null && Double.isFinite(value) && value > 0.0;
    }

    private static String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value;
    }
}
