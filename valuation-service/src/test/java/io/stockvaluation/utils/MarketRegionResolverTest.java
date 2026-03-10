package io.stockvaluation.utils;

import io.stockvaluation.dto.BasicInfoDataDTO;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class MarketRegionResolverTest {

    @Test
    void resolveRegions_prefersEuropeanTimezone() {
        BasicInfoDataDTO basicInfo = new BasicInfoDataDTO();
        basicInfo.setCountryOfIncorporation("Sweden");
        basicInfo.setTimeZoneFullName("Europe/Stockholm");

        assertEquals("Europe", MarketRegionResolver.resolveGrowthAnchorRegion(basicInfo));
        assertEquals("Europe", MarketRegionResolver.resolveCostOfCapitalRegion(basicInfo));
    }

    @Test
    void resolveRegions_mapsAsianTimezoneToEmerging() {
        BasicInfoDataDTO basicInfo = new BasicInfoDataDTO();
        basicInfo.setTimeZoneFullName("Asia/Kolkata");

        assertEquals("Emerging Markets", MarketRegionResolver.resolveGrowthAnchorRegion(basicInfo));
        assertEquals("Emerging", MarketRegionResolver.resolveCostOfCapitalRegion(basicInfo));
    }
}
