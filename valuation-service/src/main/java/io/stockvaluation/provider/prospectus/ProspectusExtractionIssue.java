package io.stockvaluation.provider.prospectus;

public record ProspectusExtractionIssue(
        String code,
        String severity,
        String message,
        String field) {
}
