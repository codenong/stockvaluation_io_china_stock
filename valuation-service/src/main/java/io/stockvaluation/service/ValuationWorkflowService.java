package io.stockvaluation.service;

import io.stockvaluation.dto.CompanyDataDTO;
import io.stockvaluation.dto.ValuationOutputDTO;
import io.stockvaluation.dto.valuationoutput.CalibrationResultDTO;
import io.stockvaluation.form.FinancialDataInput;

public interface ValuationWorkflowService {

    ValuationOutputDTO getValuation(
            String ticker,
            FinancialDataInput financialDataInputOverrides
    );

    ValuationOutputDTO getExternalValuation(
            String ticker,
            CompanyDataDTO companyData,
            FinancialDataInput financialDataInputOverrides
    );

    CalibrationResultDTO calibrateToMarketPrice(
            String ticker,
            FinancialDataInput financialData,
            Double currentPrice
    );
}
