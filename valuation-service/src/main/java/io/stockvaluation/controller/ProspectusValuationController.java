package io.stockvaluation.controller;

import io.stockvaluation.provider.prospectus.ProspectusExtractionRequest;
import io.stockvaluation.provider.prospectus.ProspectusValuationRequest;
import io.stockvaluation.service.ProspectusExtractionService;
import io.stockvaluation.service.ProspectusValuationService;
import io.stockvaluation.utils.ResponseGenerator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Slf4j
@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/prospectus")
public class ProspectusValuationController {

    private final ProspectusExtractionService extractionService;
    private final ProspectusValuationService valuationService;

    @PostMapping("/extract")
    public ResponseEntity<?> extract(@RequestBody ProspectusExtractionRequest request) {
        try {
            return ResponseGenerator.generateSuccessResponse(extractionService.extract(request));
        } catch (IllegalArgumentException e) {
            return ResponseGenerator.generateBadRequestResponse(e.getMessage());
        } catch (RuntimeException e) {
            log.error("Error extracting prospectus", e);
            return ResponseGenerator.generateExceptionResponseDTO(e);
        }
    }

    @PostMapping("/valuation")
    public ResponseEntity<?> value(@RequestBody ProspectusValuationRequest request) {
        try {
            return ResponseGenerator.generateSuccessResponse(valuationService.value(request));
        } catch (IllegalArgumentException e) {
            return ResponseGenerator.generateUnprocessableEntityResponse(e.getMessage());
        } catch (RuntimeException e) {
            log.error("Error valuing prospectus", e);
            return ResponseGenerator.generateExceptionResponseDTO(e);
        }
    }
}
