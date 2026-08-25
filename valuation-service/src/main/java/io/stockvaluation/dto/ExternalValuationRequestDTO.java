package io.stockvaluation.dto;

import io.stockvaluation.form.FinancialDataInput;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * Request payload for valuation using externally prepared company data.
 *
 * The external data path intentionally reuses the existing CompanyDataDTO and
 * FinancialDataInput contracts so the deterministic DCF workflow remains shared
 * with ticker-based valuation.
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class ExternalValuationRequestDTO {

    private String ticker;

    private CompanyDataDTO companyData;

    /**
     * Optional valuation scenario overrides.
     *
     * This reuses the existing StockValuation input contract instead
     * of introducing a second set of DCF assumptions.
     */
    private FinancialDataInput overrides;
}
