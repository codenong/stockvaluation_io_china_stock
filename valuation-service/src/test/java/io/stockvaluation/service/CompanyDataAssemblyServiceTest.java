package io.stockvaluation.service;

import io.stockvaluation.config.ValuationAssumptionProperties;
import io.stockvaluation.domain.CostOfCapital;
import io.stockvaluation.domain.IndustryAveragesGlobal;
import io.stockvaluation.domain.IndustryAveragesUS;
import io.stockvaluation.domain.InputStatDistribution;
import io.stockvaluation.domain.SectorMapping;
import io.stockvaluation.dto.BasicInfoDataDTO;
import io.stockvaluation.dto.CompanyDataDTO;
import io.stockvaluation.dto.FinancialDataDTO;
import io.stockvaluation.provider.DataProvider;
import io.stockvaluation.provider.PrimaryFilingAvailability;
import io.stockvaluation.provider.PrimaryFilingDataProvider;
import io.stockvaluation.provider.SourceProvenance;
import io.stockvaluation.repository.CostOfCapitalRepository;
import io.stockvaluation.repository.CountryEquityRepository;
import io.stockvaluation.repository.IndustryAveragesGlobalRepository;
import io.stockvaluation.repository.IndustryAveragesUSRepository;
import io.stockvaluation.repository.InputStatRepository;
import io.stockvaluation.repository.RiskFreeRateRepository;
import io.stockvaluation.repository.SectorMappingRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyDouble;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.lenient;

@ExtendWith(MockitoExtension.class)
class CompanyDataAssemblyServiceTest {

    @Mock
    private CountryEquityRepository countryEquityRepository;
    @Mock
    private SectorMappingRepository sectorMappingRepository;
    @Mock
    private DataProvider dataProvider;
    @Mock
    private RiskFreeRateRepository riskFreeRateRepository;
    @Mock
    private IndustryAveragesUSRepository industryAvgUSRepository;
    @Mock
    private IndustryAveragesGlobalRepository industryAvgGloRepository;
    @Mock
    private InputStatRepository inputStatRepository;
    @Mock
    private CostOfCapitalRepository costOfCapitalRepository;
    @Mock
    private CurrencyRateService currencyRateService;
    @Mock
    private CompanyDataMapper companyDataMapper;
    @Mock
    private CompanyFinancialIngestionService companyFinancialIngestionService;
    @Mock
    private ValuationAssumptionProperties valuationAssumptionProperties;
    @Mock
    private PrimaryFilingDataProvider primaryFilingDataProvider;

    @InjectMocks
    private CompanyDataAssemblyService companyDataAssemblyService;

    @BeforeEach
    void setUp() {
        lenient().when(valuationAssumptionProperties.getBaselineRiskFreeCurrencyCode()).thenReturn("USD");
        lenient().when(valuationAssumptionProperties.getBaselineRiskFreeRate()).thenReturn(4.0);
        lenient().when(valuationAssumptionProperties.getConvergenceYearMargin()).thenReturn(5.0);

        lenient().when(riskFreeRateRepository.findRiskFreeRateByCurrency("USD")).thenReturn(Optional.of(4.2));
    }

    @Test
    void testResolveBaselineRiskFreeRate() {
        Double result = ReflectionTestUtils.invokeMethod(companyDataAssemblyService, "resolveBaselineRiskFreeRate");
        assertEquals(4.2, result);
    }

    @Test
    void testResolveBaselineRiskFreeRate_EmptyCurrencyCode() {
        when(valuationAssumptionProperties.getBaselineRiskFreeCurrencyCode()).thenReturn("");
        Double result = ReflectionTestUtils.invokeMethod(companyDataAssemblyService, "resolveBaselineRiskFreeRate");
        assertEquals(4.0, result); // Returns default 4.0 if empty
    }

    @Test
    void testResolveRiskFreeRateForCurrency() {
        lenient().when(riskFreeRateRepository.findRiskFreeRateByCurrency("EUR")).thenReturn(Optional.of(3.5));
        Double result = ReflectionTestUtils.invokeMethod(companyDataAssemblyService, "resolveRiskFreeRateForCurrency",
                "EUR");
        assertEquals(3.5, result);
    }

    @Test
    void testResolveRiskFreeRateForCurrency_NullCurrency() {
        Double result = ReflectionTestUtils.invokeMethod(companyDataAssemblyService, "resolveRiskFreeRateForCurrency",
                (String) null);
        assertEquals(4.2, result);
    }

    @Test
    void testConvertPercentage() {
        Double result = ReflectionTestUtils.invokeMethod(companyDataAssemblyService, "convertPercentage", 250.0);
        assertEquals(2.5, result);

        Double nullResult = ReflectionTestUtils.invokeMethod(companyDataAssemblyService, "convertPercentage",
                (Double) null);
        assertEquals(0.0, nullResult);
    }

    @Test
    void testReAdjustSalesToCapitalFirstPhases() {
        Double result1 = ReflectionTestUtils.invokeMethod(companyDataAssemblyService,
                "reAdjustSalesToCapitalFirstPhases", 4.0, 1.5);
        assertEquals(2.0, result1); // Math.max(4.0/2, 1.5) = 2.0

        Double result2 = ReflectionTestUtils.invokeMethod(companyDataAssemblyService,
                "reAdjustSalesToCapitalFirstPhases", null, 1.5);
        assertEquals(1.5, result2);
    }

    @Test
    void testAssembleCompanyData_US_Company() throws Exception {
        String ticker = "AAPL";

        Map<String, Object> basicInfoMap = new HashMap<>();
        basicInfoMap.put("currency", "USD");
        basicInfoMap.put("financialCurrency", "USD");
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);

        BasicInfoDataDTO basicInfoDataDTO = new BasicInfoDataDTO();
        basicInfoDataDTO.setCountryOfIncorporation("United States");
        basicInfoDataDTO.setCurrency("USD");
        basicInfoDataDTO.setIndustryGlobal("Technology");
        basicInfoDataDTO.setTimeZoneFullName("America/New_York");
        basicInfoDataDTO.setMarketCap(1000000000L);
        basicInfoDataDTO.setFirstTradeDateEpochUtc(1600000000); // added to prevent NPE
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(basicInfoDataDTO);

        FinancialDataDTO financialDataDTO = new FinancialDataDTO();
        financialDataDTO.setStockPrice(150.0);
        financialDataDTO.setRevenueTTM(380000.0);
        financialDataDTO.setRevenueLTM(360000.0);
        financialDataDTO.setOperatingIncomeTTM(110000.0);
        financialDataDTO.setOperatingIncomeLTM(100000.0);

        List<Double> historicalRevenue = List.of(380000.0, 360000.0, 340000.0);
        List<Double> historicalMargins = List.of(0.28, 0.27, 0.26);

        CompanyFinancialIngestionService.FinancialIngestionData ingestionData = new CompanyFinancialIngestionService.FinancialIngestionData(
                financialDataDTO,
                historicalRevenue,
                historicalMargins,
                15000.0,
                100000.0,
                SourceProvenance.yahooNormalized("yfinance-http", "2025-06-30"));
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap)).thenReturn(ingestionData);

        when(countryEquityRepository.findCorporateTaxRateByCountry("United States")).thenReturn(Optional.of(21.0));

        Map<String, Object> revenueEstimateMapData = new HashMap<>();
        Map<String, Object> growthMap = new HashMap<>();
        growthMap.put("+1y", 0.05); // 5% growth
        revenueEstimateMapData.put("growth", growthMap);
        when(dataProvider.getRevenueEstimate(ticker, "yearly")).thenReturn(revenueEstimateMapData);

        SectorMapping sectorMapping = new SectorMapping();
        sectorMapping.setIndustryAsPerExcel("Technology");
        when(sectorMappingRepository.findByIndustryName("Technology")).thenReturn(sectorMapping);

        when(industryAvgUSRepository.findSalesToCapitalByIndustryName("Technology")).thenReturn(Optional.of(1.5));

        IndustryAveragesUS avgUS = new IndustryAveragesUS();
        avgUS.setPreTaxOperatingMargin(25.0);
        avgUS.setAnnualAverageRevenueGrowth(8.0);
        when(industryAvgUSRepository.findByIndustryName("Technology")).thenReturn(avgUS);

        InputStatDistribution inputStat = new InputStatDistribution();
        inputStat.setPreTaxOperatingMarginFirstQuartile(10.0);
        inputStat.setPreTaxOperatingMarginMedian(20.0);
        inputStat.setPreTaxOperatingMarginThirdQuartile(30.0);
        inputStat.setSalesToInvestedCapitalThirdQuartile(2.0);
        when(inputStatRepository.findFirstByIndustryGroupOrderByIdAsc("Technology"))
                .thenReturn(Optional.of(inputStat));

        CostOfCapital costOfCapital = new CostOfCapital();
        costOfCapital.setMedian("0.08");
        costOfCapital.setThirdQuartile("0.10");
        when(costOfCapitalRepository.findCostOfCapitalByRegion("US")).thenReturn(Optional.of(costOfCapital));

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker);

        assertNotNull(result);
        assertNotNull(result.getBasicInfoDataDTO());
        assertNotNull(result.getFinancialDataDTO());
        assertNotNull(result.getCompanyDriveDataDTO());

        assertEquals(0.15, result.getFinancialDataDTO().getEffectiveTaxRate(), 0.01); // 15000 / 100000
        assertEquals(21.0, result.getFinancialDataDTO().getMarginalTaxRate(), 0.01);
        assertEquals(0.05, result.getCompanyDriveDataDTO().getRevenueNextYear());
        assertEquals(2.0, result.getCompanyDriveDataDTO().getSalesToCapitalYears1To5(), 0.01);
        assertEquals(1.5, result.getCompanyDriveDataDTO().getSalesToCapitalYears6To10(), 0.01);
        assertEquals("yahoo_normalized", result.getFinancialDataDTO().getSourceProvenance().getSourceClass());
        assertEquals("2025-06-30", result.getFinancialDataDTO().getSourceProvenance().getSourceDate());
    }

    @Test
    void assembleCompanyData_researchedUsCompanyUsesPrimaryFilingProviderWhenAvailable() {
        String ticker = "AAPL";
        Map<String, Object> basicInfoMap = usBasicInfoMap(ticker);
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(usBasicInfo());
        when(primaryFilingDataProvider.hasPrimaryFinancials(ticker)).thenReturn(true);

        FinancialDataDTO primaryFinancials = financials(112.0, 30.0, 52.0, 22.0, 10.0);
        CompanyFinancialIngestionService.FinancialIngestionData primaryIngestion =
                ingestion(primaryFinancials, SourceProvenance.primaryFiling("sec-xbrl-fixture", "2025-09-30"));
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, primaryFilingDataProvider))
                .thenReturn(primaryIngestion);

        FinancialDataDTO yahooFinancials = financials(100.0, 30.0, 52.0, 22.0, 10.0);
        CompanyFinancialIngestionService.FinancialIngestionData yahooIngestion =
                ingestion(yahooFinancials, SourceProvenance.yahooNormalized("yfinance-http", "2025-09-30"));
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, dataProvider))
                .thenReturn(yahooIngestion);

        stubUsValuationInputs();

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker, true);

        SourceProvenance provenance = result.getFinancialDataDTO().getSourceProvenance();
        assertEquals("primary_filing", provenance.getSourceClass());
        assertEquals("primary_filing_used", provenance.getSourcePolicyStatus());
        assertEquals("sec-xbrl-fixture", provenance.getProvider());
        assertEquals(1, provenance.getDataQualityWarnings().size());
        assertEquals("revenue", provenance.getDataQualityWarnings().get(0).getField());
        assertEquals("material_mismatch", provenance.getDataQualityWarnings().get(0).getStatus());
        assertEquals(100.0, provenance.getDataQualityWarnings().get(0).getNormalizedValue());
        assertEquals(112.0, provenance.getDataQualityWarnings().get(0).getFilingValue());
    }

    @Test
    void assembleCompanyData_researchedUsCompanyFallsBackWhenPrimaryFilingIsNotValuationUsable() {
        String ticker = "AAPL";
        Map<String, Object> basicInfoMap = usBasicInfoMap(ticker);
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(usBasicInfo());
        when(primaryFilingDataProvider.hasPrimaryFinancials(ticker)).thenReturn(true);

        FinancialDataDTO primaryFinancials = financials(100.0, 30.0, 52.0, 22.0, 100.0);
        primaryFinancials.setRevenueLTM(0.0);
        primaryFinancials.setNoOfShareOutstanding(null);
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, primaryFilingDataProvider))
                .thenReturn(ingestion(primaryFinancials, SourceProvenance.primaryFiling(
                        "sec-edgar-companyfacts",
                        "2025-09-30")));

        FinancialDataDTO yahooFinancials = financials(100.0, 24.0, 50.0, 20.0, 10.0);
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, dataProvider))
                .thenReturn(ingestion(yahooFinancials, SourceProvenance.yahooNormalized(
                        "yfinance-http",
                        "2025-09-30")));

        stubUsValuationInputs();

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker, true);

        SourceProvenance provenance = result.getFinancialDataDTO().getSourceProvenance();
        assertEquals("yahoo_normalized", provenance.getSourceClass());
        assertEquals("sec_insufficient_facts_yahoo_fallback", provenance.getSourcePolicyStatus());
        assertEquals("company_report_check_pending", provenance.getCrossCheckStatus());
        assertTrue(provenance.getWarnings().stream()
                .anyMatch(warning -> warning.contains("prior annual revenue")));
        assertEquals(10.0, result.getFinancialDataDTO().getNoOfShareOutstanding());
    }

    @Test
    void assembleCompanyData_researchedUsPrimaryFilingWarningsDoNotAccumulateAcrossRuns() {
        String ticker = "AAPL";
        Map<String, Object> basicInfoMap = usBasicInfoMap(ticker);
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(usBasicInfo());
        when(primaryFilingDataProvider.hasPrimaryFinancials(ticker)).thenReturn(true);

        FinancialDataDTO primaryFinancials = financials(112.0, 30.0, 52.0, 22.0, 10.0);
        CompanyFinancialIngestionService.FinancialIngestionData primaryIngestion =
                ingestion(primaryFinancials, SourceProvenance.primaryFiling("sec-xbrl-fixture", "2025-09-30"));
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, primaryFilingDataProvider))
                .thenReturn(primaryIngestion);

        FinancialDataDTO yahooFinancials = financials(100.0, 30.0, 52.0, 22.0, 10.0);
        CompanyFinancialIngestionService.FinancialIngestionData yahooIngestion =
                ingestion(yahooFinancials, SourceProvenance.yahooNormalized("yfinance-http", "2025-09-30"));
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, dataProvider))
                .thenReturn(yahooIngestion);

        stubUsValuationInputs();

        CompanyDataDTO first = companyDataAssemblyService.assembleCompanyData(ticker, true);
        CompanyDataDTO second = companyDataAssemblyService.assembleCompanyData(ticker, true);

        assertEquals(1, first.getFinancialDataDTO().getSourceProvenance().getDataQualityWarnings().size());
        assertEquals(1, second.getFinancialDataDTO().getSourceProvenance().getDataQualityWarnings().size());
        assertEquals("revenue",
                second.getFinancialDataDTO().getSourceProvenance().getDataQualityWarnings().get(0).getField());
    }

    @Test
    void assembleCompanyData_reconciliationUsesFieldSpecificShareCountThreshold() {
        String ticker = "AAPL";
        Map<String, Object> basicInfoMap = usBasicInfoMap(ticker);
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(usBasicInfo());
        when(primaryFilingDataProvider.hasPrimaryFinancials(ticker)).thenReturn(true);

        CompanyFinancialIngestionService.FinancialIngestionData primaryIngestion =
                ingestion(financials(100.0, 30.0, 52.0, 22.0, 100.0),
                        SourceProvenance.primaryFiling("sec-xbrl-fixture", "2025-09-30"));
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, primaryFilingDataProvider))
                .thenReturn(primaryIngestion);

        CompanyFinancialIngestionService.FinancialIngestionData yahooIngestion =
                ingestion(financials(100.0, 30.0, 52.0, 22.0, 103.0),
                        SourceProvenance.yahooNormalized("yfinance-http", "2025-09-30"));
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, dataProvider))
                .thenReturn(yahooIngestion);

        stubUsValuationInputs();

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker, true);

        SourceProvenance.DataQualityWarning warning = result.getFinancialDataDTO()
                .getSourceProvenance()
                .getDataQualityWarnings()
                .stream()
                .filter(item -> "shares_outstanding".equals(item.getField()))
                .findFirst()
                .orElseThrow();
        assertEquals("material_mismatch", warning.getStatus());
        assertEquals(0.02, warning.getThresholdPct());
    }

    @Test
    void assembleCompanyData_reconciliationWarnsWhenOperatingIncomeSignDiffers() {
        String ticker = "AAPL";
        Map<String, Object> basicInfoMap = usBasicInfoMap(ticker);
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(usBasicInfo());
        when(primaryFilingDataProvider.hasPrimaryFinancials(ticker)).thenReturn(true);

        CompanyFinancialIngestionService.FinancialIngestionData primaryIngestion =
                ingestion(financials(100.0, -1.0, 52.0, 22.0, 100.0),
                        SourceProvenance.primaryFiling("sec-xbrl-fixture", "2025-09-30"));
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, primaryFilingDataProvider))
                .thenReturn(primaryIngestion);

        CompanyFinancialIngestionService.FinancialIngestionData yahooIngestion =
                ingestion(financials(100.0, 1.0, 52.0, 22.0, 100.0),
                        SourceProvenance.yahooNormalized("yfinance-http", "2025-09-30"));
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, dataProvider))
                .thenReturn(yahooIngestion);

        stubUsValuationInputs();

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker, true);

        SourceProvenance.DataQualityWarning warning = result.getFinancialDataDTO()
                .getSourceProvenance()
                .getDataQualityWarnings()
                .stream()
                .filter(item -> "operating_income".equals(item.getField()))
                .findFirst()
                .orElseThrow();
        assertEquals("sign_mismatch", warning.getStatus());
    }

    @Test
    void assembleCompanyData_reconciliationWarnsWhenRdOrSbcMissingFromOneProvider() {
        String ticker = "AAPL";
        Map<String, Object> basicInfoMap = usBasicInfoMap(ticker);
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(usBasicInfo());
        when(primaryFilingDataProvider.hasPrimaryFinancials(ticker)).thenReturn(true);

        FinancialDataDTO primaryFinancials = financials(100.0, 30.0, 52.0, 22.0, 100.0);
        primaryFinancials.setResearchAndDevelopmentMap(Map.of());
        primaryFinancials.setStockBasedCompensationTTM(null);
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, primaryFilingDataProvider))
                .thenReturn(ingestion(primaryFinancials, SourceProvenance.primaryFiling("sec-xbrl-fixture", "2025-09-30")));

        FinancialDataDTO yahooFinancials = financials(100.0, 30.0, 52.0, 22.0, 100.0);
        yahooFinancials.setResearchAndDevelopmentMap(Map.of("currentR&D-0", 20.0));
        yahooFinancials.setStockBasedCompensationTTM(12.0);
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, dataProvider))
                .thenReturn(ingestion(yahooFinancials, SourceProvenance.yahooNormalized("yfinance-http", "2025-09-30")));

        stubUsValuationInputs();

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker, true);

        List<String> warningFields = result.getFinancialDataDTO()
                .getSourceProvenance()
                .getDataQualityWarnings()
                .stream()
                .filter(item -> "missing_present_mismatch".equals(item.getStatus()))
                .map(SourceProvenance.DataQualityWarning::getField)
                .toList();
        assertTrue(warningFields.contains("research_and_development"));
        assertTrue(warningFields.contains("stock_based_compensation"));
    }

    @Test
    void assembleCompanyData_reconciliationWarnsWhenSourceMetadataDiffersOrIsStale() {
        String ticker = "AAPL";
        Map<String, Object> basicInfoMap = usBasicInfoMap(ticker);
        basicInfoMap.put("financialCurrency", "EUR");
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(usBasicInfo());
        when(primaryFilingDataProvider.hasPrimaryFinancials(ticker)).thenReturn(true);

        SourceProvenance primarySource = SourceProvenance.primaryFiling(
                "sec-xbrl-fixture",
                "2024-01-31",
                "2023-12-31");
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, primaryFilingDataProvider))
                .thenReturn(ingestion(financials(100.0, 30.0, 52.0, 22.0, 100.0), primarySource));

        SourceProvenance yahooSource = SourceProvenance.yahooNormalized("yfinance-http", "2025-09-30");
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, dataProvider))
                .thenReturn(ingestion(financials(100.0, 30.0, 52.0, 22.0, 100.0), yahooSource));

        when(currencyRateService.convertCurrency("USD", "EUR", 150.0)).thenReturn(140.0);
        stubUsValuationInputs();

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker, true);

        List<SourceProvenance.DataQualityWarning> warnings = result.getFinancialDataDTO()
                .getSourceProvenance()
                .getDataQualityWarnings();
        assertWarningStatus(warnings, "source_period", "period_mismatch");
        assertWarningStatus(warnings, "source_date", "stale_source_date");
        assertWarningStatus(warnings, "currency", "currency_mismatch");
        SourceProvenance.DataQualityWarning periodWarning = warning(warnings, "source_period", "period_mismatch");
        assertEquals("2025-09-30", periodWarning.getNormalizedPeriodEnd());
        assertEquals("2023-12-31", periodWarning.getFilingPeriodEnd());
    }

    @Test
    void assembleCompanyData_reconciliationWarnsWhenAverageSharesDifferFromPointInTimeShares() {
        String ticker = "AAPL";
        Map<String, Object> basicInfoMap = usBasicInfoMap(ticker);
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(usBasicInfo());
        when(primaryFilingDataProvider.hasPrimaryFinancials(ticker)).thenReturn(true);

        FinancialDataDTO primaryFinancials = financials(100.0, 30.0, 52.0, 22.0, 100.0);
        primaryFinancials.setDilutedSharesOutstanding(90.0);
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, primaryFilingDataProvider))
                .thenReturn(ingestion(primaryFinancials, SourceProvenance.primaryFiling("sec-xbrl-fixture", "2025-09-30")));

        FinancialDataDTO yahooFinancials = financials(100.0, 30.0, 52.0, 22.0, 100.0);
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, dataProvider))
                .thenReturn(ingestion(yahooFinancials, SourceProvenance.yahooNormalized("yfinance-http", "2025-09-30")));

        stubUsValuationInputs();

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker, true);

        SourceProvenance.DataQualityWarning warning = warning(
                result.getFinancialDataDTO().getSourceProvenance().getDataQualityWarnings(),
                "shares_outstanding",
                "average_vs_point_in_time_mismatch");
        assertEquals(90.0, warning.getNormalizedValue());
        assertEquals(100.0, warning.getFilingValue());
    }

    @Test
    void assembleCompanyData_reconciliationWarnsWhenRequiredFieldsAreMissingFromBothProviders() {
        String ticker = "AAPL";
        Map<String, Object> basicInfoMap = usBasicInfoMap(ticker);
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(usBasicInfo());
        when(primaryFilingDataProvider.hasPrimaryFinancials(ticker)).thenReturn(true);

        FinancialDataDTO primaryFinancials = financials(100.0, 30.0, 52.0, 22.0, 100.0);
        primaryFinancials.setCashAndMarkablTTM(null);
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, primaryFilingDataProvider))
                .thenReturn(ingestion(primaryFinancials, SourceProvenance.primaryFiling("sec-xbrl-fixture", "2025-09-30")));

        FinancialDataDTO yahooFinancials = financials(100.0, 30.0, 52.0, 22.0, 100.0);
        yahooFinancials.setCashAndMarkablTTM(null);
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, dataProvider))
                .thenReturn(ingestion(yahooFinancials, SourceProvenance.yahooNormalized("yfinance-http", "2025-09-30")));

        stubUsValuationInputs();

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker, true);

        assertWarningStatus(
                result.getFinancialDataDTO().getSourceProvenance().getDataQualityWarnings(),
                "cash_and_short_term_investments",
                "missing_required_field");
    }

    @Test
    void assembleCompanyData_researchedUsCompanyUsesExplicitFallbackOnlyAfterPrimaryProviderUnavailable() {
        String ticker = "AAPL";
        Map<String, Object> basicInfoMap = usBasicInfoMap(ticker);
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(usBasicInfo());
        when(primaryFilingDataProvider.hasPrimaryFinancials(ticker)).thenReturn(false);

        CompanyFinancialIngestionService.FinancialIngestionData yahooIngestion =
                ingestion(financials(100.0, 24.0, 50.0, 20.0, 10.0),
                        SourceProvenance.yahooNormalized("yfinance-http", "2025-09-30"));
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, dataProvider))
                .thenReturn(yahooIngestion);

        stubUsValuationInputs();

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker, true);

        SourceProvenance provenance = result.getFinancialDataDTO().getSourceProvenance();
        assertEquals("yahoo_normalized", provenance.getSourceClass());
        assertEquals("sec_http_error_yahoo_fallback", provenance.getSourcePolicyStatus());
        assertEquals("company_report_check_pending", provenance.getCrossCheckStatus());
        assertTrue(provenance.getWarnings().stream()
                .anyMatch(warning -> warning.contains("primary filing provider returned unavailable")));
    }

    @Test
    void assembleCompanyData_researchedUsFallbackIncludesClassifiedSecUnavailableStatus() {
        String ticker = "MSFT";
        Map<String, Object> basicInfoMap = usBasicInfoMap(ticker);
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(usBasicInfo());
        when(primaryFilingDataProvider.hasPrimaryFinancials(ticker)).thenReturn(false);
        when(primaryFilingDataProvider.getPrimaryFinancialsAvailability(ticker))
                .thenReturn(PrimaryFilingAvailability.unavailable(
                        "missing_user_agent",
                        "sec-edgar-companyfacts",
                        List.of("SEC EDGAR provider requires SEC_USER_AGENT/provider.sec.user-agent.")));

        CompanyFinancialIngestionService.FinancialIngestionData yahooIngestion =
                ingestion(financials(100.0, 24.0, 50.0, 20.0, 10.0),
                        SourceProvenance.yahooNormalized("yfinance-http", "2025-09-30"));
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, dataProvider))
                .thenReturn(yahooIngestion);

        stubUsValuationInputs();

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker, true);

        SourceProvenance provenance = result.getFinancialDataDTO().getSourceProvenance();
        assertEquals("sec_missing_user_agent_yahoo_fallback", provenance.getSourcePolicyStatus());
        assertTrue(provenance.getWarnings().stream()
                .anyMatch(warning -> warning.contains("missing_user_agent")));
        assertTrue(provenance.getWarnings().stream()
                .anyMatch(warning -> warning.contains("SEC_USER_AGENT")));
    }

    @Test
    void assembleCompanyData_researchedUsHttpErrorFallbackUsesSpecificPhase9Status() {
        String ticker = "MSFT";
        Map<String, Object> basicInfoMap = usBasicInfoMap(ticker);
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(usBasicInfo());
        when(primaryFilingDataProvider.hasPrimaryFinancials(ticker)).thenReturn(false);
        when(primaryFilingDataProvider.getPrimaryFinancialsAvailability(ticker))
                .thenReturn(PrimaryFilingAvailability.unavailable(
                        "http_error",
                        "sec-edgar-companyfacts",
                        List.of("SEC companyfacts request returned 503.")));

        CompanyFinancialIngestionService.FinancialIngestionData yahooIngestion =
                ingestion(financials(100.0, 24.0, 50.0, 20.0, 10.0),
                        SourceProvenance.yahooNormalized("yfinance-http", "2025-09-30"));
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, dataProvider))
                .thenReturn(yahooIngestion);

        stubUsValuationInputs();

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker, true);

        SourceProvenance provenance = result.getFinancialDataDTO().getSourceProvenance();
        assertEquals("yahoo_normalized", provenance.getSourceClass());
        assertEquals("sec_http_error_yahoo_fallback", provenance.getSourcePolicyStatus());
        assertEquals("company_report_check_pending", provenance.getCrossCheckStatus());
        assertTrue(provenance.getWarnings().stream()
                .anyMatch(warning -> warning.contains("http_error")));
    }

    @Test
    void assembleCompanyData_researchedUsUnsupportedTaxonomyUsesSpecificPhase9Status() {
        String ticker = "ASML";
        Map<String, Object> basicInfoMap = usBasicInfoMap(ticker);
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(usBasicInfo());
        when(primaryFilingDataProvider.hasPrimaryFinancials(ticker)).thenReturn(false);
        when(primaryFilingDataProvider.getPrimaryFinancialsAvailability(ticker))
                .thenReturn(PrimaryFilingAvailability.unavailable(
                        "unsupported_taxonomy",
                        "sec-edgar-companyfacts",
                        List.of("SEC companyfacts used ifrs-full taxonomy.")));

        CompanyFinancialIngestionService.FinancialIngestionData yahooIngestion =
                ingestion(financials(100.0, 24.0, 50.0, 20.0, 10.0),
                        SourceProvenance.yahooNormalized("yfinance-http", "2025-09-30"));
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, dataProvider))
                .thenReturn(yahooIngestion);

        stubUsValuationInputs();

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker, true);

        SourceProvenance provenance = result.getFinancialDataDTO().getSourceProvenance();
        assertEquals("sec_unsupported_taxonomy_yahoo_fallback", provenance.getSourcePolicyStatus());
        assertEquals("company_report_check_pending", provenance.getCrossCheckStatus());
        assertTrue(provenance.getWarnings().stream()
                .anyMatch(warning -> warning.contains("unsupported_taxonomy")));
    }

    @Test
    void assembleCompanyData_researchedNonUsCompanyUsesExplicitCompanyReportPendingStatus() {
        String ticker = "SAP.DE";
        Map<String, Object> basicInfoMap = new HashMap<>();
        basicInfoMap.put("currency", "EUR");
        basicInfoMap.put("financialCurrency", "EUR");
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);

        BasicInfoDataDTO basicInfoDataDTO = new BasicInfoDataDTO();
        basicInfoDataDTO.setCountryOfIncorporation("Germany");
        basicInfoDataDTO.setCurrency("EUR");
        basicInfoDataDTO.setIndustryGlobal("Software");
        basicInfoDataDTO.setMarketCap(1000000000L);
        basicInfoDataDTO.setFirstTradeDateEpochUtc(1600000000);
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(basicInfoDataDTO);

        CompanyFinancialIngestionService.FinancialIngestionData yahooIngestion =
                ingestion(financials(100.0, 24.0, 50.0, 20.0, 10.0),
                        SourceProvenance.yahooNormalized("yfinance-http", "2025-12-31"));
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap, dataProvider))
                .thenReturn(yahooIngestion);

        when(countryEquityRepository.findCorporateTaxRateByCountry("Germany")).thenReturn(Optional.of(30.0));
        when(dataProvider.getRevenueEstimate(ticker, "yearly")).thenReturn(new HashMap<>());
        SectorMapping sectorMapping = new SectorMapping();
        sectorMapping.setIndustryAsPerExcel("Software");
        when(sectorMappingRepository.findByIndustryName("Software")).thenReturn(sectorMapping);
        IndustryAveragesGlobal avgGlo = new IndustryAveragesGlobal();
        avgGlo.setPreTaxOperatingMargin(20.0);
        avgGlo.setAnnualAverageRevenueGrowth(5.0);
        when(industryAvgGloRepository.findByIndustryName("Software")).thenReturn(avgGlo);
        when(industryAvgGloRepository.findSalesToCapitalByIndustryName("Software")).thenReturn(Optional.of(1.2));
        when(costOfCapitalRepository.findCostOfCapitalByRegion(anyString())).thenReturn(Optional.of(new CostOfCapital()));

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker, true);

        SourceProvenance provenance = result.getFinancialDataDTO().getSourceProvenance();
        assertEquals("primary_adapter_not_supported_yahoo_normalized", provenance.getSourcePolicyStatus());
        assertEquals("company_report_check_pending", provenance.getCrossCheckStatus());
    }

    @Test
    void testAssembleCompanyData_CurrencyConversion() throws Exception {
        String ticker = "SOME_TICKER";

        Map<String, Object> basicInfoMap = new HashMap<>();
        basicInfoMap.put("currency", "EUR");
        basicInfoMap.put("financialCurrency", "USD");
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);

        BasicInfoDataDTO basicInfoDataDTO = new BasicInfoDataDTO();
        basicInfoDataDTO.setCountryOfIncorporation("France");
        basicInfoDataDTO.setCurrency("EUR");
        basicInfoDataDTO.setFirstTradeDateEpochUtc(1500000000); // added to prevent NPE
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(basicInfoDataDTO);

        FinancialDataDTO financialDataDTO = new FinancialDataDTO();
        financialDataDTO.setStockPrice(150.0);
        financialDataDTO.setRevenueTTM(100.0); // avoid zero division
        financialDataDTO.setRevenueLTM(90.0);
        financialDataDTO.setOperatingIncomeTTM(10.0); // avoid zero division
        financialDataDTO.setOperatingIncomeLTM(9.0);

        CompanyFinancialIngestionService.FinancialIngestionData ingestionData = new CompanyFinancialIngestionService.FinancialIngestionData(
                financialDataDTO, new ArrayList<>(), new ArrayList<>(), null, null);
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap)).thenReturn(ingestionData);

        when(currencyRateService.convertCurrency("EUR", "USD", 150.0)).thenReturn(165.0);
        when(countryEquityRepository.findCorporateTaxRateByCountry("France")).thenReturn(Optional.of(25.0));

        when(dataProvider.getRevenueEstimate(ticker, "yearly")).thenReturn(new HashMap<>());

        // Setup minimal valid data to avoid NPE
        SectorMapping mapping = new SectorMapping();
        mapping.setIndustryAsPerExcel("Unknown");
        when(sectorMappingRepository.findByIndustryName(any())).thenReturn(mapping);
        when(industryAvgGloRepository.findByIndustryName(any())).thenReturn(new IndustryAveragesGlobal());

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker);

        assertEquals(165.0, result.getFinancialDataDTO().getStockPrice());
        assertEquals("USD", result.getBasicInfoDataDTO().getStockCurrency());
    }

    @Test
    void testAssembleCompanyData_CurrencyConversionFailureStopsValuation() {
        String ticker = "SOME_TICKER";

        Map<String, Object> basicInfoMap = new HashMap<>();
        basicInfoMap.put("currency", "EUR");
        basicInfoMap.put("financialCurrency", "USD");
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);

        BasicInfoDataDTO basicInfoDataDTO = new BasicInfoDataDTO();
        basicInfoDataDTO.setCountryOfIncorporation("France");
        basicInfoDataDTO.setCurrency("EUR");
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(basicInfoDataDTO);

        FinancialDataDTO financialDataDTO = new FinancialDataDTO();
        financialDataDTO.setStockPrice(150.0);
        CompanyFinancialIngestionService.FinancialIngestionData ingestionData =
                new CompanyFinancialIngestionService.FinancialIngestionData(
                        financialDataDTO, new ArrayList<>(), new ArrayList<>(), null, null);
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap)).thenReturn(ingestionData);

        when(currencyRateService.convertCurrency("EUR", "USD", 150.0))
                .thenThrow(new IllegalArgumentException("Currency not found: EUR or USD"));

        IllegalStateException error = assertThrows(IllegalStateException.class,
                () -> companyDataAssemblyService.assembleCompanyData(ticker));

        assertTrue(error.getMessage().contains("Cannot safely value SOME_TICKER"));
    }

    @Test
    void testAssembleCompanyData_Global_Company() throws Exception {
        String ticker = "GLOBAL_CO";

        Map<String, Object> basicInfoMap = new HashMap<>();
        basicInfoMap.put("currency", "GBP");
        basicInfoMap.put("financialCurrency", "GBP");
        when(dataProvider.getCompanyInfo(ticker)).thenReturn(basicInfoMap);

        BasicInfoDataDTO basicInfoDataDTO = new BasicInfoDataDTO();
        basicInfoDataDTO.setCountryOfIncorporation("United Kingdom");
        basicInfoDataDTO.setCurrency("GBP");
        basicInfoDataDTO.setIndustryGlobal("Manufacturing");
        basicInfoDataDTO.setTimeZoneFullName("Europe/London");
        basicInfoDataDTO.setMarketCap(50000000L); // added to prevent NPE
        basicInfoDataDTO.setFirstTradeDateEpochUtc(1500000000); // added to prevent NPE
        when(companyDataMapper.mapBasicInfo(ticker, basicInfoMap)).thenReturn(basicInfoDataDTO);

        FinancialDataDTO financialDataDTO = new FinancialDataDTO();
        financialDataDTO.setRevenueTTM(100.0); // avoid zero division
        financialDataDTO.setRevenueLTM(90.0);
        financialDataDTO.setOperatingIncomeTTM(10.0); // avoid zero division
        financialDataDTO.setOperatingIncomeLTM(9.0);

        CompanyFinancialIngestionService.FinancialIngestionData ingestionData = new CompanyFinancialIngestionService.FinancialIngestionData(
                financialDataDTO, new ArrayList<>(), new ArrayList<>(), null, null);
        when(companyFinancialIngestionService.ingest(ticker, basicInfoMap)).thenReturn(ingestionData);

        when(countryEquityRepository.findCorporateTaxRateByCountry("United Kingdom")).thenReturn(Optional.of(19.0));
        when(dataProvider.getRevenueEstimate(ticker, "yearly")).thenReturn(new HashMap<>());

        SectorMapping sectorMapping = new SectorMapping();
        sectorMapping.setIndustryAsPerExcel("Manufacturing");
        when(sectorMappingRepository.findByIndustryName("Manufacturing")).thenReturn(sectorMapping);

        IndustryAveragesGlobal avgGlo = new IndustryAveragesGlobal();
        avgGlo.setPreTaxOperatingMargin(20.0);
        avgGlo.setAnnualAverageRevenueGrowth(5.0);
        when(industryAvgGloRepository.findByIndustryName("Manufacturing")).thenReturn(avgGlo);
        when(industryAvgGloRepository.findSalesToCapitalByIndustryName("Manufacturing")).thenReturn(Optional.of(1.2));

        CostOfCapital costOfCapital = new CostOfCapital();
        when(costOfCapitalRepository.findCostOfCapitalByRegion("Europe")).thenReturn(Optional.of(costOfCapital));

        CompanyDataDTO result = companyDataAssemblyService.assembleCompanyData(ticker);

        assertNotNull(result);
        assertEquals(19.0, result.getFinancialDataDTO().getMarginalTaxRate(), 0.01);
        assertEquals(1.2, result.getCompanyDriveDataDTO().getSalesToCapitalYears1To5(), 0.01);
        assertEquals(1.2, result.getCompanyDriveDataDTO().getSalesToCapitalYears6To10(), 0.01);
    }

    private static Map<String, Object> usBasicInfoMap(String ticker) {
        Map<String, Object> basicInfoMap = new HashMap<>();
        basicInfoMap.put("ticker", ticker);
        basicInfoMap.put("currency", "USD");
        basicInfoMap.put("financialCurrency", "USD");
        return basicInfoMap;
    }

    private static BasicInfoDataDTO usBasicInfo() {
        BasicInfoDataDTO basicInfoDataDTO = new BasicInfoDataDTO();
        basicInfoDataDTO.setCountryOfIncorporation("United States");
        basicInfoDataDTO.setCurrency("USD");
        basicInfoDataDTO.setIndustryGlobal("Technology");
        basicInfoDataDTO.setTimeZoneFullName("America/New_York");
        basicInfoDataDTO.setMarketCap(1000000000L);
        basicInfoDataDTO.setFirstTradeDateEpochUtc(1600000000);
        return basicInfoDataDTO;
    }

    private static FinancialDataDTO financials(
            double revenue,
            double operatingIncome,
            double cash,
            double debt,
            double shares) {
        FinancialDataDTO financialDataDTO = new FinancialDataDTO();
        financialDataDTO.setStockPrice(150.0);
        financialDataDTO.setRevenueTTM(revenue);
        financialDataDTO.setRevenueLTM(revenue);
        financialDataDTO.setOperatingIncomeTTM(operatingIncome);
        financialDataDTO.setOperatingIncomeLTM(operatingIncome);
        financialDataDTO.setCashAndMarkablTTM(cash);
        financialDataDTO.setCashAndMarkablLTM(cash);
        financialDataDTO.setBookValueDebtTTM(debt);
        financialDataDTO.setBookValueDebtLTM(debt);
        financialDataDTO.setNoOfShareOutstanding(shares);
        financialDataDTO.setResearchAndDevelopmentMap(Map.of("currentR&D-0", 4.0));
        return financialDataDTO;
    }

    private static CompanyFinancialIngestionService.FinancialIngestionData ingestion(
            FinancialDataDTO financials,
            SourceProvenance provenance) {
        return new CompanyFinancialIngestionService.FinancialIngestionData(
                financials,
                List.of(90.0, 95.0, 100.0),
                List.of(0.20, 0.22, 0.24),
                5.0,
                25.0,
                provenance);
    }

    private static void assertWarningStatus(
            List<SourceProvenance.DataQualityWarning> warnings,
            String field,
            String status) {
        warning(warnings, field, status);
    }

    private static SourceProvenance.DataQualityWarning warning(
            List<SourceProvenance.DataQualityWarning> warnings,
            String field,
            String status) {
        return warnings.stream()
                .filter(item -> field.equals(item.getField()))
                .filter(item -> status.equals(item.getStatus()))
                .findFirst()
                .orElseThrow();
    }

    private void stubUsValuationInputs() {
        when(countryEquityRepository.findCorporateTaxRateByCountry("United States")).thenReturn(Optional.of(21.0));
        when(dataProvider.getRevenueEstimate(anyString(), eq("yearly"))).thenReturn(new HashMap<>());

        SectorMapping sectorMapping = new SectorMapping();
        sectorMapping.setIndustryAsPerExcel("Technology");
        when(sectorMappingRepository.findByIndustryName("Technology")).thenReturn(sectorMapping);
        when(industryAvgUSRepository.findSalesToCapitalByIndustryName("Technology")).thenReturn(Optional.of(1.5));

        IndustryAveragesUS avgUS = new IndustryAveragesUS();
        avgUS.setPreTaxOperatingMargin(25.0);
        avgUS.setAnnualAverageRevenueGrowth(8.0);
        when(industryAvgUSRepository.findByIndustryName("Technology")).thenReturn(avgUS);

        InputStatDistribution inputStat = new InputStatDistribution();
        inputStat.setPreTaxOperatingMarginFirstQuartile(10.0);
        inputStat.setPreTaxOperatingMarginMedian(20.0);
        inputStat.setPreTaxOperatingMarginThirdQuartile(30.0);
        inputStat.setSalesToInvestedCapitalThirdQuartile(2.0);
        when(inputStatRepository.findFirstByIndustryGroupOrderByIdAsc("Technology"))
                .thenReturn(Optional.of(inputStat));

        CostOfCapital costOfCapital = new CostOfCapital();
        costOfCapital.setMedian("0.08");
        costOfCapital.setThirdQuartile("0.10");
        when(costOfCapitalRepository.findCostOfCapitalByRegion("US")).thenReturn(Optional.of(costOfCapital));
    }
}
