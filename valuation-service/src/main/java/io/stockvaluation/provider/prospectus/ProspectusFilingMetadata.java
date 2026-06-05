package io.stockvaluation.provider.prospectus;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@NoArgsConstructor
@AllArgsConstructor
@Getter
@Setter
public class ProspectusFilingMetadata {
    private String form;
    private String cik;
    private String accession;
    private String filingDate;
}
