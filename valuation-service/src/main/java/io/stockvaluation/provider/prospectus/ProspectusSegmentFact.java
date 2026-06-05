package io.stockvaluation.provider.prospectus;

import io.stockvaluation.provider.SourceProvenance;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class ProspectusSegmentFact {
    private String segmentName;
    private Double revenueAmount;
    private Double revenueWeight;
    private String sectorKey;
    private String mappedIndustry;
    private String mappingConfidence;
    private String sourceRowLabel;
    private String tableTitle;
    private String periodEnd;
    private SourceProvenance sourceProvenance;
}
