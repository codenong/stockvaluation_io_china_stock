package io.stockvaluation.provider.prospectus;

import io.stockvaluation.provider.SourceProvenance;
import lombok.Getter;
import lombok.Setter;

import java.util.ArrayList;
import java.util.List;

@Getter
@Setter
public class ProspectusFinancialPacket {
    private String schemaVersion = "prospectus_financial_packet.v1";
    private ProspectusCompanyIdentity company = new ProspectusCompanyIdentity();
    private ProspectusFilingMetadata filing = new ProspectusFilingMetadata();
    private String sourceUrl;
    private ProspectusFinancials financials = new ProspectusFinancials();
    private ProspectusOfferingFacts offering = new ProspectusOfferingFacts();
    private List<ProspectusShareCountFact> shareCounts = new ArrayList<>();
    private List<ProspectusSegmentFact> segments = new ArrayList<>();
    private List<ProspectusRawTable> segmentCandidateTables = new ArrayList<>();
    private List<ProspectusExtractionIssue> extractionIssues = new ArrayList<>();
    private SourceProvenance sourceProvenance;
    private String reviewStatus = "review_required";
}
