package io.stockvaluation.service;

import io.stockvaluation.enums.CashflowType;
import io.stockvaluation.enums.EarningsLevel;
import io.stockvaluation.enums.GrowthPattern;
import io.stockvaluation.enums.ModelType;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ValuationModelTest {

    @Test
    void stableGrowthLabelUsesStableTemplateOutputs() {
        ValuationModel model = createModel(true, true, false, false, "Stable Growth", false, 0.05, "");

        assertEquals(ModelType.OPTION_PRICING, model.getModelType());
        assertEquals(EarningsLevel.CURRENT, model.getEarningsLevel());
        assertEquals(CashflowType.FCFF, model.getCashflowToDiscount());
        assertEquals("No high growth period", model.getGrowthPeriodLength());
        assertEquals(GrowthPattern.STABLE, model.getGrowthPattern());
    }

    @Test
    void negativeCyclicalEarningsUseNormalizedStableGrowth() {
        ValuationModel model = createModel(false, false, true, false, "", false, 0.04, "Normalized Earnings");

        assertEquals(ModelType.DISCOUNTED_CF, model.getModelType());
        assertEquals(EarningsLevel.NORMALIZED, model.getEarningsLevel());
        assertEquals("5 years of less", model.getGrowthPeriodLength());
        assertEquals(GrowthPattern.STABLE, model.getGrowthPattern());
    }

    @Test
    void negativeEarningsWithoutNormalizedOverrideUseNStagePattern() {
        ValuationModel model = createModel(false, false, false, false, "", false, 0.12, "Current Earnings");

        assertEquals(EarningsLevel.CURRENT, model.getEarningsLevel());
        assertEquals("5 to 10 years", model.getGrowthPeriodLength());
        assertEquals(GrowthPattern.N_STAGE, model.getGrowthPattern());
    }

    @Test
    void sustainableAdvantageAboveThresholdUsesLongGrowthPeriodAndTwoStagePattern() {
        ValuationModel model = createModel(true, false, false, false, "", true, 0.12, "");

        assertEquals("10 or more years", model.getGrowthPeriodLength());
        assertEquals(GrowthPattern.TWO_STAGE, model.getGrowthPattern());
        assertEquals(ModelType.DISCOUNTED_CF.getDisplayName(), model.getModelTypeString());
        assertEquals(EarningsLevel.CURRENT.getDisplayName(), model.getEarningsLevelString());
        assertEquals(CashflowType.FCFF.getDisplayName(), model.getCashflowToDiscountString());
        assertEquals(GrowthPattern.TWO_STAGE.getDisplayName(), model.getGrowthPatternString());
    }

    @Test
    void nonSustainableGrowthAboveThresholdStillUsesMediumGrowthPeriod() {
        ValuationModel model = createModel(true, false, false, false, "", false, 0.12, "");

        assertEquals("5 to 10 years", model.getGrowthPeriodLength());
        assertEquals(GrowthPattern.TWO_STAGE, model.getGrowthPattern());
    }

    private static ValuationModel createModel(
            boolean earningsPositive,
            boolean useOptionPricing,
            boolean negativeIsCyclical,
            boolean negativeIsOneTime,
            String growthLabel,
            boolean hasSustainableAdvantage,
            double firmGrowthRate,
            String earningsOverride) {
        return new ValuationModel(
                earningsPositive,
                useOptionPricing,
                negativeIsCyclical,
                negativeIsOneTime,
                true,
                false,
                0.0,
                0.0,
                growthLabel,
                hasSustainableAdvantage,
                firmGrowthRate,
                0.03,
                0.02,
                earningsOverride,
                0.0101,
                0.06,
                100.0,
                0.0,
                0.0,
                0.0,
                0.2);
    }
}
