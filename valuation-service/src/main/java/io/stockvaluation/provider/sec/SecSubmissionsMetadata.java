package io.stockvaluation.provider.sec;

import java.util.List;
import java.util.Map;

record SecSubmissionsMetadata(
        String cik,
        String name,
        String latestPeriodicFilingDate,
        boolean hasUsPeriodicFiling) {

    static SecSubmissionsMetadata from(Map<String, Object> payload) {
        String cik = string(payload.get("cik"));
        String name = string(payload.get("name"));
        Object filingsObject = payload.get("filings");
        if (!(filingsObject instanceof Map<?, ?> filings)) {
            return new SecSubmissionsMetadata(cik, name, null, false);
        }
        Object recentObject = filings.get("recent");
        if (!(recentObject instanceof Map<?, ?> recent)) {
            return new SecSubmissionsMetadata(cik, name, null, false);
        }
        List<?> forms = list(recent.get("form"));
        List<?> filingDates = list(recent.get("filingDate"));
        String latestDate = null;
        boolean hasPeriodic = false;
        for (int i = 0; i < forms.size(); i++) {
            String form = string(forms.get(i));
            if (!isUsPeriodicForm(form)) {
                continue;
            }
            hasPeriodic = true;
            if (i < filingDates.size()) {
                String date = string(filingDates.get(i));
                if (!date.isBlank() && (latestDate == null || date.compareTo(latestDate) > 0)) {
                    latestDate = date;
                }
            }
        }
        return new SecSubmissionsMetadata(cik, name, latestDate, hasPeriodic);
    }

    private static boolean isUsPeriodicForm(String form) {
        return "10-K".equals(form) || "10-Q".equals(form);
    }

    private static List<?> list(Object value) {
        return value instanceof List<?> list ? list : List.of();
    }

    private static String string(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }
}
