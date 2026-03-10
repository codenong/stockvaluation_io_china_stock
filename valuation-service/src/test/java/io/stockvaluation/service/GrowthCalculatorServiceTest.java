package io.stockvaluation.service;

import io.stockvaluation.domain.InputStatDistribution;
import io.stockvaluation.dto.GrowthDto;
import io.stockvaluation.exception.InsufficientFinancialDataException;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

class GrowthCalculatorServiceTest {

    @Test
    void testGenerateRevenueGrowth() {
        Double result = GrowthCalculatorService.generateRevenueGrowth(0.05, 0.02);
        assertNotNull(result);
    }

    @Test
    void testGenerateOperatingMargin_Vol() {
        Double result = GrowthCalculatorService.generateOperatingMargin(0.15, 0.05);
        assertNotNull(result);
        assertTrue(result >= 0);
    }

    @Test
    void testGenerateOperatingMargin_MinModeMax() {
        double result = GrowthCalculatorService.generateOperatingMargin(0.10, 0.15, 0.20);
        assertTrue(result >= 0.10 && result <= 0.20);
    }

    @Test
    void testGenerateCorrelatedVariables() {
        double[] result = GrowthCalculatorService.generateCorrelatedVariables(0.05, 0.02, 0.15, 0.05, 0.5);
        assertEquals(2, result.length);
    }

    @Test
    void testGenerateCorrelatedVariables_InvalidRevenueStdDev() {
        assertThrows(IllegalArgumentException.class, () -> {
            GrowthCalculatorService.generateCorrelatedVariables(0.05, -0.02, 0.15, 0.05, 0.5);
        });
    }

    @Test
    void testGenerateCorrelatedVariables_InvalidRevenueMu() {
        assertThrows(IllegalArgumentException.class, () -> {
            // adjustedMean = -2.0 - (-1.0) = -1.0 <= 0
            GrowthCalculatorService.generateCorrelatedVariables(-2.0, 0.02, 0.15, 0.05, 0.5);
        });
    }

    @Test
    void testGenerateCorrelatedVariables_InvalidMarginStdDev() {
        assertThrows(IllegalArgumentException.class, () -> {
            GrowthCalculatorService.generateCorrelatedVariables(0.05, 0.02, 0.15, 0.0, 0.5);
        });
    }

    @Test
    void testCalculateLogNormalParams() {
        Map<String, Double> result = GrowthCalculatorService.calculateLogNormalParams(0.05, 0.02, -1.0);
        assertNotNull(result.get("muLog"));
        assertNotNull(result.get("sigmaLog"));
        assertEquals(-1.0, result.get("gamma"));
    }

    @Test
    void testCalculateLogNormalParams_InvalidSigma() {
        assertThrows(IllegalArgumentException.class, () -> {
            GrowthCalculatorService.calculateLogNormalParams(0.05, -0.02, -1.0);
        });
    }

    @Test
    void testCalculateLogNormalParams_InvalidMuGamma() {
        assertThrows(IllegalArgumentException.class, () -> {
            GrowthCalculatorService.calculateLogNormalParams(-2.0, 0.02, -1.0);
        });
    }

    @Test
    void testCalculateLogNormalParams_NearZeroVariance() {
        Map<String, Double> result = GrowthCalculatorService.calculateLogNormalParams(0.05, 1e-10, -1.0);
        assertNotNull(result.get("muLog"));
        assertNotNull(result.get("sigmaLog"));
    }

    @Test
    void testPhi() {
        Double result = ReflectionTestUtils.invokeMethod(GrowthCalculatorService.class, "Phi", 0.0);
        assertEquals(0.5, result, 0.01);
    }

    @Test
    void testTriangularFromUniform() {
        Double result1 = ReflectionTestUtils.invokeMethod(GrowthCalculatorService.class, "triangularFromUniform", 0.2,
                0.1, 0.2, 0.3);
        Double result2 = ReflectionTestUtils.invokeMethod(GrowthCalculatorService.class, "triangularFromUniform", 0.8,
                0.1, 0.2, 0.3);
        assertNotNull(result1);
        assertNotNull(result2);
    }

    @Test
    void testClamp() {
        Double result1 = ReflectionTestUtils.invokeMethod(GrowthCalculatorService.class, "clamp", 0.5, 0.1, 0.9);
        assertEquals(0.5, result1);
        Double result2 = ReflectionTestUtils.invokeMethod(GrowthCalculatorService.class, "clamp", 1.5, 0.1, 0.9);
        assertEquals(0.9, result2);
        Double result3 = ReflectionTestUtils.invokeMethod(GrowthCalculatorService.class, "clamp", 0.0, 0.1, 0.9);
        assertEquals(0.1, result3);
    }

    @Test
    void testCalculateSD() {
        List<Double> data = Arrays.asList(2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0);
        double result = GrowthCalculatorService.calculateSD(data);
        assertTrue(result > 0);
    }

    @Test
    void testGenerateGBMPath() {
        double[] path = GrowthCalculatorService.generateGBMPath(100.0, 0.05, 0.2, 5);
        assertEquals(5, path.length);
        assertEquals(100.0, path[0]);
    }

    @Test
    void testCalculateGrowth() {
        List<Double> revenues = Arrays.asList(100.0, 110.0, 121.0);
        List<Double> margins = Arrays.asList(0.10, 0.11, 0.12);

        GrowthDto result = GrowthCalculatorService.calculateGrowth(revenues, margins, 0.05, 0.20);
        assertNotNull(result);
        assertEquals(0.1, result.getRevenueMu(), 0.01);
    }

    @Test
    void testCalculateGrowth_NullInputs() {
        assertThrows(InsufficientFinancialDataException.class, () -> {
            GrowthCalculatorService.calculateGrowth(null, null, 0.05, 0.20);
        });
    }

    @Test
    void testCalculateGrowth_InsufficientData() {
        List<Double> revenues = Arrays.asList(100.0, 110.0);
        List<Double> margins = Arrays.asList(0.10, 0.11);
        assertThrows(InsufficientFinancialDataException.class, () -> {
            GrowthCalculatorService.calculateGrowth(revenues, margins, 0.05, 0.20);
        });
    }

    @Test
    void testCalculateGrowth_ZeroRevenue() {
        List<Double> revenues = Arrays.asList(100.0, 0.0, 110.0);
        List<Double> margins = Arrays.asList(0.10, 0.11, 0.12);
        assertThrows(InsufficientFinancialDataException.class, () -> {
            GrowthCalculatorService.calculateGrowth(revenues, margins, 0.05, 0.20);
        });
    }

    @Test
    void testAdjustAnnualGrowth2_5years_NoDistribution() {
        double result = GrowthCalculatorService.adjustAnnualGrowth2_5years(0.10, 0.08, Optional.empty());
        assertEquals(0.10 * 0.7 + 0.08 * 0.3, result, 0.001);
    }

    @Test
    void testAdjustAnnualGrowth2_5years_NullDistributionData() {
        InputStatDistribution dist = new InputStatDistribution();
        double result = GrowthCalculatorService.adjustAnnualGrowth2_5years(0.10, 0.08, Optional.of(dist));
        assertEquals(0.074, result, 0.001); // 0.10 * 0.5 + 0.0 * 0.2 + 0.08 * 0.3 = 0.074
    }

    @Test
    void testAdjustAnnualGrowth2_5years_WithDistribution_StrongCap() {
        InputStatDistribution dist = new InputStatDistribution();
        dist.setRevenueGrowthRateFirstQuartile(2.0);
        dist.setRevenueGrowthRateMedian(5.0);
        dist.setRevenueGrowthRateThirdQuartile(8.0);

        // revenueGrowthNext (0.20) > q3 (0.08) and >= 2.0 * industryAvg (0.05)
        double result = GrowthCalculatorService.adjustAnnualGrowth2_5years(0.20, 0.05, Optional.of(dist));
        double expected = (0.20 * 0.5) + (0.08 * 0.3) + (0.05 * 0.2);
        assertEquals(expected, result, 0.001);
    }

    @Test
    void testAdjustAnnualGrowth2_5years_WithDistribution_GentleCap() {
        InputStatDistribution dist = new InputStatDistribution();
        dist.setRevenueGrowthRateFirstQuartile(2.0);
        dist.setRevenueGrowthRateMedian(5.0);
        dist.setRevenueGrowthRateThirdQuartile(8.0);

        // revenueGrowthNext (0.10) > q3 (0.08) and >= 1.5 * industryAvg (0.06)
        double result = GrowthCalculatorService.adjustAnnualGrowth2_5years(0.10, 0.06, Optional.of(dist));
        double expected = (0.10 * 0.75) + (0.08 * 0.15) + (0.06 * 0.10);
        assertEquals(expected, result, 0.001);
    }

    @Test
    void testAdjustAnnualGrowth2_5years_WithDistribution_SlightlyAboveQ3() {
        InputStatDistribution dist = new InputStatDistribution();
        dist.setRevenueGrowthRateFirstQuartile(2.0);
        dist.setRevenueGrowthRateMedian(5.0);
        dist.setRevenueGrowthRateThirdQuartile(8.0);

        // revenueGrowthNext (0.09) > q3 (0.08) but < 1.5 * industryAvg (0.08)
        double result = GrowthCalculatorService.adjustAnnualGrowth2_5years(0.09, 0.08, Optional.of(dist));
        double expected = (0.09 * 0.5) + (0.05 * 0.2) + (0.08 * 0.3);
        assertEquals(expected, result, 0.001);
    }

    @Test
    void testAdjustAnnualGrowth2_5years_WithDistribution_BelowQ1() {
        InputStatDistribution dist = new InputStatDistribution();
        dist.setRevenueGrowthRateFirstQuartile(5.0);
        dist.setRevenueGrowthRateMedian(8.0);
        dist.setRevenueGrowthRateThirdQuartile(12.0);

        // revenueGrowthNext (0.02) < q1 (0.05)
        double result = GrowthCalculatorService.adjustAnnualGrowth2_5years(0.02, 0.08, Optional.of(dist));
        double expected = (0.02 * 0.2) + (0.05 * 0.5) + (0.08 * 0.3);
        assertEquals(expected, result, 0.001);
    }

    @Test
    void testAdjustAnnualGrowth2_5years_WithDistribution_Moderate() {
        InputStatDistribution dist = new InputStatDistribution();
        dist.setRevenueGrowthRateFirstQuartile(2.0);
        dist.setRevenueGrowthRateMedian(5.0);
        dist.setRevenueGrowthRateThirdQuartile(10.0);

        // revenueGrowthNext (0.08) is between q1 and q3
        double result = GrowthCalculatorService.adjustAnnualGrowth2_5years(0.08, 0.08, Optional.of(dist));
        double expected = (0.08 * 0.5) + (0.05 * 0.2) + (0.08 * 0.3);
        assertEquals(expected, result, 0.001);
    }

    @Test
    void testApplyGrowthBounds() {
        Double result1 = ReflectionTestUtils.invokeMethod(GrowthCalculatorService.class, "applyGrowthBounds", -150.0);
        assertEquals(-100.0, result1);

        Double result2 = ReflectionTestUtils.invokeMethod(GrowthCalculatorService.class, "applyGrowthBounds", 400.0);
        assertEquals(300.0, result2);

        Double result3 = ReflectionTestUtils.invokeMethod(GrowthCalculatorService.class, "applyGrowthBounds", 50.0);
        assertEquals(50.0, result3);
    }
}
