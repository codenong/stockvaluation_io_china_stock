package io.stockvaluation.provider.prospectus;

public interface ProspectusDocumentClient {

    ProspectusDocument fetch(String filingUrl);
}
