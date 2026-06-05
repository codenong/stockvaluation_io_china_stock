package io.stockvaluation.provider.prospectus;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@NoArgsConstructor
@AllArgsConstructor
@Getter
@Setter
public class ProspectusCompanyIdentity {
    private String legalName;
    private String tickerOrExpectedSymbol;
    private String countryOfIncorporation;
    private String currency;
    private String industryKey;
}
