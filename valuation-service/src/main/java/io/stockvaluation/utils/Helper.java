package io.stockvaluation.utils;

import io.stockvaluation.domain.CostOfCapital;
import io.stockvaluation.domain.IndustryAveragesGlobal;
import io.stockvaluation.domain.IndustryAveragesUS;
import io.stockvaluation.domain.InputStatDistribution;
import io.stockvaluation.dto.BasicInfoDataDTO;
import io.stockvaluation.dto.FinancialDataDTO;
import io.stockvaluation.exception.InsufficientFinancialDataException;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Arrays;
import java.util.Optional;

public class Helper {

    /**
     * Company-anchored target operating margin for the consolidated single-industry path.
     *
     * <p>The company's own normalized margin is the anchor. The industry distribution is a
     * guardrail, not a verdict: it supplies a fallback only when the company signal is unusable.
     * It never clamps a genuinely high-margin company down to the industry (the old behavior,
     * which systematically under-valued franchises) and never lifts a genuinely low-margin
     * company up to the industry (which would over-value laggards).
     *
     * <p>Over-earning is handled by anchoring on a <em>normalized</em> (multi-period) company
     * margin rather than the latest peak, so a cyclical/temporary spike is not carried to the
     * terminal year. Any long-run competitive fade is a narrative judgment set in the guided
     * framing layer, not a mechanical haircut imposed here against often-unreliable industry
     * quartiles.
     *
     * @param industryFirstQuartile   industry pre-tax operating margin Q1 (percent); reserved guardrail input
     * @param industryMedian          industry pre-tax operating margin median (percent); fallback for unusable data
     * @param industryThirdQuartile   industry pre-tax operating margin Q3 (percent); reserved guardrail input
     * @param companyNormalizedMargin company normalized pre-tax operating margin (percent)
     * @param avgIndustryMargin       industry average pre-tax operating margin (percent); reserved guardrail input
     * @return the target operating margin (percent)
     */
    public static double companyAnchoredTargetOperatingMargin(double industryFirstQuartile,
            double industryMedian,
            double industryThirdQuartile,
            double companyNormalizedMargin,
            double avgIndustryMargin) {

        // Fall back to the industry median only when the company signal is unusable.
        if (!Double.isFinite(companyNormalizedMargin) || companyNormalizedMargin <= 0.0) {
            return industryMedian;
        }

        // Anchor on the company's own normalized margin. No mechanical lift or clamp toward the
        // industry: a franchise keeps its margin, a laggard keeps its margin, and the competitive
        // fade (if any) is decided in the narrative/framing layer.
        return companyNormalizedMargin;
    }

    public static double targetOperatingMargin(double preTaxOperatingMarginFirstQuartile,
            double preTaxOperatingMarginMedian,
            double preTaxOperatingMarginThirdQuartile,
            double operatingMarginNextYear,
            double avgPreTaxOperatingMargin) {

        // Step 1: Calculate IQR and skew
        double iqr = preTaxOperatingMarginThirdQuartile - preTaxOperatingMarginFirstQuartile;
        double qSkew = 0.0;

        if (iqr != 0) {
            qSkew = (preTaxOperatingMarginFirstQuartile
                    - 2 * preTaxOperatingMarginMedian
                    + preTaxOperatingMarginThirdQuartile) / iqr;
        }

        // Step 2: Adjust the median based on skew
        double adjustedMedian = preTaxOperatingMarginMedian + (qSkew * iqr * 0.3);
        double constrainedAdjustedMedian = Math.max(preTaxOperatingMarginFirstQuartile,
                Math.min(adjustedMedian, preTaxOperatingMarginThirdQuartile));

        // Step 3: Determine weights
        double weightNextYear;
        double weightAvg;
        double weightAdjustedMedian;

        // If next year's margin is at least 1.5x the industry average, favor it heavily
        if (operatingMarginNextYear >= 1.5 * avgPreTaxOperatingMargin) {
            weightNextYear = 0.75;
            weightAvg = 0.15;
            weightAdjustedMedian = 0.10;
        } else {
            weightNextYear = 0.5;
            weightAvg = 0.25;
            weightAdjustedMedian = 0.25;
        }

        // Step 4: Blend the values
        double blended = (weightNextYear * operatingMarginNextYear)
                + (weightAvg * avgPreTaxOperatingMargin)
                + (weightAdjustedMedian * constrainedAdjustedMedian);

        // Step 5: Constrain final output within quartiles
        double constrainedBlended = Math.max(preTaxOperatingMarginFirstQuartile,
                Math.min(blended, preTaxOperatingMarginThirdQuartile));

        // Step 6: Ensure non-negative if forecast is positive
        if (operatingMarginNextYear > 0) {
            constrainedBlended = Math.max(constrainedBlended, 0.0);
        }

        // Optional: Apply smoothing to prevent sharp drops (uncomment if needed)
        double smoothed = 0.7 * operatingMarginNextYear + 0.3 * constrainedBlended;

        double[] margins = {
                preTaxOperatingMarginFirstQuartile,
                preTaxOperatingMarginMedian,
                preTaxOperatingMarginThirdQuartile,
                operatingMarginNextYear,
                avgPreTaxOperatingMargin
        };

        // Use streams to filter positive values and find the minimum
        double lowestPositive = Arrays.stream(margins)
                .filter(value -> value > 0)
                .min()
                .orElse(Double.NaN);

        double highestPositive = Arrays.stream(margins)
                .filter(value -> value > 0)
                .max()
                .orElse(Double.NaN);

        return Math.max(smoothed, (lowestPositive + highestPositive) / 2);

        // return constrainedBlended;
    }

    public static double calculateGrowthRate(double totalRevenueTTM, double revenueLTM) {
        if (revenueLTM == 0) {
            throw new InsufficientFinancialDataException("revenueLTM cannot be zero.");
        }
        return new BigDecimal(((totalRevenueTTM - revenueLTM) / revenueLTM))
                .setScale(2, RoundingMode.HALF_UP)
                .doubleValue();
    }

    public static double adjustAnnualGrowth2_5(double revenueGrowthNext) {
        return Math.min(revenueGrowthNext, 0.7);
    }

    public static String calculateRisk(long marketCap, double debtToEquity, int firstTradeDateEpochUtc, String currency,
            double marketDebtToCapital) {
        // Priority: marketCap > debtToEquity > firstTradeDateEpochUtc

        // Define thresholds
        long currentEpoch = System.currentTimeMillis() / 1000; // Current time in seconds since epoch
        long thresholdOldCompany = 20L * 365 * 24 * 60 * 60; // 20 years in seconds

        // Market Cap Priority
        if (marketCap >= 500_000_000_000.0 && currency.equalsIgnoreCase("USD")) {
            return "median";
        }

        // Debt-to-Equity Ratio Evaluation
        boolean isHighDebtToEquity = false;

        if (marketDebtToCapital != 0)
            isHighDebtToEquity = (debtToEquity
                    / (((marketDebtToCapital / 100) / (1 - (marketDebtToCapital / 100))))) > 1.5;

        // First Trade Date Evaluation (older companies are lower risk)
        boolean isOldCompany = (currentEpoch - firstTradeDateEpochUtc) > thresholdOldCompany;

        // Determine Risk Category Based on Combined Factors
        if (!isHighDebtToEquity && isOldCompany) {
            return "firstQuartile";
        } else if (isHighDebtToEquity && isOldCompany) {
            return "median";
        } else if (isHighDebtToEquity && !isOldCompany) {
            return "ninthDecile";
        } else {
            return "thirdQuartile";
        }
    }

    public static Double costOfCapital(CostOfCapital costOfCapital,
            BasicInfoDataDTO basicInfoDataDTO,
            FinancialDataDTO financialDataDTO,
            IndustryAveragesUS industryAveragesUS,
            IndustryAveragesGlobal industryAveragesGlobal,
            Optional<InputStatDistribution> optionalInputStatDistribution) {
        double industryCostOfCapital = 0.0;
        double marketDebtToCapital = 0.0;

        // Retrieve industry-specific data (prioritize US, fallback to Global)
        if (industryAveragesUS != null) {
            industryCostOfCapital = industryAveragesUS.getCostOfCapital();
            marketDebtToCapital = industryAveragesUS.getMarketDebtToCapital();
        } else if (industryAveragesGlobal != null) {
            industryCostOfCapital = industryAveragesGlobal.getCostOfCapital();
            marketDebtToCapital = industryAveragesGlobal.getMarketDebtToCapital();
        }
        // Determine the company's risk category
        double debtToEquity = basicInfoDataDTO.getDebtToEquity() != null ? basicInfoDataDTO.getDebtToEquity() / 100
                : 0.0;
        String risk = calculateRisk(
                basicInfoDataDTO.getMarketCap(),
                debtToEquity,
                basicInfoDataDTO.getFirstTradeDateEpochUtc(),
                basicInfoDataDTO.getCurrency(),
                marketDebtToCapital);

        // Get the corresponding decile value from Damodaran's data
        String decileValueStr = getDecileValue(costOfCapital, risk);
        double decileValue = parseDoubleSafe(decileValueStr);

        // If no industry data is available, return the raw Damodaran decile value
        if (industryCostOfCapital == 0) {
            return decileValue;
        }

        // Calculate company's debt-to-capital ratio
        double companyDebtToCapital = (debtToEquity / (1 + debtToEquity)) * 100;

        // Adjust the industry's cost of capital based on the company's debt ratio
        double adjustedIndustryWACC = calculateIndustryScalingFactor(
                companyDebtToCapital,
                marketDebtToCapital,
                industryCostOfCapital);

        double median = parseDoubleSafe(costOfCapital.getMedian());
        double ratio = median != 0 ? decileValue / median : 1.0;

        return Math.min((adjustedIndustryWACC * ratio), parseDoubleSafe(costOfCapital.getNinthDecile()));
    }

    private static double calculateIndustryScalingFactor(double companyDebtRatio,
            double industryDebtRatio,
            double industryWACC) {
        if (industryDebtRatio == 0 || industryWACC == 0) {
            return industryWACC;
        }

        // Compute the logarithmic impact of the company's debt ratio relative to the
        // industry
        double debtRatioImpact = Math.log1p(companyDebtRatio) / Math.log1p(industryDebtRatio);
        // Apply a dampening factor to moderate the adjustment
        return industryWACC * (1 + (debtRatioImpact - 1) * 0.25);
    }

    private static double parseDoubleSafe(String value) {
        try {
            return Double.parseDouble(value);
        } catch (NumberFormatException | NullPointerException e) {
            return 0.0; // Handle invalid values appropriately
        }
    }

    private static String getDecileValue(CostOfCapital costOfCapital, String risk) {
        return switch (risk.toLowerCase()) {
            case "firstdecile" -> costOfCapital.getFirstDecile();
            case "firstquartile" -> costOfCapital.getFirstQuartile();
            case "thirdquartile" -> costOfCapital.getThirdQuartile();
            case "ninthdecile" -> costOfCapital.getNinthDecile();
            default -> costOfCapital.getMedian();
        };
    }

}
