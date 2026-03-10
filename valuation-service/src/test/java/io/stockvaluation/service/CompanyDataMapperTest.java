package io.stockvaluation.service;

import io.stockvaluation.dto.BasicInfoDataDTO;
import io.stockvaluation.exception.BadRequestException;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;

class CompanyDataMapperTest {

    private final CompanyDataMapper mapper = new CompanyDataMapper();

    @Test
    void mapBasicInfoMapsKnownFieldsAndConvertsEpochMilliseconds() {
        Map<String, Object> basicInfo = new HashMap<>();
        basicInfo.put("trailingPegRatio", 2.0);
        basicInfo.put("financialCurrency", "USD");
        basicInfo.put("currency", "SEK");
        basicInfo.put("longName", "Example Corp");
        basicInfo.put("country", "Sweden");
        basicInfo.put("industryKey", "software-infrastructure");
        basicInfo.put("longBusinessSummary", "Summary");
        basicInfo.put("website", "https://example.com");
        basicInfo.put("compensationRisk", 3);
        basicInfo.put("marketCap", 123456789L);
        basicInfo.put("heldPercentInstitutions", 0.81);
        basicInfo.put("firstTradeDateMilliseconds", 1_700_000_000_000L);
        basicInfo.put("timeZoneFullName", "Europe/Stockholm");
        basicInfo.put("beta", 1.2d);
        basicInfo.put("debtToEquity", 45.0d);

        BasicInfoDataDTO result = mapper.mapBasicInfo("EXMP", basicInfo);

        assertEquals("EXMP", result.getTicker());
        assertEquals("USD", result.getCurrency());
        assertEquals("SEK", result.getStockCurrency());
        assertEquals("Example Corp", result.getCompanyName());
        assertEquals("Sweden", result.getCountryOfIncorporation());
        assertEquals("software-infrastructure", result.getIndustryUs());
        assertEquals("software-infrastructure", result.getIndustryGlobal());
        assertEquals("Summary", result.getSummary());
        assertEquals("https://example.com", result.getWebsite());
        assertEquals(3, result.getCompensationRisk());
        assertEquals(123456789L, result.getMarketCap());
        assertEquals(0.81, result.getHeldPercentInstitutions());
        assertEquals(1_700_000_000, result.getFirstTradeDateEpochUtc());
        assertEquals("Europe/Stockholm", result.getTimeZoneFullName());
        assertEquals(1.2d, result.getBeta());
        assertEquals(45.0d, result.getDebtToEquity());
        assertEquals(LocalDate.now(), result.getDateOfValuation());
        assertFalse(basicInfo.containsKey("trailingPegRatio"));
    }

    @Test
    void mapBasicInfoDefaultsEpochToZeroWhenMillisecondsAreNotALong() {
        Map<String, Object> basicInfo = new HashMap<>();
        basicInfo.put("sectorKey", "technology");
        basicInfo.put("firstTradeDateMilliseconds", "not-a-long");

        BasicInfoDataDTO result = mapper.mapBasicInfo("EXMP", basicInfo);

        assertEquals(0, result.getFirstTradeDateEpochUtc());
    }

    @Test
    void mapBasicInfoRejectsMissingPayloadAndFinancialCompanies() {
        assertThrows(BadRequestException.class, () -> mapper.mapBasicInfo("EXMP", null));
        assertThrows(BadRequestException.class, () -> mapper.mapBasicInfo("EXMP", Map.of()));

        Map<String, Object> financePayload = new HashMap<>();
        financePayload.put("sectorKey", "financial-services");

        assertThrows(BadRequestException.class, () -> mapper.mapBasicInfo("EXMP", financePayload));
    }
}
