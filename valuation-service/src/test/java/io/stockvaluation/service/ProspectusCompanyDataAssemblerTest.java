package io.stockvaluation.service;

import io.stockvaluation.config.ValuationAssumptionProperties;
import io.stockvaluation.domain.CostOfCapital;
import io.stockvaluation.domain.SectorMapping;
import io.stockvaluation.provider.prospectus.ProspectusCompanyIdentity;
import io.stockvaluation.provider.prospectus.ProspectusTestPackets;
import io.stockvaluation.provider.prospectus.ProspectusFinancialSnapshotMapper;
import io.stockvaluation.repository.CostOfCapitalRepository;
import io.stockvaluation.repository.CountryEquityRepository;
import io.stockvaluation.repository.IndustryAveragesGlobalRepository;
import io.stockvaluation.repository.IndustryAveragesUSRepository;
import io.stockvaluation.repository.InputStatRepository;
import io.stockvaluation.repository.RiskFreeRateRepository;
import io.stockvaluation.repository.SectorMappingRepository;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ProspectusCompanyDataAssemblerTest {

    @Test
    void leavesProspectusIndustryUnmappedWhenNoReviewedMappingExists() {
        CountryEquityRepository countryEquityRepository = mock(CountryEquityRepository.class);
        SectorMappingRepository sectorMappingRepository = mock(SectorMappingRepository.class);
        IndustryAveragesUSRepository industryAvgUSRepository = mock(IndustryAveragesUSRepository.class);
        IndustryAveragesGlobalRepository industryAvgGloRepository = mock(IndustryAveragesGlobalRepository.class);
        InputStatRepository inputStatRepository = mock(InputStatRepository.class);
        CostOfCapitalRepository costOfCapitalRepository = mock(CostOfCapitalRepository.class);
        RiskFreeRateRepository riskFreeRateRepository = mock(RiskFreeRateRepository.class);
        ValuationAssumptionProperties valuationAssumptionProperties = mock(ValuationAssumptionProperties.class);
        when(countryEquityRepository.findCorporateTaxRateByCountry("United States")).thenReturn(Optional.of(21.0));
        when(riskFreeRateRepository.findRiskFreeRateByCurrency("USD")).thenReturn(Optional.of(4.5));
        when(valuationAssumptionProperties.getBaselineRiskFreeRate()).thenReturn(4.5);
        when(valuationAssumptionProperties.getConvergenceYearMargin()).thenReturn(5.0);

        var packet = ProspectusTestPackets.reviewedPacket();
        packet.setCompany(new ProspectusCompanyIdentity(
                "Example IPO Corp.",
                "EXMP",
                "United States",
                "USD",
                null));
        packet.setSegments(List.of());

        ProspectusCompanyDataAssembler assembler = new ProspectusCompanyDataAssembler(
                new ProspectusFinancialSnapshotMapper(),
                countryEquityRepository,
                sectorMappingRepository,
                industryAvgUSRepository,
                industryAvgGloRepository,
                inputStatRepository,
                costOfCapitalRepository,
                riskFreeRateRepository,
                valuationAssumptionProperties);

        var basic = assembler.assemble(packet).getBasicInfoDataDTO();

        assertEquals("unmapped-prospectus", basic.getIndustryUs());
        assertEquals("unmapped-prospectus", basic.getIndustryGlobal());
    }

    @Test
    void preservesAllExtractedProspectusResearchAndDevelopmentYears() {
        CountryEquityRepository countryEquityRepository = mock(CountryEquityRepository.class);
        SectorMappingRepository sectorMappingRepository = mock(SectorMappingRepository.class);
        IndustryAveragesUSRepository industryAvgUSRepository = mock(IndustryAveragesUSRepository.class);
        IndustryAveragesGlobalRepository industryAvgGloRepository = mock(IndustryAveragesGlobalRepository.class);
        InputStatRepository inputStatRepository = mock(InputStatRepository.class);
        CostOfCapitalRepository costOfCapitalRepository = mock(CostOfCapitalRepository.class);
        RiskFreeRateRepository riskFreeRateRepository = mock(RiskFreeRateRepository.class);
        ValuationAssumptionProperties valuationAssumptionProperties = mock(ValuationAssumptionProperties.class);
        SectorMapping sectorMapping = new SectorMapping();
        sectorMapping.setIndustryAsPerExcel("Aerospace/Defense");
        when(sectorMappingRepository.findByIndustryName("aerospace-defense")).thenReturn(sectorMapping);
        when(countryEquityRepository.findCorporateTaxRateByCountry("United States")).thenReturn(Optional.of(21.0));
        when(riskFreeRateRepository.findRiskFreeRateByCurrency("USD")).thenReturn(Optional.of(4.5));
        when(inputStatRepository.findFirstByIndustryGroupOrderByIdAsc("Aerospace/Defense")).thenReturn(Optional.empty());
        CostOfCapital cost = new CostOfCapital();
        cost.setMedian("0.08");
        when(costOfCapitalRepository.findCostOfCapitalByRegion("US")).thenReturn(Optional.of(cost));
        when(valuationAssumptionProperties.getConvergenceYearMargin()).thenReturn(5.0);
        var packet = ProspectusTestPackets.reviewedPacket();
        var provenance = packet.getSourceProvenance();
        packet.getFinancials().getIncomeStatement().add(ProspectusTestPackets.fact(
                "research_and_development",
                "Research and development",
                "Year Ended December 31, 2024",
                180_000_000.0,
                "millions",
                provenance));
        var rd2023 = ProspectusTestPackets.fact(
                "research_and_development",
                "Research and development",
                "Year Ended December 31, 2023",
                120_000_000.0,
                "millions",
                provenance);
        rd2023.setPeriodEnd("2023-12-31");
        packet.getFinancials().getIncomeStatement().add(rd2023);

        ProspectusCompanyDataAssembler assembler = new ProspectusCompanyDataAssembler(
                new ProspectusFinancialSnapshotMapper(),
                countryEquityRepository,
                sectorMappingRepository,
                industryAvgUSRepository,
                industryAvgGloRepository,
                inputStatRepository,
                costOfCapitalRepository,
                riskFreeRateRepository,
                valuationAssumptionProperties);

        Map<String, Double> rd = assembler.assemble(packet).getFinancialDataDTO().getResearchAndDevelopmentMap();

        assertEquals(3, rd.size());
        assertEquals(250_000_000.0, rd.get("currentR&D-0"));
        assertEquals(180_000_000.0, rd.get("currentR&D-1"));
        assertEquals(120_000_000.0, rd.get("currentR&D-2"));
    }
}
