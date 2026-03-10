package io.stockvaluation.service;

import io.stockvaluation.dto.GrowthAnchorDTO;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

class GrowthAnchorServiceTest {

    @Test
    void getAnchorByYahooIndustry_resolvesViaIndustryMapping() {
        GrowthAnchorService service = new GrowthAnchorService();
        service.init();

        Optional<GrowthAnchorDTO> anchor = service.getAnchorByYahooIndustry("consumer-electronics", "United States");
        assertTrue(anchor.isPresent(), "Expected mapped growth anchor for consumer-electronics");
    }

    @Test
    void getAnchorByYahooIndustry_prefersLatestYearPerRegion() {
        GrowthAnchorService service = new GrowthAnchorService();
        service.init();

        Optional<GrowthAnchorDTO> anchor = service.getAnchorByYahooIndustry("Software - Infrastructure",
                "United States");
        assertTrue(anchor.isPresent(), "Expected mapped growth anchor for Software - Infrastructure");

        GrowthAnchorDTO dto = anchor.get();
        assertEquals(2026, dto.getYear(), "Anchor should use latest available year for the region");
        assertNotNull(dto.getP25());
        assertNotNull(dto.getP50());
        assertNotEquals(dto.getP25(), dto.getP50(), "Dispersion band should not collapse for latest-year row");
    }

    @Test
    void getAnchorByYahooIndustry_usesMappedRegionWhenCountryIsNotAnchorRegion() {
        GrowthAnchorService service = new GrowthAnchorService();
        service.init();

        Optional<GrowthAnchorDTO> anchor = service.getAnchorByYahooIndustry(
                "Semiconductor Equipment & Materials",
                "Netherlands");
        assertTrue(anchor.isPresent(), "Expected mapped growth anchor for Semiconductor Equipment & Materials");

        GrowthAnchorDTO dto = anchor.get();
        assertEquals("Europe", dto.getRegion());
        assertEquals(2026, dto.getYear());
    }

    @Test
    void getAnchor_prefersGlobalBeforeUnitedStatesFallback() {
        GrowthAnchorService service = new GrowthAnchorService();
        service.init();

        Optional<GrowthAnchorDTO> anchor = service.getAnchor("softwareinternet", "India");
        assertTrue(anchor.isPresent(), "Expected growth anchor when exact region is unavailable");

        GrowthAnchorDTO dto = anchor.get();
        assertEquals("Global", dto.getRegion());
        assertEquals(2026, dto.getYear());
    }

    @Test
    void serviceReportsAvailabilityEntitiesAndRegionFilters() {
        GrowthAnchorService service = new GrowthAnchorService();
        service.init();

        assertTrue(service.isAvailable());
        assertFalse(service.getAvailableEntities().isEmpty());
        assertFalse(service.getAnchorsByRegion("United States").isEmpty());
        assertFalse(service.getAnchorsByRegion(null).isEmpty());
        assertTrue(service.getAnchor(null, "United States").isEmpty());
        assertTrue(service.getAnchor("missing-entity", "United States").isEmpty());
        assertTrue(service.getAnchorByYahooIndustry(" ", "United States").isEmpty());
    }

    @Test
    void privateNormalizationParsingAndRecencyHelpersHandleAliasesAndInvalidValues() {
        GrowthAnchorService service = new GrowthAnchorService();

        assertEquals("united states", ReflectionTestUtils.invokeMethod(service, "normalizeRegionLabel", "USA"));
        assertEquals("emerging markets", ReflectionTestUtils.invokeMethod(service, "normalizeRegionLabel", "emerging"));
        assertEquals("softwareinfrastructure", ReflectionTestUtils.invokeMethod(service, "normalizeKey", "Software - Infrastructure"));
        assertEquals("softwareinternet", ReflectionTestUtils.invokeMethod(service, "normalizeEntity", "Software Internet"));
        assertEquals(12.5, ReflectionTestUtils.invokeMethod(service, "dbl", "12.5"));
        assertNull(ReflectionTestUtils.invokeMethod(service, "dbl", "not-a-number"));
        assertEquals(2026, ((Integer) ReflectionTestUtils.invokeMethod(service, "intVal", "2026")).intValue());
        assertNull(ReflectionTestUtils.invokeMethod(service, "intVal", "NaN"));

        GrowthAnchorDTO older = GrowthAnchorDTO.builder().year(2025).build();
        GrowthAnchorDTO newer = GrowthAnchorDTO.builder().year(2026).build();
        assertTrue((Boolean) ReflectionTestUtils.invokeMethod(service, "isNewer", newer, older));
        assertFalse((Boolean) ReflectionTestUtils.invokeMethod(service, "isNewer", older, newer));
        assertEquals(2026, ((Integer) ReflectionTestUtils.invokeMethod(service, "yearOrZero", newer)).intValue());
        assertEquals(0, ((Integer) ReflectionTestUtils.invokeMethod(service, "yearOrZero", new Object[]{null})).intValue());
    }
}
