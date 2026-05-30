package io.stockvaluation.provider;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.ArrayList;
import java.util.List;

@NoArgsConstructor
@AllArgsConstructor
@Getter
@Setter
public class SourceProvenance {

    public static final String PRIMARY_FILING = "primary_filing";
    public static final String YAHOO_NORMALIZED = "yahoo_normalized";
    public static final String COMPANY_IR = "company_ir";
    public static final String AGENT_RESEARCHED = "agent_researched";

    private String sourceClass;
    private String provider;
    private String sourceDate;
    private String periodEnd;
    private String retrievalStatus;
    private String crossCheckStatus;
    private String sourcePolicyStatus;
    private List<String> warnings = new ArrayList<>();
    private List<DataQualityWarning> dataQualityWarnings = new ArrayList<>();

    public SourceProvenance(
            String sourceClass,
            String provider,
            String sourceDate,
            String periodEnd,
            String retrievalStatus,
            String crossCheckStatus,
            String sourcePolicyStatus,
            List<String> warnings) {
        this.sourceClass = sourceClass;
        this.provider = provider;
        this.sourceDate = sourceDate;
        this.periodEnd = periodEnd;
        this.retrievalStatus = retrievalStatus;
        this.crossCheckStatus = crossCheckStatus;
        this.sourcePolicyStatus = sourcePolicyStatus;
        this.warnings = warnings == null ? new ArrayList<>() : new ArrayList<>(warnings);
        this.dataQualityWarnings = new ArrayList<>();
    }

    public static SourceProvenance yahooNormalized(String provider, String periodEnd) {
        SourceProvenance provenance = new SourceProvenance();
        provenance.setSourceClass(YAHOO_NORMALIZED);
        provenance.setProvider(provider);
        provenance.setSourceDate(periodEnd);
        provenance.setPeriodEnd(periodEnd);
        provenance.setRetrievalStatus("retrieved");
        provenance.setCrossCheckStatus("company_report_check_pending");
        provenance.setSourcePolicyStatus("normalized_provider");
        if (periodEnd == null || periodEnd.isBlank()) {
            provenance.setRetrievalStatus("retrieved_missing_period");
            provenance.setSourcePolicyStatus("missing_source_date");
            provenance.setWarnings(List.of("Provider returned financial data without parseable period metadata."));
        }
        return provenance;
    }

    public static SourceProvenance primaryFiling(String provider, String periodEnd) {
        SourceProvenance provenance = new SourceProvenance();
        provenance.setSourceClass(PRIMARY_FILING);
        provenance.setProvider(provider);
        provenance.setSourceDate(periodEnd);
        provenance.setPeriodEnd(periodEnd);
        provenance.setRetrievalStatus("retrieved");
        provenance.setCrossCheckStatus("not_applicable");
        provenance.setSourcePolicyStatus("primary_filing_used");
        if (periodEnd == null || periodEnd.isBlank()) {
            provenance.setRetrievalStatus("retrieved_missing_period");
            provenance.setSourcePolicyStatus("missing_source_date");
            provenance.setWarnings(List.of("Primary filing provider returned data without parseable period metadata."));
        }
        return provenance;
    }

    @NoArgsConstructor
    @AllArgsConstructor
    @Getter
    @Setter
    public static class DataQualityWarning {
        private String field;
        private String status;
        private Double normalizedValue;
        private Double filingValue;
        private Double differencePct;
        private Double thresholdPct;
        private String sourceClass;
        private String sourceDate;
    }
}
