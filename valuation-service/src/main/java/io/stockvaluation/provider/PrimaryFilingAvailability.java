package io.stockvaluation.provider;

import java.util.List;

public record PrimaryFilingAvailability(
        boolean available,
        String status,
        String provider,
        List<String> warnings) {

    public static PrimaryFilingAvailability available(String provider) {
        return new PrimaryFilingAvailability(true, "available", provider, List.of());
    }

    public static PrimaryFilingAvailability unavailable(String status, String provider, List<String> warnings) {
        return new PrimaryFilingAvailability(false, status, provider, warnings == null ? List.of() : List.copyOf(warnings));
    }
}
