package io.stockvaluation.provider.prospectus;

import io.stockvaluation.provider.SourceProvenance;
import lombok.Getter;
import lombok.Setter;

import java.util.ArrayList;
import java.util.List;

@Getter
@Setter
public class ProspectusSegmentFact {
    private String segmentName;
    private Double revenueAmount;
    private Double revenueWeight;
    private String sectorKey;
    private String mappedIndustry;
    private String mappingConfidence;
    private Double mappingScore;
    private Double mappingScoreMargin;
    private String rationale;
    private List<String> components = new ArrayList<>();
    private String rowRole;
    private List<String> warnings = new ArrayList<>();
    private String sourceRowLabel;
    private String tableTitle;
    private String periodEnd;
    private SourceProvenance sourceProvenance;
}
