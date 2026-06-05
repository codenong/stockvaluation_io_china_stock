package io.stockvaluation.service;

import io.stockvaluation.config.ValuationAssumptionProperties;
import io.stockvaluation.domain.CostOfCapital;
import io.stockvaluation.domain.IndustryAveragesGlobal;
import io.stockvaluation.domain.IndustryAveragesUS;
import io.stockvaluation.domain.InputStatDistribution;
import io.stockvaluation.domain.SectorMapping;
import io.stockvaluation.dto.BasicInfoDataDTO;
import io.stockvaluation.dto.CompanyDataDTO;
import io.stockvaluation.dto.CompanyDriveDataDTO;
import io.stockvaluation.dto.FinancialDataDTO;
import io.stockvaluation.provider.BalanceSheetSnapshot;
import io.stockvaluation.provider.IncomeStatementSnapshot;
import io.stockvaluation.provider.prospectus.ProspectusFinancialPacket;
import io.stockvaluation.provider.prospectus.ProspectusFinancialSnapshotMapper;
import io.stockvaluation.provider.prospectus.ProspectusMappedSnapshots;
import io.stockvaluation.provider.prospectus.ProspectusSegmentFact;
import io.stockvaluation.repository.CostOfCapitalRepository;
import io.stockvaluation.repository.CountryEquityRepository;
import io.stockvaluation.repository.IndustryAveragesGlobalRepository;
import io.stockvaluation.repository.IndustryAveragesUSRepository;
import io.stockvaluation.repository.InputStatRepository;
import io.stockvaluation.repository.RiskFreeRateRepository;
import io.stockvaluation.repository.SectorMappingRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class ProspectusCompanyDataAssembler {

    private final ProspectusFinancialSnapshotMapper mapper;
    private final CountryEquityRepository countryEquityRepository;
    private final SectorMappingRepository sectorMappingRepository;
    private final IndustryAveragesUSRepository industryAvgUSRepository;
    private final IndustryAveragesGlobalRepository industryAvgGloRepository;
    private final InputStatRepository inputStatRepository;
    private final CostOfCapitalRepository costOfCapitalRepository;
    private final RiskFreeRateRepository riskFreeRateRepository;
    private final ValuationAssumptionProperties valuationAssumptionProperties;

    public CompanyDataDTO assemble(ProspectusFinancialPacket packet) {
        ProspectusMappedSnapshots snapshots = mapper.map(packet);
        IncomeStatementSnapshot latestIncome = latest(snapshots.yearlyIncome());
        IncomeStatementSnapshot priorIncome = prior(snapshots.yearlyIncome());
        BalanceSheetSnapshot latestBalance = latest(snapshots.yearlyBalance());
        String industryKey = resolveIndustryKey(packet);
        SectorMapping sectorMapping = sectorMappingRepository.findByIndustryName(industryKey);
        String damodaranIndustry = sectorMapping == null ? null : sectorMapping.getIndustryAsPerExcel();

        BasicInfoDataDTO basic = new BasicInfoDataDTO();
        basic.setTicker(symbol(packet));
        basic.setCompanyName(packet.getCompany().getLegalName());
        basic.setCountryOfIncorporation(defaultString(packet.getCompany().getCountryOfIncorporation(), "United States"));
        basic.setCurrency(defaultString(packet.getCompany().getCurrency(), "USD"));
        basic.setStockCurrency(defaultString(packet.getCompany().getCurrency(), "USD"));
        basic.setIndustryUs(industryKey);
        basic.setIndustryGlobal(industryKey);
        basic.setDateOfValuation(LocalDate.now());

        FinancialDataDTO financial = new FinancialDataDTO();
        financial.setRevenueTTM(value(latestIncome.totalRevenue()));
        financial.setRevenueLTM(value(priorIncome.totalRevenue(), latestIncome.totalRevenue()));
        financial.setOperatingIncomeTTM(value(latestIncome.operatingIncome()));
        financial.setOperatingIncomeLTM(value(priorIncome.operatingIncome(), latestIncome.operatingIncome()));
        financial.setInterestExpenseTTM(value(latestIncome.interestExpense()));
        financial.setInterestExpenseLTM(value(priorIncome.interestExpense(), latestIncome.interestExpense()));
        financial.setBookValueEqualityTTM(value(latestBalance.bookValueEquity()));
        financial.setBookValueEqualityLTM(value(latestBalance.bookValueEquity()));
        financial.setBookValueDebtTTM(value(latestBalance.totalDebt()));
        financial.setBookValueDebtLTM(value(latestBalance.totalDebt()));
        financial.setCashAndMarkablTTM(value(latestBalance.cashAndShortTermInvestments()));
        financial.setCashAndMarkablLTM(value(latestBalance.cashAndShortTermInvestments()));
        financial.setNonOperatingAssetTTM(0.0);
        financial.setNonOperatingAssetLTM(0.0);
        financial.setMinorityInterestTTM(value(latestBalance.minorityInterest()));
        financial.setMinorityInterestLTM(0.0);
        financial.setNoOfShareOutstanding(latestBalance.sharesOutstanding());
        financial.setStockPrice(packet.getOffering() == null ? null : packet.getOffering().getOfferingPrice());
        financial.setHighestStockPrice(financial.getStockPrice());
        financial.setLowestStockPrice(financial.getStockPrice());
        financial.setPreviousDayStockPrice(financial.getStockPrice());
        financial.setResearchAndDevelopmentMap(researchAndDevelopmentMap(latestIncome, priorIncome));
        financial.setSourceProvenance(packet.getSourceProvenance());

        double marginalTaxRate = countryEquityRepository
                .findCorporateTaxRateByCountry(basic.getCountryOfIncorporation())
                .orElse(21.0);
        financial.setMarginalTaxRate(marginalTaxRate);
        financial.setEffectiveTaxRate(marginalTaxRate / 100.0);

        CompanyDriveDataDTO drive = driveData(basic, financial, damodaranIndustry);
        CompanyDataDTO companyData = new CompanyDataDTO();
        companyData.setBasicInfoDataDTO(basic);
        companyData.setFinancialDataDTO(financial);
        companyData.setCompanyDriveDataDTO(drive);
        return companyData;
    }

    private CompanyDriveDataDTO driveData(BasicInfoDataDTO basic, FinancialDataDTO financial, String damodaranIndustry) {
        CompanyDriveDataDTO drive = new CompanyDriveDataDTO();
        double revenueGrowth = growth(financial.getRevenueTTM(), financial.getRevenueLTM());
        double currentMargin = safeRatio(financial.getOperatingIncomeTTM(), financial.getRevenueTTM());
        drive.setRevenueNextYear(revenueGrowth);
        drive.setOperatingMarginNextYear(currentMargin);
        drive.setCompoundAnnualGrowth2_5(revenueGrowth);
        double riskFreeRate = riskFreeRateRepository.findRiskFreeRateByCurrency(basic.getCurrency())
                .orElse(valuationAssumptionProperties.getBaselineRiskFreeRate());
        drive.setRiskFreeRate(riskFreeRate);
        drive.setConvergenceYearMargin(valuationAssumptionProperties.getConvergenceYearMargin());

        Optional<InputStatDistribution> distribution = damodaranIndustry == null
                ? Optional.empty()
                : inputStatRepository.findFirstByIndustryGroupOrderByIdAsc(damodaranIndustry);
        if (distribution.isPresent()) {
            drive.setTargetPreTaxOperatingMargin(distribution.get().getPreTaxOperatingMarginMedian() / 100.0);
            drive.setSalesToCapitalYears1To5(distribution.get().getSalesToInvestedCapitalThirdQuartile());
        } else {
            drive.setTargetPreTaxOperatingMargin(currentMargin);
            drive.setSalesToCapitalYears1To5(2.0);
        }
        drive.setSalesToCapitalYears6To10(resolveSalesToCapital(basic, damodaranIndustry, drive.getSalesToCapitalYears1To5()));
        drive.setInitialCostCapital(resolveInitialCostOfCapital(basic, damodaranIndustry));
        return drive;
    }

    private double resolveSalesToCapital(BasicInfoDataDTO basic, String damodaranIndustry, double fallback) {
        if (damodaranIndustry == null) {
            return fallback;
        }
        if ("United States".equalsIgnoreCase(basic.getCountryOfIncorporation())) {
            return industryAvgUSRepository.findSalesToCapitalByIndustryName(damodaranIndustry).orElse(fallback);
        }
        return industryAvgGloRepository.findSalesToCapitalByIndustryName(damodaranIndustry).orElse(fallback);
    }

    private double resolveInitialCostOfCapital(BasicInfoDataDTO basic, String damodaranIndustry) {
        if (damodaranIndustry != null) {
            if ("United States".equalsIgnoreCase(basic.getCountryOfIncorporation())) {
                IndustryAveragesUS us = industryAvgUSRepository.findByIndustryName(damodaranIndustry);
                if (us != null && us.getCostOfCapital() > 0.0) {
                    return us.getCostOfCapital() / 100.0;
                }
            } else {
                IndustryAveragesGlobal global = industryAvgGloRepository.findByIndustryName(damodaranIndustry);
                if (global != null && global.getCostOfCapital() > 0.0) {
                    return global.getCostOfCapital() / 100.0;
                }
            }
        }
        Optional<CostOfCapital> cost = costOfCapitalRepository.findCostOfCapitalByRegion("US");
        return cost.map(CostOfCapital::getMedian)
                .map(this::parsePercent)
                .orElse(0.08);
    }

    private double parsePercent(String value) {
        if (value == null || value.isBlank()) {
            return 0.08;
        }
        try {
            double parsed = Double.parseDouble(value);
            return parsed > 1.0 ? parsed / 100.0 : parsed;
        } catch (NumberFormatException ignored) {
            return 0.08;
        }
    }

    private static Map<String, Double> researchAndDevelopmentMap(
            IncomeStatementSnapshot latestIncome,
            IncomeStatementSnapshot priorIncome) {
        Map<String, Double> values = new LinkedHashMap<>();
        values.put("currentR&D-0", value(latestIncome.researchAndDevelopment()));
        values.put("currentR&D-1", value(priorIncome.researchAndDevelopment()));
        return values;
    }

    private static String resolveIndustryKey(ProspectusFinancialPacket packet) {
        if (packet.getSegments() != null) {
            for (ProspectusSegmentFact segment : packet.getSegments()) {
                if (segment.getSectorKey() != null && !segment.getSectorKey().isBlank()) {
                    return segment.getSectorKey();
                }
            }
        }
        if (packet.getCompany() != null
                && packet.getCompany().getIndustryKey() != null
                && !packet.getCompany().getIndustryKey().isBlank()) {
            return packet.getCompany().getIndustryKey();
        }
        return "aerospace-defense";
    }

    private static String symbol(ProspectusFinancialPacket packet) {
        if (packet.getCompany() != null
                && packet.getCompany().getTickerOrExpectedSymbol() != null
                && !packet.getCompany().getTickerOrExpectedSymbol().isBlank()) {
            return packet.getCompany().getTickerOrExpectedSymbol().toUpperCase();
        }
        return "PROSPECTUS";
    }

    private static <T> T latest(Map<String, T> values) {
        if (values == null || values.isEmpty()) {
            throw new IllegalArgumentException("prospectus packet did not map required financial snapshots");
        }
        return values.entrySet().stream().max(Map.Entry.comparingByKey()).orElseThrow().getValue();
    }

    private static <T> T prior(Map<String, T> values) {
        if (values == null || values.isEmpty()) {
            throw new IllegalArgumentException("prospectus packet did not map required financial snapshots");
        }
        return values.entrySet().stream()
                .sorted(Map.Entry.<String, T>comparingByKey().reversed())
                .skip(1)
                .map(Map.Entry::getValue)
                .findFirst()
                .orElse(latest(values));
    }

    private static double growth(Double current, Double prior) {
        if (current == null || prior == null || prior == 0.0) {
            return 0.05;
        }
        double growth = (current - prior) / prior;
        if (!Double.isFinite(growth)) {
            return 0.05;
        }
        return Math.max(-0.5, Math.min(0.6, growth));
    }

    private static double safeRatio(Double numerator, Double denominator) {
        if (numerator == null || denominator == null || denominator == 0.0) {
            return 0.0;
        }
        double ratio = numerator / denominator;
        return Double.isFinite(ratio) ? ratio : 0.0;
    }

    private static double value(Double value) {
        return value == null ? 0.0 : value;
    }

    private static double value(Double value, Double fallback) {
        return value == null ? value(fallback) : value;
    }

    private static String defaultString(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }
}
