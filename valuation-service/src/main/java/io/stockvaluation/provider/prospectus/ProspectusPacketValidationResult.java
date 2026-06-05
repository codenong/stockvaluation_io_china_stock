package io.stockvaluation.provider.prospectus;

import java.util.List;

public record ProspectusPacketValidationResult(
        String status,
        List<ProspectusExtractionIssue> blockingIssues,
        List<ProspectusExtractionIssue> warnings) {
}
