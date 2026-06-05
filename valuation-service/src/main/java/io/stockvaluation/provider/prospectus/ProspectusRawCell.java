package io.stockvaluation.provider.prospectus;

public record ProspectusRawCell(
        String rawValue,
        Double normalizedValue) {
}
