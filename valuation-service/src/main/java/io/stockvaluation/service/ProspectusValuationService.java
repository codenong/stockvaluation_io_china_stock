package io.stockvaluation.service;

import io.stockvaluation.dto.CompanyDataDTO;
import io.stockvaluation.dto.OverrideAssumption;
import io.stockvaluation.dto.SegmentResponseDTO;
import io.stockvaluation.dto.SegmentWeightedParameters;
import io.stockvaluation.dto.SourceQualityGateDTO;
import io.stockvaluation.dto.ValuationOutputDTO;
import io.stockvaluation.dto.valuationoutput.AssumptionTransparencyDTO;
import io.stockvaluation.form.FinancialDataInput;
import io.stockvaluation.provider.prospectus.ProspectusFinancialPacket;
import io.stockvaluation.provider.prospectus.ProspectusSegmentFact;
import io.stockvaluation.provider.prospectus.ProspectusExtractionIssue;
import io.stockvaluation.provider.prospectus.ProspectusPacketValidationResult;
import io.stockvaluation.provider.prospectus.ProspectusPacketValidator;
import io.stockvaluation.provider.prospectus.ProspectusValuationRequest;
import io.stockvaluation.provider.prospectus.ProspectusValuationBasis;
import io.stockvaluation.provider.prospectus.ProspectusValuationResult;
import io.stockvaluation.utils.SegmentParameterContext;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class ProspectusValuationService {

    private final ProspectusPacketValidator validator;
    private final ProspectusCompanyDataAssembler assembler;
    private final CommonService commonService;
    private final ValuationTemplateService templateService;
    private final ValuationOutputService outputService;

    public ProspectusValuationResult value(ProspectusValuationRequest request) {
        SegmentParameterContext.clear();
        try {
            ProspectusPacketValidationResult validation = validator.validateForValuation(
                    request == null ? null : request.packet());
            if (!validation.blockingIssues().isEmpty()) {
                String codes = validation.blockingIssues().stream()
                        .map(ProspectusExtractionIssue::code)
                        .collect(Collectors.joining(","));
                throw new IllegalArgumentException("prospectus packet is blocked: " + codes);
            }
            ProspectusValuationBasis basis = ProspectusValuationBasis.evaluate(request.packet());
            CompanyDataDTO companyData = assembler.assemble(request.packet());
            applyProFormaCashBridge(companyData, basis);
            FinancialDataInput input = initializeInput(companyData);
            applyProspectusSegments(request.packet(), input, companyData);
            var template = templateService.determineTemplate(input, companyData);
            String ticker = companyData.getBasicInfoDataDTO().getTicker();
            ValuationOutputDTO output = outputService.getValuationOutput(ticker, input, template);
            output.setAssumptionTransparency(buildProspectusTransparency(output, input, request.packet(), basis));
            output.setSourceQualityGate(notRequiredGate());
            return new ProspectusValuationResult(
                    "valued",
                    "offering_price",
                    request.packet(),
                    request.packet().getSourceProvenance(),
                    notRequiredGate(),
                    basis.status(),
                    basis.valuationCaseStatus(),
                    basis.proceedsBasis(),
                    basis.warnings(),
                    output);
        } finally {
            SegmentParameterContext.clear();
        }
    }

    private static FinancialDataInput initializeInput(CompanyDataDTO companyData) {
        FinancialDataInput input = new FinancialDataInput();
        input.setBasicInfoDataDTO(companyData.getBasicInfoDataDTO());
        input.setFinancialDataDTO(companyData.getFinancialDataDTO());
        input.setCompanyDriveDataDTO(companyData.getCompanyDriveDataDTO());
        input.setGrowthDto(companyData.getGrowthDto());
        input.setIndustry(companyData.getBasicInfoDataDTO().getIndustryGlobal());
        input.setIsExpensesCapitalize(false);
        input.setHasOperatingLease(false);
        input.setHasEmployeeOptions(false);
        input.setCompanyRiskLevel("Medium");
        input.setRevenueNextYear(companyData.getCompanyDriveDataDTO().getRevenueNextYear() * 100.0);
        input.setOperatingMarginNextYear(companyData.getCompanyDriveDataDTO().getOperatingMarginNextYear() * 100.0);
        input.setCompoundAnnualGrowth2_5(companyData.getCompanyDriveDataDTO().getCompoundAnnualGrowth2_5() * 100.0);
        input.setTargetPreTaxOperatingMargin(companyData.getCompanyDriveDataDTO().getTargetPreTaxOperatingMargin() * 100.0);
        input.setConvergenceYearMargin(5.0);
        input.setSalesToCapitalYears1To5(companyData.getCompanyDriveDataDTO().getSalesToCapitalYears1To5());
        input.setSalesToCapitalYears6To10(companyData.getCompanyDriveDataDTO().getSalesToCapitalYears6To10());
        input.setRiskFreeRate(companyData.getCompanyDriveDataDTO().getRiskFreeRate() * 100.0);
        input.setInitialCostCapital(companyData.getCompanyDriveDataDTO().getInitialCostCapital() * 100.0);
        input.setOverrideAssumptionCostCapital(new OverrideAssumption(0D, false, 0D, null));
        input.setOverrideAssumptionReturnOnCapital(new OverrideAssumption(0D, false, 0D, null));
        input.setOverrideAssumptionProbabilityOfFailure(new OverrideAssumption(0D, false, 0D, "V"));
        input.setOverrideAssumptionReinvestmentLag(new OverrideAssumption(0D, false, 0D, null));
        input.setOverrideAssumptionTaxRate(new OverrideAssumption(0D, false, 0D, null));
        input.setOverrideAssumptionNOL(new OverrideAssumption(0D, false, 0D, null));
        input.setOverrideAssumptionRiskFreeRate(new OverrideAssumption(0D, false, 0D, null));
        input.setOverrideAssumptionGrowthRate(new OverrideAssumption(0D, false, 0D, null));
        input.setOverrideAssumptionCashPosition(new OverrideAssumption(0D, false, 0D, null));
        input.setResearchedBaselineMode(true);
        input.setRequestPolicyMode("prospectus_reviewed");
        return input;
    }

    private static void applyProFormaCashBridge(CompanyDataDTO companyData, ProspectusValuationBasis basis) {
        if (companyData == null || companyData.getFinancialDataDTO() == null || basis == null || basis.netProceeds() == null) {
            return;
        }
        var financial = companyData.getFinancialDataDTO();
        financial.setCashAndMarkablTTM(value(financial.getCashAndMarkablTTM()) + basis.netProceeds());
        financial.setCashAndMarkablLTM(value(financial.getCashAndMarkablLTM()) + basis.netProceeds());
    }

    private void applyProspectusSegments(
            ProspectusFinancialPacket packet,
            FinancialDataInput input,
            CompanyDataDTO companyData) {
        SegmentResponseDTO segments = prospectusSegments(packet, companyData);
        if (segments == null || segments.getSegments() == null || segments.getSegments().size() <= 1) {
            return;
        }
        input.setSegments(segments);
        commonService.applySegmentWeightedParameters(input, companyData, List.of("segments"));
        SegmentWeightedParameters segmentParams = SegmentParameterContext.getParameters();
        input.setSegments(segmentParams != null && segmentParams.hasValidParameters()
                ? projectionSegments(segments)
                : null);
    }

    private static SegmentResponseDTO prospectusSegments(
            ProspectusFinancialPacket packet,
            CompanyDataDTO companyData) {
        List<ProspectusSegmentFact> facts = packet.getSegments() == null ? List.of() : packet.getSegments();
        if (facts.isEmpty()) {
            return null;
        }
        double consolidatedRevenue = companyData.getFinancialDataDTO() == null
                ? 0.0
                : value(companyData.getFinancialDataDTO().getRevenueTTM());
        List<SegmentResponseDTO.Segment> segments = new ArrayList<>();
        double totalWeight = 0.0;
        for (ProspectusSegmentFact fact : facts) {
            Double weight = segmentRevenueWeight(fact, consolidatedRevenue);
            if (weight == null || weight <= 0.0) {
                continue;
            }
            totalWeight += weight;
            segments.add(new SegmentResponseDTO.Segment(
                    blankToNull(fact.getSectorKey()),
                    blankToNull(fact.getMappedIndustry()),
                    List.of(defaultString(fact.getSegmentName(), "Unnamed prospectus segment")),
                    mappingScore(fact.getMappingConfidence()),
                    weight,
                    null));
        }
        if (segments.size() <= 1 || totalWeight <= 0.0) {
            return null;
        }
        if (totalWeight < 0.99) {
            segments.add(new SegmentResponseDTO.Segment(
                    null,
                    null,
                    List.of("Unmapped prospectus revenue"),
                    0.0,
                    round6(1.0 - totalWeight),
                    null));
        } else if (totalWeight > 1.01) {
            for (SegmentResponseDTO.Segment segment : segments) {
                segment.setRevenueShare(round6(segment.getRevenueShare() / totalWeight));
            }
        }
        return new SegmentResponseDTO(segments);
    }

    private static SegmentResponseDTO projectionSegments(SegmentResponseDTO segments) {
        if (segments == null || segments.getSegments() == null || segments.getSegments().isEmpty()) {
            return null;
        }
        SegmentWeightedParameters segmentParams = SegmentParameterContext.getParameters();
        List<SegmentResponseDTO.Segment> mappedSegments = new ArrayList<>();
        Set<String> seenSectors = new LinkedHashSet<>();
        for (SegmentResponseDTO.Segment segment : segments.getSegments()) {
            String sector = blankToNull(segment.getSector());
            if (sector == null || !seenSectors.add(sector)) {
                continue;
            }
            SegmentWeightedParameters.SectorParameters sectorParams = segmentParams == null
                    ? null
                    : segmentParams.getSectorParameters(sector);
            if (segmentParams != null && segmentParams.hasValidParameters() && sectorParams == null) {
                continue;
            }
            Double revenueShare = sectorParams != null && isPositiveFinite(sectorParams.getRevenueShare())
                    ? sectorParams.getRevenueShare()
                    : segment.getRevenueShare();
            if (!isPositiveFinite(revenueShare)) {
                continue;
            }
            mappedSegments.add(new SegmentResponseDTO.Segment(
                    sector,
                    sectorParams == null ? segment.getIndustry() : sectorParams.getIndustryAsPerExcel(),
                    segment.getComponents(),
                    segment.getMappingScore(),
                    round6(revenueShare),
                    segment.getOperatingMargin()));
        }
        return mappedSegments.isEmpty() ? null : new SegmentResponseDTO(mappedSegments);
    }

    private static Double segmentRevenueWeight(ProspectusSegmentFact fact, double consolidatedRevenue) {
        Double explicitWeight = fact.getRevenueWeight();
        if (isPositiveFinite(explicitWeight)) {
            double normalized = explicitWeight > 1.0 ? explicitWeight / 100.0 : explicitWeight;
            return normalized > 0.0 && normalized <= 1.0 ? round6(normalized) : null;
        }
        if (isPositiveFinite(fact.getRevenueAmount()) && consolidatedRevenue > 0.0) {
            double weight = fact.getRevenueAmount() / consolidatedRevenue;
            return weight > 0.0 && weight <= 1.0 ? round6(weight) : null;
        }
        return null;
    }

    private static AssumptionTransparencyDTO buildProspectusTransparency(
            ValuationOutputDTO output,
            FinancialDataInput input,
            ProspectusFinancialPacket packet,
            ProspectusValuationBasis basis) {
        AssumptionTransparencyDTO dto = output.getAssumptionTransparency() == null
                ? new AssumptionTransparencyDTO()
                : output.getAssumptionTransparency();
        dto.setIndustryUs(output.getIndustryUs());
        dto.setIndustryGlobal(output.getIndustryGlobal());
        dto.setCurrency(output.getCurrency());
        dto.setRequestPolicyMode("prospectus_reviewed");
        dto.setValuationCaseStatus(basis.valuationCaseStatus());
        dto.setValuationBasisStatus(basis.status());
        dto.setProceedsBasis(basis.proceedsBasis());
        dto.setSegmentCount(input.getSegments() == null || input.getSegments().getSegments() == null
                ? 0
                : input.getSegments().getSegments().size());
        dto.setMappedIndustries(new ArrayList<>());
        dto.setWeightedBaselineAssumptions(new LinkedHashMap<>());

        SegmentWeightedParameters segmentParams = SegmentParameterContext.getParameters();
        List<String> warnings = new ArrayList<>();
        if (segmentParams != null && segmentParams.getSegmentWarnings() != null) {
            warnings.addAll(segmentParams.getSegmentWarnings());
        }
        warnings.addAll(basis.warnings());
        List<AssumptionTransparencyDTO.BaselineIssue> unsupportedIssues = new ArrayList<>();
        if (!basis.clean()) {
            unsupportedIssues.add(baselineIssue(
                    "cash_share_basis",
                    basis.status(),
                    "Post-offering shares require disclosed net proceeds or pro-forma cash before this can be a clean valuation basis."));
        }
        List<AssumptionTransparencyDTO.BaselineIssue> segmentMaterialityIssues = segmentMaterialityIssues(packet);
        unsupportedIssues.addAll(segmentMaterialityIssues);
        for (AssumptionTransparencyDTO.BaselineIssue issue : segmentMaterialityIssues) {
            warnings.add(issue.getReason());
        }
        boolean challenged = !basis.clean() || !segmentMaterialityIssues.isEmpty();

        if (segmentParams != null && segmentParams.hasValidParameters()) {
            dto.setBaselineQuality("segment_weighted_baseline");
            dto.setBaselineUseStatus(challenged ? "challenged_baseline" : "validated_segment_weighted");
            dto.setSegmentAware(true);
            dto.setSegmentCount(segmentParams.getSegmentCount());
            dto.setSegmentCoveragePct(value(segmentParams.getSegmentCoveragePct()));
            dto.setMappedIndustries(mappedIndustries(segmentParams));
            dto.setWeightedBaselineAssumptions(weightedAssumptions(segmentParams));
            dto.setTargetOperatingMarginSource("Segment-weighted prospectus baseline");
            dto.setTargetOperatingMarginStatus("segment_weighted");
        } else {
            String baselineQuality = segmentParams != null && segmentParams.getBaselineQuality() != null
                    ? segmentParams.getBaselineQuality()
                    : "segment_evidence_insufficient";
            dto.setBaselineQuality(baselineQuality);
            dto.setBaselineUseStatus(challenged ? "challenged_baseline" : "segment_evidence_insufficient");
            dto.setSegmentAware(false);
            if (segmentParams != null) {
                dto.setSegmentCount(segmentParams.getSegmentCount());
            }
            dto.setSegmentCoveragePct(segmentParams == null ? 0.0 : value(segmentParams.getSegmentCoveragePct()));
            dto.setTargetOperatingMarginSource("Single-industry mechanical fallback");
            dto.setTargetOperatingMarginStatus("segment_evidence_insufficient");
            warnings.add("Prospectus segment weighting could not be used; baseline is labeled " + baselineQuality + ".");
            unsupportedIssues.add(baselineIssue("segments", baselineQuality, "Prospectus segment evidence did not support validated segment weighting."));
            unsupportedIssues.add(baselineIssue("target_operating_margin", "mechanical_fallback", "Target operating margin came from a company-level fallback because segment weighting was unavailable."));
        }
        dto.setUnsupportedBaselineDrivers(dedupeIssues(unsupportedIssues));
        dto.setBaselineWarnings(dedupe(warnings));
        return dto;
    }

    private static List<AssumptionTransparencyDTO.BaselineIssue> segmentMaterialityIssues(ProspectusFinancialPacket packet) {
        List<ProspectusSegmentFact> facts = packet == null || packet.getSegments() == null
                ? List.of()
                : packet.getSegments();
        List<AssumptionTransparencyDTO.BaselineIssue> issues = new ArrayList<>();
        for (ProspectusSegmentFact fact : facts) {
            Double weight = fact.getRevenueWeight();
            if (weight == null || !Double.isFinite(weight)) {
                continue;
            }
            double normalized = weight > 1.0 ? weight / 100.0 : weight;
            if (normalized <= 0.0) {
                continue;
            }
            String segmentName = defaultString(fact.getSegmentName(), "Unnamed segment");
            boolean unmapped = blankToNull(fact.getSectorKey()) == null || blankToNull(fact.getMappedIndustry()) == null;
            if (unmapped && normalized > 0.10) {
                issues.add(baselineIssue(
                        "segments",
                        "segment_mapping_material_gap",
                        "material unmapped prospectus revenue: " + segmentName + " is " + pct(normalized) + " of revenue."));
                continue;
            }
            String confidence = fact.getMappingConfidence() == null ? "" : fact.getMappingConfidence().toLowerCase();
            if ("low".equals(confidence) && normalized > 0.05) {
                issues.add(baselineIssue(
                        "segments",
                        "low_confidence_segment_material",
                        "material low-confidence prospectus segment mapping: " + segmentName + " is " + pct(normalized) + " of revenue."));
            }
        }
        return issues;
    }

    private static List<String> mappedIndustries(SegmentWeightedParameters segmentParams) {
        if (segmentParams == null || !segmentParams.hasSectorParameters()) {
            return List.of();
        }
        return segmentParams.getSectorParameters().values().stream()
                .map(SegmentWeightedParameters.SectorParameters::getIndustryAsPerExcel)
                .filter(Objects::nonNull)
                .filter(industry -> !industry.isBlank())
                .distinct()
                .toList();
    }

    private static Map<String, Object> weightedAssumptions(SegmentWeightedParameters segmentParams) {
        Map<String, Object> assumptions = new LinkedHashMap<>();
        assumptions.put("revenueGrowthRateYears2To5", segmentParams.getWeightedCompoundAnnualGrowth2_5());
        assumptions.put("operatingMarginNextYear", segmentParams.getWeightedOperatingMarginNextYear());
        assumptions.put("targetOperatingMargin", segmentParams.getWeightedTargetPreTaxOperatingMargin());
        assumptions.put("salesToCapitalYears1To5", segmentParams.getWeightedSalesToCapitalYears1To5());
        assumptions.put("salesToCapitalYears6To10", segmentParams.getWeightedSalesToCapitalYears6To10());
        assumptions.put("initialCostOfCapital", displayCostOfCapital(segmentParams.getWeightedInitialCostCapital()));
        return assumptions;
    }

    private static double displayCostOfCapital(Double costOfCapital) {
        double value = value(costOfCapital);
        return Math.abs(value) > 100.0 ? value / 100.0 : value;
    }

    private static AssumptionTransparencyDTO.BaselineIssue baselineIssue(
            String field,
            String status,
            String reason) {
        AssumptionTransparencyDTO.BaselineIssue issue = new AssumptionTransparencyDTO.BaselineIssue();
        issue.setField(field);
        issue.setStatus(status);
        issue.setReason(reason);
        return issue;
    }

    private static List<String> dedupe(List<String> values) {
        return values.stream()
                .filter(Objects::nonNull)
                .filter(value -> !value.isBlank())
                .distinct()
                .toList();
    }

    private static List<AssumptionTransparencyDTO.BaselineIssue> dedupeIssues(
            List<AssumptionTransparencyDTO.BaselineIssue> issues) {
        Map<String, AssumptionTransparencyDTO.BaselineIssue> deduped = new LinkedHashMap<>();
        for (AssumptionTransparencyDTO.BaselineIssue issue : issues) {
            if (issue == null || issue.getField() == null || issue.getField().isBlank()) {
                continue;
            }
            String key = issue.getField() + "|" + issue.getStatus() + "|" + issue.getReason();
            deduped.putIfAbsent(key, issue);
        }
        return new ArrayList<>(deduped.values());
    }

    private static double mappingScore(String confidence) {
        if (confidence == null) {
            return 0.0;
        }
        return switch (confidence.toLowerCase()) {
            case "high" -> 0.95;
            case "medium" -> 0.75;
            case "low" -> 0.25;
            default -> 0.0;
        };
    }

    private static boolean isPositiveFinite(Double value) {
        return value != null && Double.isFinite(value) && value > 0.0;
    }

    private static double round6(double value) {
        return Math.round(value * 1_000_000.0) / 1_000_000.0;
    }

    private static String pct(double value) {
        return "%.1f%%".formatted(value * 100.0);
    }

    private static SourceQualityGateDTO notRequiredGate() {
        return new SourceQualityGateDTO(
                "not_required",
                "prospectus_packet_reviewed",
                true,
                false,
                false,
                List.of());
    }

    private static double value(Double value) {
        return value == null ? 0.0 : value;
    }

    private static String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value;
    }

    private static String defaultString(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }
}
