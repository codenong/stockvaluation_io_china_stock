package io.stockvaluation.service;

import io.stockvaluation.dto.SourceQualityGateDTO;
import io.stockvaluation.provider.prospectus.ProspectusDocument;
import io.stockvaluation.provider.prospectus.ProspectusDocumentClient;
import io.stockvaluation.provider.prospectus.ProspectusExtractionRequest;
import io.stockvaluation.provider.prospectus.ProspectusExtractionResult;
import io.stockvaluation.provider.prospectus.ProspectusFinancialExtractor;
import io.stockvaluation.provider.prospectus.ProspectusFinancialPacket;
import io.stockvaluation.provider.prospectus.ProspectusTableExtractor;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class ProspectusExtractionService {

    private final ProspectusDocumentClient documentClient;
    private final ProspectusTableExtractor tableExtractor;
    private final ProspectusFinancialExtractor financialExtractor;

    public ProspectusExtractionResult extract(ProspectusExtractionRequest request) {
        if (request == null || request.filingUrl() == null || request.filingUrl().isBlank()) {
            throw new IllegalArgumentException("filing_url is required.");
        }
        ProspectusDocument document = documentClient.fetch(request.filingUrl());
        ProspectusFinancialPacket packet = financialExtractor.extract(document, tableExtractor.extract(document.html()));
        if (request.expectedCompany() != null && !request.expectedCompany().isBlank()) {
            packet.getCompany().setLegalName(request.expectedCompany());
        }
        if (request.expectedSymbol() != null && !request.expectedSymbol().isBlank()) {
            packet.getCompany().setTickerOrExpectedSymbol(request.expectedSymbol());
        }
        return new ProspectusExtractionResult(
                "requires_review",
                packet,
                extractionReviewGate());
    }

    public static SourceQualityGateDTO extractionReviewGate() {
        return new SourceQualityGateDTO(
                "requires_user_decision",
                "prospectus_extraction_review_required",
                true,
                false,
                true,
                List.of("approve_extracted_packet", "correct_packet", "add_sources", "stop"));
    }
}
