package io.stockvaluation.controller;

import io.stockvaluation.dto.ValuationOutputDTO;
import io.stockvaluation.dto.ExternalValuationRequestDTO;

import io.stockvaluation.exception.InsufficientFinancialDataException;
import io.stockvaluation.form.FinancialDataInput;
import io.stockvaluation.service.ValuationWorkflowService;
import io.stockvaluation.utils.ResponseGenerator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@Slf4j
@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/automated-dcf-analysis")
public class AutomatedDCFAnalysisController {

    private final ValuationWorkflowService valuationWorkflowService;

    @PostMapping("/{ticker}/valuation")
    public ResponseEntity<?> getValuationOutput(@PathVariable String ticker,
                                                @RequestBody FinancialDataInput financialDataInputOverrides) {
        try {
            ValuationOutputDTO valuationOutputDTO = valuationWorkflowService.getValuation(
                    ticker,
                    financialDataInputOverrides
            );
            return ResponseGenerator.generateSuccessResponse(valuationOutputDTO);
        } catch (InsufficientFinancialDataException e) {
            log.warn("Unprocessable valuation input in POST /{}/valuation: {}", ticker, e.getMessage());
            return ResponseGenerator.generateUnprocessableEntityResponse(e.getMessage());
        } catch (ResponseStatusException e) {
            log.warn("Unprocessable valuation scenario in POST /{}/valuation: {}", ticker, e.getReason());
            return ResponseGenerator.generateUnprocessableEntityResponse(e.getReason());
        } catch (IllegalArgumentException e) {
            log.warn("Invalid valuation scenario input in POST /{}/valuation: {}", ticker, e.getMessage());
            return ResponseGenerator.generateUnprocessableEntityResponse(e.getMessage());
        } catch (RuntimeException e) {
            log.error("Error in POST /{}/valuation", ticker, e);
            return ResponseGenerator.generateExceptionResponseDTO(e);
        }
    }

    @PostMapping("/external/valuation")
    public ResponseEntity<?> getExternalValuationOutput(
            @RequestBody ExternalValuationRequestDTO request) {
        String ticker = request != null ? request.getTicker() : null;
        try {
            if (request == null || request.getTicker() == null || request.getTicker().isBlank()) {
                return ResponseGenerator.generateUnprocessableEntityResponse(
                        "external valuation requires ticker");
            }
            if (request.getCompanyData() == null) {
                return ResponseGenerator.generateUnprocessableEntityResponse(
                        "external valuation requires companyData");
            }

            ValuationOutputDTO valuationOutputDTO =
                    valuationWorkflowService.getExternalValuation(
                            ticker,
                            request.getCompanyData(),
                            request.getOverrides());

            return ResponseGenerator.generateSuccessResponse(valuationOutputDTO);
        } catch (InsufficientFinancialDataException e) {
            log.warn("Unprocessable external valuation input in POST /external/{}/valuation: {}",
                    ticker, e.getMessage());
            return ResponseGenerator.generateUnprocessableEntityResponse(e.getMessage());
        } catch (ResponseStatusException e) {
            log.warn("Unprocessable external valuation scenario in POST /external/{}/valuation: {}",
                    ticker, e.getReason());
            return ResponseGenerator.generateUnprocessableEntityResponse(e.getReason());
        } catch (IllegalArgumentException e) {
            log.warn("Invalid external valuation scenario in POST /external/{}/valuation: {}",
                    ticker, e.getMessage());
            return ResponseGenerator.generateUnprocessableEntityResponse(e.getMessage());
        } catch (RuntimeException e) {
            log.error("Error in POST /external/{}/valuation", ticker, e);
            return ResponseGenerator.generateExceptionResponseDTO(e);
        }
    }

}
