package io.stockvaluation.provider.prospectus;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@NoArgsConstructor
@AllArgsConstructor
@Getter
@Setter
public class ProspectusOfferingFacts {
    private Double offeringPrice;
    private String offeringPriceBasis;
    private Double sharesOffered;
    private Double postOfferingShares;
    private String shareCountBasis;
    private Double netProceeds;
    private String proceedsBasis;
}
