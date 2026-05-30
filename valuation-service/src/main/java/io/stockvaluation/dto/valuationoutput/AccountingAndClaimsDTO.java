package io.stockvaluation.dto.valuationoutput;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@NoArgsConstructor
@AllArgsConstructor
@Getter
@Setter
public class AccountingAndClaimsDTO {

    private String schemaVersion = "accounting_and_claims.v1";
    private Topic rdCapitalization = new Topic();
    private Topic sbcDilution = new Topic();
    private Topic leases = new Topic();
    private Topic optionsWarrants = new Topic();
    private Topic nolTax = new Topic();
    private Topic cash = new Topic();
    private Topic debt = new Topic();
    private Topic shareCount = new Topic();
    private List<Decision> effectiveAccountingDecisions = new ArrayList<>();

    @NoArgsConstructor
    @AllArgsConstructor
    @Getter
    @Setter
    public static class Topic {
        private String status;
        private String modelTreatment;
        private String sourceClass;
        private String provider;
        private String sourceDate;
        private String retrievalStatus;
        private String sourcePolicyStatus;
        private String reason;
        private Double value;
        private Map<String, Object> diagnostics = new LinkedHashMap<>();
        private Map<String, Object> reportedValues = new LinkedHashMap<>();
    }

    @NoArgsConstructor
    @AllArgsConstructor
    @Getter
    @Setter
    public static class Decision {
        private String topic;
        private String status;
        private String bucket;
        private String field;
        private String reason;
    }
}
