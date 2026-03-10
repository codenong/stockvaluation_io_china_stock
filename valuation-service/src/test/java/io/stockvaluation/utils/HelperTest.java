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
}
