package io.stockvaluation.dto;

import io.stockvaluation.dto.valuationoutput.CompanyDTO;
import org.junit.jupiter.api.Test;

import java.util.Collections;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Coverage test for simple getter/setter, equals/hashCode/toString branches
 * in DTOs. Lombok generated code often accounts for high branch counts
 * (due to if (this == o), if (canEqual), etc).
 */
class DtoCoverageTest {

    @Test
    void segmentWeightedParametersCoverage() {
        SegmentWeightedParameters p1 = new SegmentWeightedParameters();
        p1.setSegmentWeighted(true);
        p1.setWeightedRevenueNextYear(10.0);

        assertTrue(p1.equals(p1));
        assertFalse(p1.equals(null));
        assertFalse(p1.equals(new Object()));
        assertNotNull(p1.toString());
        p1.hashCode();

        SegmentWeightedParameters.SectorParameters s1 = new SegmentWeightedParameters.SectorParameters();
        s1.setSectorName("tech");
        s1.setRevenueShare(0.5);
        assertTrue(s1.equals(s1));
        assertFalse(s1.equals(null));
        assertNotNull(s1.toString());
        s1.hashCode();
    }

    @Test
    void infoDTOCoverage() {
        InfoDTO i1 = new InfoDTO();
        i1.setCompanyName("Acme");
        i1.setTicker("ACM");
        i1.setWebsite("acme.com");
        i1.setIndustryGlobal("Tech");
        i1.setIndustryUs("Tech US");
        i1.setCountryOfIncorporation("US");
        i1.setNoOfShareOutstanding(100.0);
        i1.setStockPrice(50.0);
        i1.setLowestStockPrice(10.0);
        i1.setHighestStockPrice(100.0);
        i1.setPriceChangeFromLastStock(5.0);
        i1.setPercentageChangeFromLastStock(10.0);
        i1.setPriceChangeCurrentStock(1.0);
        i1.setPercentageChangeCurrentStock(2.0);
        i1.setDateOfValuation(java.time.LocalDate.now());

        assertEquals("Acme", i1.getCompanyName());
        assertEquals("ACM", i1.getTicker());
        assertEquals("acme.com", i1.getWebsite());
        assertEquals("Tech", i1.getIndustryGlobal());
        assertEquals("Tech US", i1.getIndustryUs());
        assertEquals("US", i1.getCountryOfIncorporation());
        assertEquals(100.0, i1.getNoOfShareOutstanding());
        assertEquals(50.0, i1.getStockPrice());
        assertEquals(10.0, i1.getLowestStockPrice());
        assertEquals(100.0, i1.getHighestStockPrice());
        assertEquals(5.0, i1.getPriceChangeFromLastStock());
        assertEquals(10.0, i1.getPercentageChangeFromLastStock());
        assertEquals(1.0, i1.getPriceChangeCurrentStock());
        assertEquals(2.0, i1.getPercentageChangeCurrentStock());
        assertNotNull(i1.getDateOfValuation());
    }

    @Test
    void dividendDataDTOCoverage() {
        DividendDataDTO d1 = new DividendDataDTO();
        d1.setDividendYield(0.05);

        assertTrue(d1.equals(d1));
        assertFalse(d1.equals(null));
        assertNotNull(d1.toString());
        d1.hashCode();
    }

    @Test
    void valuationTemplateCoverage() {
        ValuationTemplate t1 = new ValuationTemplate();
        t1.setArrayLength(5);

        assertTrue(t1.equals(t1));
        assertFalse(t1.equals(null));
        assertNotNull(t1.toString());
        t1.hashCode();
    }

    @Test
    void companyDataDTOCoverage() {
        CompanyDataDTO c1 = new CompanyDataDTO();
        BasicInfoDataDTO b = new BasicInfoDataDTO();
        c1.setBasicInfoDataDTO(b);

        assertTrue(c1.equals(c1));
        assertFalse(c1.equals(null));
        assertNotNull(c1.toString());
        c1.hashCode();
    }

    @Test
    void valuationOutputDTOCoverage() {
        ValuationOutputDTO v1 = new ValuationOutputDTO();
        CompanyDTO c = new CompanyDTO();
        v1.setCompanyDTO(c);

        assertTrue(v1.equals(v1));
        assertFalse(v1.equals(null));
        assertNotNull(v1.toString());
        v1.hashCode();
    }
}
