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
import io.stockvaluation.provider.prospectus.ProspectusRawTable;
import io.stockvaluation.provider.prospectus.ProspectusSegmentFact;
import io.stockvaluation.provider.prospectus.ProspectusScenario;
import io.stockvaluation.provider.prospectus.ProspectusSegmentScenario;
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
import java.util.Locale;
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
            ProspectusFinancialPacket packet = request.packet();
            ProspectusScenario scenario = request.scenario();
            ProspectusValuationBasis basis = ProspectusValuationBasis.evaluate(packet, scenario);
            CompanyDataDTO companyData = assembler.assemble(request.packet());
            applyProFormaCashBridge(companyData, basis);
            FinancialDataInput input = initializeInput(companyData);
            applyProspectusScenario(scenario, packet, input, companyData);
            var template = templateService.determineTemplate(input, companyData);
            String ticker = companyData.getBasicInfoDataDTO().getTicker();
            ValuationOutputDTO output = outputService.getValuationOutput(ticker, input, template);
            AssumptionTransparencyDTO transparency = buildProspectusTransparency(output, input, packet, basis, scenario);
            output.setAssumptionTransparency(transparency);
            String valuationCaseStatus = transparency.getValuationCaseStatus() == null
                    ? basis.valuationCaseStatus()
                    : transparency.getValuationCaseStatus();
            output.setSourceQualityGate(notRequiredGate());
            return new ProspectusValuationResult(
                    "valued",
                    "offering_price",
                    packet,
                    scenario,
                    packet.getSourceProvenance(),
                    notRequiredGate(),
                    basis.status(),
                    valuationCaseStatus,
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

    private void applyProspectusScenario(
            ProspectusScenario scenario,
            ProspectusFinancialPacket packet,
            FinancialDataInput input,
            CompanyDataDTO companyData) {
        if (scenario == null) {
            applyProspectusSegments(packet, input, companyData);
            return;
        }
        input.setRequestPolicyMode("prospectus_explicit_scenario");
        applyScenarioCompanyAssumptions(scenario, input);
        if (hasScenarioSegments(scenario)) {
            applyScenarioSegments(scenario, packet, input);
        } else {
            applyProspectusSegments(packet, input, companyData);
        }
    }

    private static void applyScenarioCompanyAssumptions(ProspectusScenario scenario, FinancialDataInput input) {
        Double revenueNextYear = percentAssumption(scenario.revenueNextYear());
        if (revenueNextYear != null) {
            input.setRevenueNextYear(revenueNextYear);
        }
        Double growth2To5 = percentAssumption(scenario.compoundAnnualGrowth2_5());
        if (growth2To5 != null) {
            input.setCompoundAnnualGrowth2_5(growth2To5);
        }
        Double operatingMarginNextYear = percentAssumption(scenario.operatingMarginNextYear());
        if (operatingMarginNextYear != null) {
            input.setOperatingMarginNextYear(operatingMarginNextYear);
        }
        Double targetMargin = percentAssumption(scenario.targetOperatingMargin());
        if (targetMargin != null) {
            input.setTargetPreTaxOperatingMargin(targetMargin);
        }
        if (isPositiveFinite(scenario.marginConvergenceYear())) {
            input.setConvergenceYearMargin(scenario.marginConvergenceYear());
        }
        if (isPositiveFinite(scenario.salesToCapitalYears1To5())) {
            input.setSalesToCapitalYears1To5(scenario.salesToCapitalYears1To5());
        }
        if (isPositiveFinite(scenario.salesToCapitalYears6To10())) {
            input.setSalesToCapitalYears6To10(scenario.salesToCapitalYears6To10());
        }
        Double initialCostOfCapital = engineInitialCostOfCapital(scenario.initialCostOfCapital());
        if (initialCostOfCapital != null) {
            input.setInitialCostCapital(initialCostOfCapital);
        }
        Double terminalGrowthRate = percentAssumption(scenario.terminalGrowthRate());
        if (terminalGrowthRate != null) {
            input.setTerminalGrowthRate(terminalGrowthRate);
        }
        Double terminalCostOfCapital = percentAssumption(scenario.terminalCostOfCapital());
        if (terminalCostOfCapital != null) {
            input.setOverrideAssumptionCostCapital(new OverrideAssumption(terminalCostOfCapital, true, 0D, null));
        }
        Double terminalReturnOnCapital = percentAssumption(scenario.terminalReturnOnCapital());
        if (terminalReturnOnCapital != null) {
            input.setOverrideAssumptionReturnOnCapital(new OverrideAssumption(terminalReturnOnCapital, true, 0D, null));
        }
        if (Boolean.TRUE.equals(scenario.rdCapitalization())) {
            input.setIsExpensesCapitalize(true);
            input.setRdAmortizationMethod(defaultString(scenario.rdAmortizationMethod(), "straight_line"));
            input.setRdAmortizationPeriodYears(scenario.rdAmortizationPeriodYears() == null
                    ? 5
                    : scenario.rdAmortizationPeriodYears());
        }
    }

    private static boolean hasScenarioSegments(ProspectusScenario scenario) {
        return scenario != null && !scenario.segmentsOrEmpty().isEmpty();
    }

    private static void applyScenarioSegments(
            ProspectusScenario scenario,
            ProspectusFinancialPacket packet,
            FinancialDataInput input) {
        List<ProspectusSegmentScenario> segmentAssumptions = scenario.segmentsOrEmpty();
        if (segmentAssumptions.isEmpty()) {
            return;
        }
        double targetWeightTotal = segmentAssumptions.stream()
                .map(segment -> scenarioTerminalRevenue(segment, packet))
                .filter(ProspectusValuationService::isPositiveFinite)
                .mapToDouble(Double::doubleValue)
                .sum();
        double baseWeightTotal = segmentAssumptions.stream()
                .map(segment -> scenarioBaseRevenue(segment, packet))
                .filter(ProspectusValuationService::isPositiveFinite)
                .mapToDouble(Double::doubleValue)
                .sum();

        List<SegmentResponseDTO.Segment> projectionSegments = new ArrayList<>();
        SegmentWeightedParameters segmentParams = new SegmentWeightedParameters();
        segmentParams.setSegmentWeighted(true);
        segmentParams.setSegmentCount(segmentAssumptions.size());
        segmentParams.setBaselineQuality("prospectus_explicit_scenario");
        segmentParams.setSegmentCoveragePct(100.0);
        segmentParams.setRiskFreeRate(valueOrDefault(percentAssumption(scenario.terminalGrowthRate()), input.getRiskFreeRate()));
        segmentParams.setIndustry("prospectus_explicit_scenario");
        segmentParams.setSegmentWarnings(List.of(
                "Prospectus scenario supplied segment-level assumptions; mechanical diagnostic baseline is not the headline valuation."));

        double weightedRevenueNextYear = 0.0;
        double weightedGrowth2To5 = 0.0;
        double weightedOperatingMargin = 0.0;
        double weightedTargetMargin = 0.0;
        double weightedSalesToCapital1To5 = 0.0;
        double weightedSalesToCapital6To10 = 0.0;
        double weightedInitialCostCapital = 0.0;
        double weightSum = 0.0;

        for (int index = 0; index < segmentAssumptions.size(); index++) {
            ProspectusSegmentScenario segment = segmentAssumptions.get(index);
            String name = defaultString(segment.name(), "Prospectus segment " + (index + 1));
            String sectorKey = defaultString(blankToNull(segment.sectorKey()), scenarioSectorKey(name, index));
            String industry = defaultString(segment.mappedIndustry(), name);
            Double baseRevenue = scenarioBaseRevenue(segment, packet);
            Double terminalRevenue = scenarioTerminalRevenue(segment, packet);
            double weight = scenarioSegmentWeight(
                    baseRevenue,
                    terminalRevenue,
                    baseWeightTotal,
                    targetWeightTotal,
                    segmentAssumptions.size());

            projectionSegments.add(new SegmentResponseDTO.Segment(
                    sectorKey,
                    industry,
                    List.of(name),
                    1.0,
                    round6(weight),
                    percentAssumption(firstPresent(segment.operatingMarginNextYear(), scenario.operatingMarginNextYear()))));

            SegmentWeightedParameters.SectorParameters sectorParams = new SegmentWeightedParameters.SectorParameters();
            sectorParams.setSectorName(sectorKey);
            sectorParams.setRevenueShare(round6(weight));
            sectorParams.setBaseRevenue(valueOrDefault(baseRevenue, 0.0));
            sectorParams.setTargetRevenue(terminalRevenue);
            sectorParams.setProjectedRevenues(segment.projectedRevenuesOrEmpty().isEmpty()
                    ? null
                    : new ArrayList<>(segment.projectedRevenuesOrEmpty()));
            sectorParams.setRevenueNextYear(percentAssumption(firstPresent(
                    segment.revenueNextYear(),
                    revenueGrowthFromProjection(segment, baseRevenue, 1),
                    scenario.revenueNextYear())));
            sectorParams.setCompoundAnnualGrowth2_5(percentAssumption(firstPresent(
                    segment.compoundAnnualGrowth2_5(),
                    revenueCagrFromProjection(segment, 1, 5),
                    scenario.compoundAnnualGrowth2_5())));
            sectorParams.setTerminalGrowthRate(decimalAssumption(firstPresent(segment.terminalGrowthRate(), scenario.terminalGrowthRate())));
            sectorParams.setOperatingMarginNextYear(percentAssumption(firstPresent(segment.operatingMarginNextYear(), scenario.operatingMarginNextYear())));
            sectorParams.setTargetPreTaxOperatingMargin(percentAssumption(firstPresent(segment.targetOperatingMargin(), scenario.targetOperatingMargin())));
            sectorParams.setConvergenceYearMargin(firstPresent(segment.marginConvergenceYear(), scenario.marginConvergenceYear()));
            sectorParams.setSalesToCapitalYears1To5(firstPresent(segment.salesToCapitalYears1To5(), scenario.salesToCapitalYears1To5()));
            sectorParams.setSalesToCapitalYears6To10(firstPresent(segment.salesToCapitalYears6To10(), scenario.salesToCapitalYears6To10()));
            sectorParams.setInitialCostCapital(engineInitialCostOfCapital(firstPresent(
                    segment.initialCostOfCapital(),
                    scenario.initialCostOfCapital())));
            sectorParams.setIndustryAsPerExcel(industry);
            segmentParams.setSectorParameters(sectorKey, sectorParams);

            double weightedValue = weight > 0.0 ? weight : 1.0 / segmentAssumptions.size();
            weightSum += weightedValue;
            weightedRevenueNextYear += weightedValue * valueOrDefault(sectorParams.getRevenueNextYear(), input.getRevenueNextYear());
            weightedGrowth2To5 += weightedValue * valueOrDefault(sectorParams.getCompoundAnnualGrowth2_5(), input.getCompoundAnnualGrowth2_5());
            weightedOperatingMargin += weightedValue * valueOrDefault(sectorParams.getOperatingMarginNextYear(), input.getOperatingMarginNextYear());
            weightedTargetMargin += weightedValue * valueOrDefault(sectorParams.getTargetPreTaxOperatingMargin(), input.getTargetPreTaxOperatingMargin());
            weightedSalesToCapital1To5 += weightedValue * valueOrDefault(sectorParams.getSalesToCapitalYears1To5(), input.getSalesToCapitalYears1To5());
            weightedSalesToCapital6To10 += weightedValue * valueOrDefault(sectorParams.getSalesToCapitalYears6To10(), input.getSalesToCapitalYears6To10());
            weightedInitialCostCapital += weightedValue * valueOrDefault(sectorParams.getInitialCostCapital(), input.getInitialCostCapital());
        }

        double denominator = weightSum > 0.0 ? weightSum : 1.0;
        segmentParams.setWeightedRevenueNextYear(weightedRevenueNextYear / denominator);
        segmentParams.setWeightedCompoundAnnualGrowth2_5(weightedGrowth2To5 / denominator);
        segmentParams.setWeightedOperatingMarginNextYear(weightedOperatingMargin / denominator);
        segmentParams.setWeightedTargetPreTaxOperatingMargin(weightedTargetMargin / denominator);
        segmentParams.setConvergenceYearMargin(valueOrDefault(scenario.marginConvergenceYear(), input.getConvergenceYearMargin()));
        segmentParams.setWeightedSalesToCapitalYears1To5(weightedSalesToCapital1To5 / denominator);
        segmentParams.setWeightedSalesToCapitalYears6To10(weightedSalesToCapital6To10 / denominator);
        segmentParams.setWeightedInitialCostCapital(weightedInitialCostCapital / denominator);
        SegmentParameterContext.setParameters(segmentParams);
        input.setSegments(new SegmentResponseDTO(projectionSegments));
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

    private static Double scenarioBaseRevenue(ProspectusSegmentScenario segment, ProspectusFinancialPacket packet) {
        if (segment == null) {
            return null;
        }
        if (segment.baseRevenue() != null && Double.isFinite(segment.baseRevenue())) {
            return segment.baseRevenue();
        }
        if (!segment.projectedRevenuesOrEmpty().isEmpty()) {
            Double baseRevenue = segment.projectedRevenuesOrEmpty().get(0);
            if (baseRevenue != null && Double.isFinite(baseRevenue)) {
                return baseRevenue;
            }
        }
        String name = blankToNull(segment.name());
        if (name == null || packet == null || packet.getSegments() == null) {
            return null;
        }
        String normalizedName = normalizeKey(name);
        for (ProspectusSegmentFact fact : packet.getSegments()) {
            if (fact == null || fact.getSegmentName() == null) {
                continue;
            }
            if (normalizedName.equals(normalizeKey(fact.getSegmentName()))
                    && fact.getRevenueAmount() != null
                    && Double.isFinite(fact.getRevenueAmount())) {
                return fact.getRevenueAmount();
            }
        }
        return null;
    }

    private static Double scenarioTerminalRevenue(ProspectusSegmentScenario segment, ProspectusFinancialPacket packet) {
        if (segment == null) {
            return null;
        }
        if (segment.targetRevenue() != null && Double.isFinite(segment.targetRevenue())) {
            return segment.targetRevenue();
        }
        List<Double> projected = segment.projectedRevenuesOrEmpty();
        for (int i = projected.size() - 1; i >= 0; i--) {
            Double value = projected.get(i);
            if (value != null && Double.isFinite(value)) {
                return value;
            }
        }
        return scenarioBaseRevenue(segment, packet);
    }

    private static double scenarioSegmentWeight(
            Double baseRevenue,
            Double terminalRevenue,
            double baseWeightTotal,
            double targetWeightTotal,
            int segmentCount) {
        if (isPositiveFinite(terminalRevenue) && targetWeightTotal > 0.0) {
            return terminalRevenue / targetWeightTotal;
        }
        if (isPositiveFinite(baseRevenue) && baseWeightTotal > 0.0) {
            return baseRevenue / baseWeightTotal;
        }
        return segmentCount > 0 ? 1.0 / segmentCount : 0.0;
    }

    private static String scenarioSectorKey(String name, int index) {
        String slug = normalizeKey(name).replace('_', '-');
        return slug.isBlank() ? "prospectus-segment-" + (index + 1) : "prospectus-" + slug;
    }

    private static Double revenueGrowthFromProjection(
            ProspectusSegmentScenario segment,
            Double baseRevenue,
            int projectionIndex) {
        if (segment == null || segment.projectedRevenuesOrEmpty().size() <= projectionIndex) {
            return null;
        }
        Double prior = projectionIndex == 0
                ? baseRevenue
                : segment.projectedRevenuesOrEmpty().get(projectionIndex - 1);
        Double current = segment.projectedRevenuesOrEmpty().get(projectionIndex);
        if (!isPositiveFinite(prior) || current == null || !Double.isFinite(current)) {
            return null;
        }
        return ((current / prior) - 1.0) * 100.0;
    }

    private static Double revenueCagrFromProjection(
            ProspectusSegmentScenario segment,
            int fromIndex,
            int toIndex) {
        if (segment == null || segment.projectedRevenuesOrEmpty().size() <= toIndex || toIndex <= fromIndex) {
            return null;
        }
        Double start = segment.projectedRevenuesOrEmpty().get(fromIndex);
        Double end = segment.projectedRevenuesOrEmpty().get(toIndex);
        if (!isPositiveFinite(start) || !isPositiveFinite(end)) {
            return null;
        }
        return (Math.pow(end / start, 1.0 / (toIndex - fromIndex)) - 1.0) * 100.0;
    }

    @SafeVarargs
    private static <T> T firstPresent(T... values) {
        if (values == null) {
            return null;
        }
        for (T value : values) {
            if (value == null) {
                continue;
            }
            if (value instanceof Double doubleValue && !Double.isFinite(doubleValue)) {
                continue;
            }
            return value;
        }
        return null;
    }

    private static Double percentAssumption(Double value) {
        if (value == null || !Double.isFinite(value)) {
            return null;
        }
        return Math.abs(value) <= 1.0 ? value * 100.0 : value;
    }

    private static Double decimalAssumption(Double value) {
        Double percent = percentAssumption(value);
        return percent == null ? null : percent / 100.0;
    }

    private static Double engineInitialCostOfCapital(Double value) {
        Double percent = percentAssumption(value);
        return percent == null ? null : percent * 100.0;
    }

    private static Double valueOrDefault(Double value, Double fallback) {
        return value != null && Double.isFinite(value) ? value : fallback;
    }

    private static String normalizeKey(String value) {
        return value == null
                ? ""
                : value.toLowerCase(Locale.ROOT)
                        .replaceAll("[^a-z0-9]+", "-")
                        .replaceAll("(^-+|-+$)", "");
    }

    private static AssumptionTransparencyDTO buildProspectusTransparency(
            ValuationOutputDTO output,
            FinancialDataInput input,
            ProspectusFinancialPacket packet,
            ProspectusValuationBasis basis,
            ProspectusScenario scenario) {
        AssumptionTransparencyDTO dto = output.getAssumptionTransparency() == null
                ? new AssumptionTransparencyDTO()
                : output.getAssumptionTransparency();
        dto.setIndustryUs(output.getIndustryUs());
        dto.setIndustryGlobal(output.getIndustryGlobal());
        dto.setCurrency(output.getCurrency());
        dto.setRequestPolicyMode(scenario == null ? "prospectus_reviewed" : "prospectus_explicit_scenario");
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
        boolean explicitSegmentScenario = hasScenarioSegments(scenario);
        if (scenario != null) {
            warnings.add("Prospectus explicit scenario supplied model assumptions; mechanical diagnostic value is not the headline valuation.");
        }
        boolean validSegmentBaseline = segmentParams != null && segmentParams.hasValidParameters();
        List<AssumptionTransparencyDTO.BaselineIssue> segmentMaterialityIssues = explicitSegmentScenario
                ? List.of()
                : segmentMaterialityIssues(packet);
        unsupportedIssues.addAll(segmentMaterialityIssues);
        for (AssumptionTransparencyDTO.BaselineIssue issue : segmentMaterialityIssues) {
            warnings.add(issue.getReason());
        }
        List<AssumptionTransparencyDTO.BaselineIssue> industryMappingIssues = industryMappingIssues(
                input,
                explicitSegmentScenario,
                validSegmentBaseline);
        unsupportedIssues.addAll(industryMappingIssues);
        for (AssumptionTransparencyDTO.BaselineIssue issue : industryMappingIssues) {
            warnings.add(issue.getReason());
        }
        boolean challenged = !basis.clean() || !segmentMaterialityIssues.isEmpty() || !industryMappingIssues.isEmpty();
        dto.setValuationCaseStatus(challenged ? "challenged_valuation_case" : basis.valuationCaseStatus());

        if (validSegmentBaseline) {
            dto.setBaselineQuality(explicitSegmentScenario ? "prospectus_explicit_scenario" : "segment_weighted_baseline");
            dto.setBaselineUseStatus(challenged
                    ? "challenged_baseline"
                    : explicitSegmentScenario ? "scenario_supported" : "validated_segment_weighted");
            dto.setSegmentAware(true);
            dto.setSegmentCount(segmentParams.getSegmentCount());
            dto.setSegmentCoveragePct(value(segmentParams.getSegmentCoveragePct()));
            dto.setMappedIndustries(mappedIndustries(segmentParams));
            dto.setWeightedBaselineAssumptions(weightedAssumptions(segmentParams));
            dto.setTargetOperatingMarginSource(explicitSegmentScenario
                    ? "Prospectus explicit scenario"
                    : "Segment-weighted prospectus baseline");
            dto.setTargetOperatingMarginStatus(explicitSegmentScenario ? "scenario_supported" : "segment_weighted");
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
        if (facts.isEmpty() && hasSegmentCandidateTables(packet)) {
            issues.add(baselineIssue(
                    "segments",
                    "segment_candidates_require_scenario",
                    "prospectus returned raw segment candidate tables; explicit scenario.segments is required to choose material rows and mappings before this can be a clean valuation case."));
            return issues;
        }
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

    private static List<AssumptionTransparencyDTO.BaselineIssue> industryMappingIssues(
            FinancialDataInput input,
            boolean explicitSegmentScenario,
            boolean validSegmentBaseline) {
        if (explicitSegmentScenario || validSegmentBaseline || !isUnmappedProspectusIndustry(input == null ? null : input.getIndustry())) {
            return List.of();
        }
        return List.of(baselineIssue(
                "industry_mapping",
                "industry_mapping_missing",
                "No reviewed prospectus industry mapping was provided; an agent or user must supply a company or segment industry mapping before this can be a clean valuation case."));
    }

    private static boolean isUnmappedProspectusIndustry(String industry) {
        String normalized = blankToNull(industry);
        return normalized == null || "unmapped-prospectus".equalsIgnoreCase(normalized);
    }

    private static boolean hasSegmentCandidateTables(ProspectusFinancialPacket packet) {
        return packet != null
                && packet.getSegmentCandidateTables() != null
                && packet.getSegmentCandidateTables().stream()
                        .filter(Objects::nonNull)
                        .map(ProspectusRawTable::rows)
                        .anyMatch(rows -> rows != null && !rows.isEmpty());
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
