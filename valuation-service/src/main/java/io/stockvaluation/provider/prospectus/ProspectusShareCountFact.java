package io.stockvaluation.provider.prospectus;

import io.stockvaluation.provider.SourceProvenance;
import lombok.Getter;
import lombok.Setter;

import java.util.ArrayList;
import java.util.List;

@Getter
@Setter
public class ProspectusShareCountFact {
    private String basis;
    private String sourceRowLabel;
    private String originalColumnLabel;
    private String tableTitle;
    private String rawValue;
    private Double normalizedValue;
    private Double confidence;
    private SourceProvenance sourceProvenance;
    private List<String> warnings = new ArrayList<>();
}
