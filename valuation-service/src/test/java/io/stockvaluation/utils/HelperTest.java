package io.stockvaluation.utils;

import io.stockvaluation.domain.CostOfCapital;
import io.stockvaluation.domain.IndustryAveragesGlobal;
import io.stockvaluation.domain.IndustryAveragesUS;
import io.stockvaluation.domain.InputStatDistribution;
import io.stockvaluation.dto.BasicInfoDataDTO;
import io.stockvaluation.dto.FinancialDataDTO;
import io.stockvaluation.exception.InsufficientFinancialDataException;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class HelperTest {

    @Test
    void targetOperatingMarginBlendsWithinIndustryBounds() {
        double result = Helper.targetOperatingMargin(10.0, 20.0, 30.0, 40.0, 15.0);

        assertEquals(37.0, result, 1e-9);
    }

    @Test
    void calculateGrowthRateAndAnnualGrowthCapBehaveAsExpected() {
        assertEquals(0.2, Helper.calculateGrowthRate(120.0, 100.0));
        assertEquals(0.7, Helper.adjustAnnualGrowth2_5(0.9));
        assertThrows(InsufficientFinancialDataException.class, () -> Helper.calculateGrowthRate(100.0, 0.0));
    }

    @Test
    void calculateRiskUsesMarketCapDebtAndAgeSignals() {
        int oldCompanyEpoch = (int) ((System.currentTimeMillis() / 1000) - (25L * 365 * 24 * 60 * 60));
        int youngCompanyEpoch = (int) ((System.currentTimeMillis() / 1000) - (5L * 365 * 24 * 60 * 60));

        assertEquals("median", Helper.calculateRisk(600_000_000_000L, 0.3, oldCompanyEpoch, "USD", 30.0));
        assertEquals("firstQuartile", Helper.calculateRisk(10_000_000L, 0.1, oldCompanyEpoch, "SEK", 40.0));
        assertEquals("ninthDecile", Helper.calculateRisk(10_000_000L, 0.8, youngCompanyEpoch, "SEK", 20.0));
    }

    @Test
    void costOfCapitalAdjustsIndustryWaccByRiskBucketAndDebtRatio() {
        CostOfCapital costOfCapital = new CostOfCapital();
        costOfCapital.setFirstDecile("6.0");
        costOfCapital.setFirstQuartile("7.0");
        costOfCapital.setMedian("8.0");
        costOfCapital.setThirdQuartile("9.0");
        costOfCapital.setNinthDecile("10.0");

        BasicInfoDataDTO basicInfo = new BasicInfoDataDTO();
        basicInfo.setMarketCap(1_000_000_000L);
        basicInfo.setDebtToEquity(20.0);
        basicInfo.setFirstTradeDateEpochUtc((int) ((System.currentTimeMillis() / 1000) - (25L * 365 * 24 * 60 * 60)));
        basicInfo.setCurrency("USD");

        FinancialDataDTO financialData = new FinancialDataDTO();
        IndustryAveragesUS industryUs = new IndustryAveragesUS();
        industryUs.setCostOfCapital(9.0);
        industryUs.setMarketDebtToCapital(30.0);

        InputStatDistribution inputStats = new InputStatDistribution();
        assertEquals(7.552621673751778, Helper.costOfCapital(costOfCapital, basicInfo, financialData, industryUs, null,
                Optional.of(inputStats)), 1e-2);

        IndustryAveragesGlobal industryGlobal = new IndustryAveragesGlobal();
        industryGlobal.setCostOfCapital(11.0);
        industryGlobal.setMarketDebtToCapital(0.0);
        assertEquals(9.625, Helper.costOfCapital(costOfCapital, basicInfo, financialData, null, industryGlobal,
                Optional.empty()), 1e-9);
    }

    @Test
    void companyAnchoredTargetMarginKeepsHighMarginFranchiseAboveIndustry() {
        // Winner: company earns a normalized 32% in an industry whose quartiles top out at 22%.
        // Old logic drags the target below the company's own margin; new logic anchors on it.
        double oldTarget = Helper.targetOperatingMargin(13.0, 20.0, 22.0, 32.0, 5.0);
        double newTarget = Helper.companyAnchoredTargetOperatingMargin(13.0, 20.0, 22.0, 32.0, 5.0);

        assertEquals(31.0, newTarget, 1e-9);          // faded modestly, still not capped at the industry
        assertTrue(oldTarget < 32.0);                  // old behavior dragged the franchise below its own margin
        assertTrue(newTarget > oldTarget);             // un-clamping lifts the target back to reality
    }

    @Test
    void companyAnchoredTargetMarginDoesNotLiftLaggardOrCarryPeak() {
        // Average company sitting at the industry median is unchanged.
        assertEquals(20.0, Helper.companyAnchoredTargetOperatingMargin(13.0, 20.0, 22.0, 20.0, 15.0), 1e-9);
        // Genuine laggard (8%) is NOT lifted up to the industry -> no over-valuation of weak firms.
        assertEquals(8.0, Helper.companyAnchoredTargetOperatingMargin(13.0, 20.0, 22.0, 8.0, 15.0), 1e-9);
        // Over-earner guardrail: feed the NORMALIZED multi-year margin (21%), not the latest peak (40%).
        // The target follows the normalized figure, so a temporary spike is never carried to terminal.
        assertEquals(21.0, Helper.companyAnchoredTargetOperatingMargin(13.0, 20.0, 22.0, 21.0, 15.0), 1e-9);
        // Unusable company signal -> industry median fallback (not zero, not a crash).
        assertEquals(20.0, Helper.companyAnchoredTargetOperatingMargin(13.0, 20.0, 22.0, 0.0, 15.0), 1e-9);
        assertEquals(20.0, Helper.companyAnchoredTargetOperatingMargin(13.0, 20.0, 22.0, Double.NaN, 15.0), 1e-9);
    }

    @Test
    void companyAnchoredTargetMarginFadesExceptionalMarginsWithoutIndustryClamp() {
        double target = Helper.companyAnchoredTargetOperatingMargin(18.0, 24.0, 30.0, 46.8, 25.0);

        assertEquals(38.4, target, 1e-9);
        assertTrue(target < 46.8);
        assertTrue(target > 30.0);
    }
}
