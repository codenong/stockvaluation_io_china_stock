package io.stockvaluation.service;

import io.stockvaluation.config.SyntheticRatingProperties;
import io.stockvaluation.config.ValuationAssumptionProperties;
import io.stockvaluation.domain.CountryEquity;
import io.stockvaluation.domain.LargeBondSpread;
import io.stockvaluation.domain.SmallBondSpread;
import io.stockvaluation.dto.CompanyDataDTO;
import io.stockvaluation.dto.CompanyDriveDataDTO;
import io.stockvaluation.dto.FinancialDataDTO;
import io.stockvaluation.dto.LeaseResultDTO;
import io.stockvaluation.dto.SyntheticResultDTO;
import io.stockvaluation.provider.DataProvider;
import io.stockvaluation.repository.CountryEquityRepository;
import io.stockvaluation.repository.LargeSpreadRepository;
import io.stockvaluation.repository.SmallSpreadRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class SyntheticRatingServiceTest {

    @Mock
    private SmallSpreadRepository smallSpreadRepository;

    @Mock
    private LargeSpreadRepository largeSpreadRepository;

    @Mock
    private CountryEquityRepository countryEquityRepository;

    @Mock
    private CommonService commonService;

    @Mock
    private DataProvider dataProvider;

    private SyntheticRatingService service;

    @BeforeEach
    void setUp() {
        ValuationAssumptionProperties valuationAssumptionProperties = new ValuationAssumptionProperties();
        valuationAssumptionProperties.setPreTaxCostOfDebt(0.05);

        SyntheticRatingProperties syntheticRatingProperties = new SyntheticRatingProperties();
        syntheticRatingProperties.setLargeCapThreshold(5_000_000_000L);
        syntheticRatingProperties.setDefaultCountry("United States");
        syntheticRatingProperties.setInterestCoverageCeiling(100000.0);
        syntheticRatingProperties.setInterestCoverageFloor(-100000.0);

        service = new SyntheticRatingService(
                smallSpreadRepository,
                largeSpreadRepository,
                countryEquityRepository,
                commonService,
                dataProvider,
                valuationAssumptionProperties,
                syntheticRatingProperties);
    }

    @Test
    void calculateSyntheticRatingUsesLargeFirmBondSpread() {
        when(dataProvider.getCompanyInfo("AAPL")).thenReturn(Map.of("marketCap", 6_000_000_000L));
        when(commonService.getCompanyDataFromProvider("AAPL")).thenReturn(companyData(200.0, 180.0, 20.0, 4.0));

        LargeBondSpread spread = new LargeBondSpread();
        spread.setRating("A");
        spread.setSpread(1.5);
        when(largeSpreadRepository.findRating(10.0)).thenReturn(spread);

        CountryEquity countryEquity = new CountryEquity();
        countryEquity.setCountryRiskPremium(1.2);
        when(countryEquityRepository.findDefaultSpread("United States")).thenReturn(countryEquity);

        SyntheticResultDTO result = service.calculateSyntheticRating("AAPL", false, null, null, null);

        assertEquals("10.00", result.getInterestCoverageRatio());
        assertEquals("A", result.getEstimatedBondRating());
        assertEquals("1.50", result.getCompanyDefaultSpread());
        assertEquals("1.20", result.getCountryDefaultSpread());
        assertEquals("6.70", result.getCostOfDebt());
    }

    @Test
    void calculateSyntheticRatingUsesLeaseAdjustedMetricsForSmallFirm() {
        when(dataProvider.getCompanyInfo("NFLX")).thenReturn(Map.of("marketCap", 100_000_000L));
        when(commonService.getCompanyDataFromProvider("NFLX")).thenReturn(companyData(80.0, 70.0, 2.0, 3.0));
        when(commonService.calculateOperatingLeaseConverter()).thenReturn(new LeaseResultDTO(0.0, 10.0, 100.0, 0.0));

        SmallBondSpread spread = new SmallBondSpread();
        spread.setRating("BBB");
        spread.setSpread(2.25);
        when(smallSpreadRepository.findRating(80.0 / 7.0)).thenReturn(spread);

        CountryEquity countryEquity = new CountryEquity();
        countryEquity.setCountryRiskPremium(0.75);
        when(countryEquityRepository.findDefaultSpread("United States")).thenReturn(countryEquity);

        SyntheticResultDTO result = service.calculateSyntheticRating("NFLX", true, null, null, null);

        assertEquals("11.43", result.getInterestCoverageRatio());
        assertEquals("BBB", result.getEstimatedBondRating());
        assertEquals("2.25", result.getCompanyDefaultSpread());
        assertEquals("0.75", result.getCountryDefaultSpread());
        assertEquals("6.00", result.getCostOfDebt());
    }

    @Test
    void calculateSyntheticRatingUsesCoverageCeilingWhenInterestExpenseIsZero() {
        when(dataProvider.getCompanyInfo("SHOP")).thenReturn(Map.of());
        when(commonService.getCompanyDataFromProvider("SHOP")).thenReturn(companyData(120.0, 100.0, 0.0, 4.0));
        when(smallSpreadRepository.findRating(100000.0)).thenReturn(null);

        CountryEquity countryEquity = new CountryEquity();
        countryEquity.setCountryRiskPremium(0.5);
        when(countryEquityRepository.findDefaultSpread("United States")).thenReturn(countryEquity);

        SyntheticResultDTO result = service.calculateSyntheticRating("SHOP", false, null, null, null);

        assertEquals("100000.00", result.getInterestCoverageRatio());
        assertNull(result.getEstimatedBondRating());
        assertEquals("0.00", result.getCompanyDefaultSpread());
        assertEquals("0.50", result.getCountryDefaultSpread());
        assertEquals("4.50", result.getCostOfDebt());
    }

    @Test
    void calculateSyntheticRatingUsesCoverageFloorWhenEbitIsNegative() {
        when(dataProvider.getCompanyInfo("SNOW")).thenReturn(Map.of("marketCap", 200_000_000L));
        when(commonService.getCompanyDataFromProvider("SNOW")).thenReturn(companyData(-10.0, -12.0, 5.0, 4.0));

        SmallBondSpread spread = new SmallBondSpread();
        spread.setRating("CCC");
        spread.setSpread(4.5);
        when(smallSpreadRepository.findRating(-100000.0)).thenReturn(spread);

        CountryEquity countryEquity = new CountryEquity();
        countryEquity.setCountryRiskPremium(1.0);
        when(countryEquityRepository.findDefaultSpread("United States")).thenReturn(countryEquity);

        SyntheticResultDTO result = service.calculateSyntheticRating("SNOW", false, null, null, null);

        assertEquals("-100000.00", result.getInterestCoverageRatio());
        assertEquals("CCC", result.getEstimatedBondRating());
        assertEquals("9.50", result.getCostOfDebt());
    }

    private static CompanyDataDTO companyData(double operatingIncomeTtm, double operatingIncomeLtm, double interestExpenseTtm, double riskFreeRate) {
        FinancialDataDTO financialData = new FinancialDataDTO();
        financialData.setOperatingIncomeTTM(operatingIncomeTtm);
        financialData.setOperatingIncomeLTM(operatingIncomeLtm);
        financialData.setInterestExpenseTTM(interestExpenseTtm);

        CompanyDriveDataDTO companyDriveData = new CompanyDriveDataDTO();
        companyDriveData.setRiskFreeRate(riskFreeRate);

        CompanyDataDTO companyData = new CompanyDataDTO();
        companyData.setFinancialDataDTO(financialData);
        companyData.setCompanyDriveDataDTO(companyDriveData);
        return companyData;
    }
}
