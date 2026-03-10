package io.stockvaluation.utils;

import io.stockvaluation.dto.SegmentWeightedParameters;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SegmentParameterContextTest {

    @AfterEach
    void tearDown() {
        SegmentParameterContext.clear();
    }

    @Test
    void contextReturnsDefensiveCopiesAndSupportsSectorFallbackHelpers() {
        SegmentWeightedParameters parameters = new SegmentWeightedParameters();
        parameters.setSegmentWeighted(true);
        parameters.setWeightedRevenueNextYear(12.0);
        parameters.setWeightedCompoundAnnualGrowth2_5(14.0);
        parameters.setWeightedTargetPreTaxOperatingMargin(22.0);
        parameters.setWeightedSalesToCapitalYears1To5(2.5);
        parameters.setWeightedSalesToCapitalYears6To10(2.0);
        parameters.setWeightedInitialCostCapital(8.0);

        SegmentWeightedParameters.SectorParameters software = new SegmentWeightedParameters.SectorParameters();
        software.setSectorName("software");
        software.setRevenueShare(0.6);
        software.setRevenueNextYear(10.0);
        software.setTargetPreTaxOperatingMargin(25.0);
        software.setSalesToCapitalYears1To5(3.0);
        parameters.setSectorParameters("software", software);

        SegmentParameterContext.setParameters(parameters);

        assertTrue(SegmentParameterContext.hasValidParameters());
        assertTrue(SegmentParameterContext.hasSectorParameters());
        assertEquals(12.0, SegmentParameterContext.getParameterOrDefault(SegmentWeightedParameters::getWeightedRevenueNextYear, 0.0));
        assertEquals(25.0, SegmentParameterContext.getSectorParameterOrDefault("software",
                SegmentWeightedParameters.SectorParameters::getTargetPreTaxOperatingMargin, 0.0));
        assertEquals(Set.of("software"), SegmentParameterContext.getSectorNames());

        SegmentWeightedParameters copy = SegmentParameterContext.getParameters();
        assertNotNull(copy);
        copy.setWeightedRevenueNextYear(99.0);
        assertEquals(12.0, SegmentParameterContext.getParameters().getWeightedRevenueNextYear());

        software.setTargetPreTaxOperatingMargin(99.0);
        assertEquals(25.0, SegmentParameterContext.getSectorParameters("software").getTargetPreTaxOperatingMargin());
    }

    @Test
    void contextFallsBackWhenUnsetOrGetterFails() {
        assertFalse(SegmentParameterContext.hasValidParameters());
        assertEquals("fallback", SegmentParameterContext.getParameterOrDefault(params -> {
            throw new IllegalStateException("boom");
        }, "fallback"));
        assertEquals("fallback", SegmentParameterContext.getSectorParameterOrDefault("missing",
                sector -> sector.getSectorName().toUpperCase(), "fallback"));

        SegmentParameterContext.setParameters(null);
        assertNull(SegmentParameterContext.getParameters());
        assertFalse(SegmentParameterContext.hasSectorParameters());
        assertTrue(SegmentParameterContext.getSectorNames().isEmpty());
    }
}
