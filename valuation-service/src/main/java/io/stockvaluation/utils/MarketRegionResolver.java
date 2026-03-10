package io.stockvaluation.utils;

import io.stockvaluation.dto.BasicInfoDataDTO;

import java.util.Locale;

public final class MarketRegionResolver {

    private MarketRegionResolver() {
    }

    public static String resolveGrowthAnchorRegion(BasicInfoDataDTO basicInfoDataDTO) {
        return switch (resolveRegionKey(basicInfoDataDTO)) {
            case "europe" -> "Europe";
            case "japan" -> "Japan";
            case "emerging markets" -> "Emerging Markets";
            case "united states" -> "United States";
            default -> "Global";
        };
    }

    public static String resolveCostOfCapitalRegion(BasicInfoDataDTO basicInfoDataDTO) {
        return switch (resolveRegionKey(basicInfoDataDTO)) {
            case "europe" -> "Europe";
            case "japan" -> "Japan";
            case "emerging markets" -> "Emerging";
            case "united states" -> "US";
            default -> "Global";
        };
    }

    static String resolveRegionKey(BasicInfoDataDTO basicInfoDataDTO) {
        if (basicInfoDataDTO == null) {
            return "global";
        }
        return resolveRegionKey(
                basicInfoDataDTO.getCountryOfIncorporation(),
                basicInfoDataDTO.getTimeZoneFullName());
    }

    static String resolveRegionKey(String countryOfIncorporation, String timeZoneFullName) {
        if (timeZoneFullName != null) {
            String normalizedTimeZone = timeZoneFullName.trim().toLowerCase(Locale.ROOT);
            if (normalizedTimeZone.contains("europe")) {
                return "europe";
            }
            if (normalizedTimeZone.contains("tokyo")) {
                return "japan";
            }
            if (normalizedTimeZone.contains("asia")) {
                return "emerging markets";
            }
            if (normalizedTimeZone.contains("america")) {
                return "united states";
            }
            return "global";
        }

        if ("Japan".equalsIgnoreCase(countryOfIncorporation)) {
            return "japan";
        }
        if ("United States".equalsIgnoreCase(countryOfIncorporation)) {
            return "united states";
        }
        return "global";
    }
}
