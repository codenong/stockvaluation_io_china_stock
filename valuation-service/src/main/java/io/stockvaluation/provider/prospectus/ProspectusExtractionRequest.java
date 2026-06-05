package io.stockvaluation.provider.prospectus;

import com.fasterxml.jackson.annotation.JsonAlias;

public record ProspectusExtractionRequest(
        @JsonAlias("filing_url") String filingUrl,
        @JsonAlias("expected_company") String expectedCompany,
        @JsonAlias("expected_symbol") String expectedSymbol) {
}
