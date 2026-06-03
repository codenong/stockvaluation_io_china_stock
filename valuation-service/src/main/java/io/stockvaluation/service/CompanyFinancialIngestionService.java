package io.stockvaluation.service;

import io.stockvaluation.dto.FinancialDataDTO;
import io.stockvaluation.provider.BalanceSheetSnapshot;
import io.stockvaluation.provider.CashFlowSnapshot;
import io.stockvaluation.provider.DataProvider;
import io.stockvaluation.provider.FinancialSnapshotProvider;
import io.stockvaluation.provider.IncomeStatementSnapshot;
import io.stockvaluation.provider.SourceProvenance;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;
import java.util.function.Function;
import java.util.function.Predicate;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class CompanyFinancialIngestionService {

    private final DataProvider dataProvider;

    public FinancialIngestionData ingest(String ticker, Map<String, Object> basicInfoMap) {
        return ingest(ticker, basicInfoMap, dataProvider);
    }

    public FinancialIngestionData ingest(String ticker, Map<String, Object> basicInfoMap, FinancialSnapshotProvider financialDataProvider) {
        Map<String, IncomeStatementSnapshot> quarterlyIncomeSnapshots =
                financialDataProvider.getIncomeStatementSnapshots(ticker, "quarterly");
        Map<String, IncomeStatementSnapshot> yearlyIncomeSnapshots =
                financialDataProvider.getIncomeStatementSnapshots(ticker, "yearly");
        Map<String, CashFlowSnapshot> quarterlyCashFlowSnapshots =
                safeCashFlowSnapshots(financialDataProvider, ticker, "quarterly");
        Map<String, CashFlowSnapshot> yearlyCashFlowSnapshots =
                safeCashFlowSnapshots(financialDataProvider, ticker, "yearly");

        Map<String, IncomeStatementSnapshot> recentQuarterlyIncome = getMostRecentPeriods(quarterlyIncomeSnapshots, 4);
        double totalRevenueTTM = calculateTotal(recentQuarterlyIncome, IncomeStatementSnapshot::totalRevenue);
        double operatingIncomeTTM = calculateTotal(recentQuarterlyIncome, IncomeStatementSnapshot::operatingIncome);
        double interestExpenseTTM = calculateTotal(recentQuarterlyIncome, IncomeStatementSnapshot::interestExpense);

        FinancialDataDTO financialDataDTO = new FinancialDataDTO();
        financialDataDTO.setResearchAndDevelopmentMap(
                mapResearchAndDevelopmentHistory(yearlyIncomeSnapshots, quarterlyIncomeSnapshots));

        List<Double> historicalRevenue = new ArrayList<>();
        List<Double> historicalMargins = new ArrayList<>();
        if (yearlyIncomeSnapshots.size() > 3) {
            Map<String, IncomeStatementSnapshot> sortedMap = new TreeMap<>(yearlyIncomeSnapshots);
            for (IncomeStatementSnapshot snapshot : sortedMap.values()) {
                if (snapshot == null
                        || snapshot.totalRevenue() == null
                        || snapshot.operatingIncome() == null
                        || snapshot.totalRevenue() == 0.0) {
                    continue;
                }
                historicalRevenue.add(snapshot.totalRevenue());
                historicalMargins.add(snapshot.operatingIncome() / snapshot.totalRevenue());
            }
        }

        IncomeStatementSnapshot previousYearIncomeSnapshot =
                findSnapshotByYear(yearlyIncomeSnapshots, targetYears(1, 2, 3),
                        snapshot -> snapshot.totalRevenue() != null,
                        IncomeStatementSnapshot.empty());
        IncomeStatementSnapshot priorYearShareSnapshot =
                findSnapshotByYear(yearlyIncomeSnapshots, targetYears(2, 3, 4),
                        snapshot -> snapshot.dilutedAverageShares() != null,
                        IncomeStatementSnapshot.empty());
        CashFlowSnapshot recentYearlyCashFlowSnapshot =
                findSnapshotByYear(yearlyCashFlowSnapshots, targetYears(1, 2, 3),
                        snapshot -> snapshot.stockBasedCompensation() != null,
                        CashFlowSnapshot.empty());

        Double revenueLTM = previousYearIncomeSnapshot.totalRevenue();
        if (Objects.equals(revenueLTM, totalRevenueTTM)) {
            IncomeStatementSnapshot olderIncomeSnapshot =
                    findSnapshotByYear(yearlyIncomeSnapshots, targetYears(2, 3),
                            snapshot -> snapshot.totalRevenue() != null,
                            IncomeStatementSnapshot.empty());
            revenueLTM = olderIncomeSnapshot.totalRevenue();
        }

        double revenueLtmValue = valueOrZero(revenueLTM);
        double operatingIncomeLtmValue = valueOrZero(previousYearIncomeSnapshot.operatingIncome());
        double interestExpenseLtmValue = valueOrZero(previousYearIncomeSnapshot.interestExpense());
        double taxProvision = valueOrZero(previousYearIncomeSnapshot.taxProvision());
        Double preTaxIncome = previousYearIncomeSnapshot.pretaxIncome();

        Map<String, BalanceSheetSnapshot> quarterlyBalanceSnapshots =
                financialDataProvider.getBalanceSheetSnapshots(ticker, "quarterly");
        BalanceSheetSnapshot mostRecentQuarterlyBalance =
                getMostRecentSnapshot(quarterlyBalanceSnapshots, BalanceSheetSnapshot.empty());

        double bookValueEquityTTM = valueOrZero(mostRecentQuarterlyBalance.bookValueEquity());
        double bookValueDebtTTM = valueOrZero(mostRecentQuarterlyBalance.totalDebt());
        double cashAndMarketableTTM = valueOrZero(mostRecentQuarterlyBalance.cashAndShortTermInvestments());
        Double numberOfShareOutStanding = mostRecentQuarterlyBalance.sharesOutstanding();

        Map<String, BalanceSheetSnapshot> yearlyBalanceSnapshots =
                financialDataProvider.getBalanceSheetSnapshots(ticker, "yearly");
        BalanceSheetSnapshot recentYearlyBalanceSnapshot =
                findSnapshotByYear(yearlyBalanceSnapshots, targetYears(1, 2, 3),
                        snapshot -> true,
                        BalanceSheetSnapshot.empty());

        double bookValueEquityLTM = valueOrZero(recentYearlyBalanceSnapshot.bookValueEquity());
        double bookValueDebtLTM = valueOrZero(recentYearlyBalanceSnapshot.totalDebt());
        double cashAndMarketableLTM = valueOrZero(recentYearlyBalanceSnapshot.cashAndShortTermInvestments());
        if (numberOfShareOutStanding == null) {
            numberOfShareOutStanding = recentYearlyBalanceSnapshot.sharesOutstanding();
        }

        financialDataDTO.setRevenueTTM(totalRevenueTTM == 0.0 ? revenueLtmValue : totalRevenueTTM);
        financialDataDTO.setRevenueLTM(revenueLtmValue);

        financialDataDTO.setOperatingIncomeTTM(operatingIncomeTTM == 0.0 ? operatingIncomeLtmValue : operatingIncomeTTM);
        financialDataDTO.setOperatingIncomeLTM(operatingIncomeLtmValue);

        financialDataDTO.setInterestExpenseTTM(interestExpenseTTM == 0.0 ? interestExpenseLtmValue : interestExpenseTTM);
        financialDataDTO.setInterestExpenseLTM(interestExpenseLtmValue);

        financialDataDTO.setBookValueEqualityTTM(bookValueEquityTTM == 0.0 ? bookValueEquityLTM : bookValueEquityTTM);
        financialDataDTO.setBookValueEqualityLTM(bookValueEquityLTM);

        financialDataDTO.setBookValueDebtTTM(bookValueDebtTTM == 0.0 ? bookValueDebtLTM : bookValueDebtTTM);
        financialDataDTO.setBookValueDebtLTM(bookValueDebtLTM);

        financialDataDTO.setCashAndMarkablTTM(cashAndMarketableTTM == 0.0 ? cashAndMarketableLTM : cashAndMarketableTTM);
        financialDataDTO.setCashAndMarkablLTM(cashAndMarketableLTM);

        financialDataDTO.setNonOperatingAssetTTM(0.0);
        financialDataDTO.setNonOperatingAssetLTM(0.0);
        financialDataDTO.setMinorityInterestTTM(valueOrZero(recentYearlyBalanceSnapshot.minorityInterest()));
        financialDataDTO.setMinorityInterestLTM(0.0);
        financialDataDTO.setNoOfShareOutstanding(numberOfShareOutStanding);
        financialDataDTO.setBasicSharesOutstanding(previousYearIncomeSnapshot.basicAverageShares());
        financialDataDTO.setDilutedSharesOutstanding(previousYearIncomeSnapshot.dilutedAverageShares());
        financialDataDTO.setPriorDilutedSharesOutstanding(priorYearShareSnapshot.dilutedAverageShares());
        financialDataDTO.setStockBasedCompensationLTM(recentYearlyCashFlowSnapshot.stockBasedCompensation());
        double stockBasedCompensationTTM = calculateTotal(
                getMostRecentPeriods(quarterlyCashFlowSnapshots, 4),
                CashFlowSnapshot::stockBasedCompensation);
        Double stockBasedCompensationTtmValue;
        if (stockBasedCompensationTTM == 0.0) {
            stockBasedCompensationTtmValue = recentYearlyCashFlowSnapshot.stockBasedCompensation();
        } else {
            stockBasedCompensationTtmValue = stockBasedCompensationTTM;
        }
        financialDataDTO.setStockBasedCompensationTTM(stockBasedCompensationTtmValue);

        financialDataDTO.setHighestStockPrice(toDouble(basicInfoMap.get("dayHigh")));
        financialDataDTO.setPreviousDayStockPrice(toDouble(basicInfoMap.get("previousClose")));
        financialDataDTO.setLowestStockPrice(toDouble(basicInfoMap.get("dayLow")));
        financialDataDTO.setStockPrice(toDouble(basicInfoMap.get("currentPrice")));

        return new FinancialIngestionData(
                financialDataDTO,
                historicalRevenue,
                historicalMargins,
                taxProvision,
                preTaxIncome,
                selectLatestProvenance(
                        quarterlyIncomeSnapshots,
                        yearlyIncomeSnapshots,
                        quarterlyBalanceSnapshots,
                        yearlyBalanceSnapshots));
    }

    private static int[] targetYears(int... offsets) {
        int currentYear = LocalDate.now().getYear();
        int[] years = new int[offsets.length];
        for (int i = 0; i < offsets.length; i++) {
            years[i] = currentYear - offsets[i];
        }
        return years;
    }

    private static <T> T findSnapshotByYear(
            Map<String, T> snapshots,
            int[] targetYears,
            Predicate<T> acceptSnapshot,
            T fallbackValue) {
        for (int targetYear : targetYears) {
            for (Map.Entry<String, T> entry : snapshots.entrySet()) {
                if (extractYear(entry.getKey()) != targetYear) {
                    continue;
                }
                T snapshot = entry.getValue();
                if (snapshot != null && acceptSnapshot.test(snapshot)) {
                    return snapshot;
                }
            }
        }
        return fallbackValue;
    }

    private static <T> Map<String, T> getMostRecentPeriods(Map<String, T> snapshots, int periods) {
        return snapshots.entrySet().stream()
                .sorted(Map.Entry.<String, T>comparingByKey().reversed())
                .limit(periods)
                .collect(Collectors.toMap(
                        Map.Entry::getKey,
                        Map.Entry::getValue,
                        (left, right) -> left,
                        LinkedHashMap::new));
    }

    private static BalanceSheetSnapshot getMostRecentSnapshot(
            Map<String, BalanceSheetSnapshot> snapshots,
            BalanceSheetSnapshot fallbackValue) {
        return snapshots.entrySet().stream()
                .max(Map.Entry.comparingByKey())
                .map(Map.Entry::getValue)
                .orElse(fallbackValue);
    }

    private static int extractYear(String timestampMillis) {
        long timestamp = Long.parseLong(timestampMillis);
        return Instant.ofEpochMilli(timestamp)
                .atZone(ZoneId.systemDefault())
                .toLocalDate()
                .getYear();
    }

    private static <T> double calculateTotal(
            Map<String, T> snapshots,
            Function<T, Double> extractor) {
        return snapshots.values().stream()
                .filter(Objects::nonNull)
                .map(extractor)
                .filter(Objects::nonNull)
                .mapToDouble(Double::doubleValue)
                .sum();
    }

    private Map<String, Double> mapResearchAndDevelopmentHistory(
            Map<String, IncomeStatementSnapshot> yearlySnapshots,
            Map<String, IncomeStatementSnapshot> quarterlySnapshots) {
        Map<String, Double> researchAndDevelopmentMap = new TreeMap<>();

        int index = 1;
        for (IncomeStatementSnapshot snapshot : getMostRecentPeriods(yearlySnapshots, 4).values()) {
            researchAndDevelopmentMap.put("currentR&D" + (-index), valueOrZero(snapshot.researchAndDevelopment()));
            index++;
        }

        double currentResearchAndDevelopment = getMostRecentPeriods(quarterlySnapshots, 4)
                .values()
                .stream()
                .filter(Objects::nonNull)
                .map(IncomeStatementSnapshot::researchAndDevelopment)
                .filter(Objects::nonNull)
                .mapToDouble(Double::doubleValue)
                .sum();
        researchAndDevelopmentMap.put("currentR&D-0", currentResearchAndDevelopment);

        return researchAndDevelopmentMap;
    }

    private static Map<String, CashFlowSnapshot> safeCashFlowSnapshots(
            FinancialSnapshotProvider financialDataProvider,
            String ticker,
            String freq) {
        try {
            Map<String, CashFlowSnapshot> snapshots = financialDataProvider.getCashFlowSnapshots(ticker, freq);
            return snapshots != null ? snapshots : Map.of();
        } catch (RuntimeException ignored) {
            return Map.of();
        }
    }

    private static double valueOrZero(Double value) {
        return value == null ? 0.0 : value;
    }

    private static Double toDouble(Object value) {
        if (value instanceof Number number) {
            return number.doubleValue();
        }
        return null;
    }

    private static SourceProvenance selectLatestProvenance(
            Map<String, IncomeStatementSnapshot> quarterlyIncomeSnapshots,
            Map<String, IncomeStatementSnapshot> yearlyIncomeSnapshots,
            Map<String, BalanceSheetSnapshot> quarterlyBalanceSnapshots,
            Map<String, BalanceSheetSnapshot> yearlyBalanceSnapshots) {
        SourceProvenance latest = latestIncomeProvenance(quarterlyIncomeSnapshots);
        if (latest != null) {
            return latest;
        }
        latest = latestBalanceProvenance(quarterlyBalanceSnapshots);
        if (latest != null) {
            return latest;
        }
        latest = latestIncomeProvenance(yearlyIncomeSnapshots);
        if (latest != null) {
            return latest;
        }
        return latestBalanceProvenance(yearlyBalanceSnapshots);
    }

    private static SourceProvenance latestIncomeProvenance(Map<String, IncomeStatementSnapshot> snapshots) {
        if (snapshots == null || snapshots.isEmpty()) {
            return null;
        }
        return snapshots.entrySet().stream()
                .sorted(Map.Entry.<String, IncomeStatementSnapshot>comparingByKey().reversed())
                .map(Map.Entry::getValue)
                .filter(Objects::nonNull)
                .map(IncomeStatementSnapshot::sourceProvenance)
                .filter(Objects::nonNull)
                .findFirst()
                .orElse(null);
    }

    private static SourceProvenance latestBalanceProvenance(Map<String, BalanceSheetSnapshot> snapshots) {
        if (snapshots == null || snapshots.isEmpty()) {
            return null;
        }
        return snapshots.entrySet().stream()
                .sorted(Map.Entry.<String, BalanceSheetSnapshot>comparingByKey().reversed())
                .map(Map.Entry::getValue)
                .filter(Objects::nonNull)
                .map(BalanceSheetSnapshot::sourceProvenance)
                .filter(Objects::nonNull)
                .findFirst()
                .orElse(null);
    }

    public record FinancialIngestionData(
            FinancialDataDTO financialDataDTO,
            List<Double> historicalRevenue,
            List<Double> historicalMargins,
            Double taxProvision,
            Double preTaxIncome,
            SourceProvenance sourceProvenance) {

        public FinancialIngestionData(
                FinancialDataDTO financialDataDTO,
                List<Double> historicalRevenue,
                List<Double> historicalMargins,
                Double taxProvision,
                Double preTaxIncome) {
            this(financialDataDTO, historicalRevenue, historicalMargins, taxProvision, preTaxIncome, null);
        }
    }
}
