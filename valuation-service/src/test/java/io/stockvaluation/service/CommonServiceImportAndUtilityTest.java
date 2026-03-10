package io.stockvaluation.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.stockvaluation.config.ValuationAssumptionProperties;
import io.stockvaluation.domain.BondRating;
import io.stockvaluation.domain.CostOfCapital;
import io.stockvaluation.domain.CountryEquity;
import io.stockvaluation.domain.FailureRate;
import io.stockvaluation.domain.IndustryAveragesGlobal;
import io.stockvaluation.domain.IndustryAveragesUS;
import io.stockvaluation.domain.Input;
import io.stockvaluation.domain.InputStatDistribution;
import io.stockvaluation.domain.LargeBondSpread;
import io.stockvaluation.domain.PastExpense;
import io.stockvaluation.domain.RDConverter;
import io.stockvaluation.domain.RegionEquity;
import io.stockvaluation.domain.RiskFreeRate;
import io.stockvaluation.domain.SectorMapping;
import io.stockvaluation.domain.SmallBondSpread;
import io.stockvaluation.dto.DividendDataDTO;
import io.stockvaluation.dto.InputRequestDTO;
import io.stockvaluation.dto.LeaseResultDTO;
import io.stockvaluation.dto.PastExpenseRequestDTO;
import io.stockvaluation.repository.BondRatingRepository;
import io.stockvaluation.repository.CostOfCapitalRepository;
import io.stockvaluation.repository.CountryEquityRepository;
import io.stockvaluation.repository.FailureRateRepository;
import io.stockvaluation.repository.IndustryAveragesGlobalRepository;
import io.stockvaluation.repository.IndustryAveragesUSRepository;
import io.stockvaluation.repository.InputRepository;
import io.stockvaluation.repository.InputStatRepository;
import io.stockvaluation.repository.LargeSpreadRepository;
import io.stockvaluation.repository.RDConverterRepository;
import io.stockvaluation.repository.RegionEquityRepository;
import io.stockvaluation.repository.RiskFreeRateRepository;
import io.stockvaluation.repository.SectorMappingRepository;
import io.stockvaluation.repository.SmallSpreadRepository;
import io.stockvaluation.provider.DataProvider;
import org.apache.poi.ss.usermodel.CellStyle;
import org.apache.poi.ss.usermodel.DataFormat;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CommonServiceImportAndUtilityTest {

    @Mock
    private CountryEquityRepository countryEquityRepository;
    @Mock
    private SectorMappingRepository sectorMappingRepository;
    @Mock
    private RestTemplate restTemplate;
    @Mock
    private DataProvider dataProvider;
    @Mock
    private RiskFreeRateRepository riskFreeRateRepository;
    @Mock
    private IndustryAveragesUSRepository industryAveragesUSRepository;
    @Mock
    private IndustryAveragesGlobalRepository industryAveragesGlobalRepository;
    @Mock
    private InputStatRepository inputStatRepository;
    @Mock
    private RDConverterRepository rdConverterRepository;
    @Mock
    private RegionEquityRepository regionEquityRepository;
    @Mock
    private CostOfCapitalRepository costOfCapitalRepository;
    @Mock
    private LargeSpreadRepository largeSpreadRepository;
    @Mock
    private SmallSpreadRepository smallSpreadRepository;
    @Mock
    private FailureRateRepository failureRateRepository;
    @Mock
    private BondRatingRepository bondRatingRepository;
    @Mock
    private CurrencyRateService currencyRateService;
    @Mock
    private InputRepository inputRepository;
    @Mock
    private CompanyDataMapper companyDataMapper;
    @Mock
    private CompanyFinancialIngestionService companyFinancialIngestionService;
    @Mock
    private ValuationAssumptionProperties valuationAssumptionProperties;
    @Mock
    private CompanyDataAssemblyService companyDataAssemblyService;
    @Mock
    private SegmentWeightedParameterService segmentWeightedParameterService;

    @InjectMocks
    private CommonService commonService;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void loadReferenceDataAndGetAllMethodsUseRepositoryContracts() throws Exception {
        commonService.loadIndustryUSData(jsonFile("[{\"industryName\":\"Software\",\"costOfCapital\":7.5}]"));
        commonService.loadIndustryGloData(jsonFile("[{\"industryName\":\"Software Global\",\"costOfCapital\":8.5}]"));
        commonService.loadCountryEquityData(jsonFile("[{\"country\":\"Sweden\",\"countryRiskPremium\":1.2}]"));
        commonService.loadRegionEquityData(jsonFile("[{\"region\":\"Europe\",\"erp\":4.0}]"));
        commonService.loadRDConverterData(jsonFile("[{\"industryName\":\"Software\",\"amortizationPeriod\":4}]"));
        commonService.loadRegionSectorMapping(jsonFile("[{\"yahooSector\":\"Technology\",\"industryAsPerexcel\":\"Software (System & Application)\"}]"));
        commonService.loadRiskFreeRate(jsonFile("[{\"currency\":\"USD\",\"riskfreeRate\":4.2}]"));
        commonService.loadCostOfCapital(jsonFile("[{\"region\":\"US\",\"median\":\"8.0\"}]"));
        commonService.loadLargeSpread(jsonFile("[{\"rating\":\"A\",\"spread\":1.5}]"));
        commonService.loadSmallSpread(jsonFile("[{\"rating\":\"BBB\",\"spread\":2.0}]"));
        commonService.loadBondRating(jsonFile("[{\"rating\":\"AAA\",\"year_1\":0.1}]"));
        commonService.loadFailureRate(jsonFile("[{\"age\":5,\"sector\":\"tech\",\"failureRate\":\"2%\"}]"));
        commonService.loadInputStat(jsonFile("[{\"industryGroup\":\"Software\",\"count\":10}]"));

        verify(industryAveragesUSRepository).saveAll(argThat((List<IndustryAveragesUS> list) ->
                list.size() == 1 && "Software".equals(list.get(0).getIndustryName())));
        verify(industryAveragesGlobalRepository).saveAll(argThat((List<IndustryAveragesGlobal> list) ->
                list.size() == 1 && "Software Global".equals(list.get(0).getIndustryName())));
        verify(countryEquityRepository).saveAll(argThat((List<CountryEquity> list) ->
                list.size() == 1 && "Sweden".equals(list.get(0).getCountry())));
        verify(regionEquityRepository).saveAll(argThat((List<RegionEquity> list) ->
                list.size() == 1 && "Europe".equals(list.get(0).getRegion())));
        verify(rdConverterRepository).saveAll(argThat((List<RDConverter> list) ->
                list.size() == 1 && "Software".equals(list.get(0).getIndustryName())));
        verify(sectorMappingRepository).saveAll(argThat((List<SectorMapping> list) ->
                list.size() == 1 && "Technology".equals(list.get(0).getYahooSector())));
        verify(riskFreeRateRepository).saveAll(argThat((List<RiskFreeRate> list) ->
                list.size() == 1 && "USD".equals(list.get(0).getCurrency())));
        verify(costOfCapitalRepository).saveAll(argThat((List<CostOfCapital> list) ->
                list.size() == 1 && "US".equals(list.get(0).getRegion())));
        verify(largeSpreadRepository).saveAll(argThat((List<LargeBondSpread> list) ->
                list.size() == 1 && "A".equals(list.get(0).getRating())));
        verify(smallSpreadRepository).saveAll(argThat((List<SmallBondSpread> list) ->
                list.size() == 1 && "BBB".equals(list.get(0).getRating())));
        verify(bondRatingRepository).saveAll(argThat((List<BondRating> list) ->
                list.size() == 1 && "AAA".equals(list.get(0).getRating())));
        verify(failureRateRepository).saveAll(argThat((List<FailureRate> list) ->
                list.size() == 1 && "tech".equals(list.get(0).getSector())));
        verify(inputStatRepository).saveAll(argThat((List<InputStatDistribution> list) ->
                list.size() == 1 && "Software".equals(list.get(0).getIndustryGroup())));

        List<IndustryAveragesUS> usList = List.of(new IndustryAveragesUS());
        List<IndustryAveragesGlobal> globalList = List.of(new IndustryAveragesGlobal());
        List<CountryEquity> countryList = List.of(new CountryEquity());
        List<RegionEquity> regionList = List.of(new RegionEquity());
        List<RDConverter> rdList = List.of(new RDConverter());
        List<SectorMapping> sectorList = List.of(new SectorMapping());
        List<RiskFreeRate> rateList = List.of(new RiskFreeRate());
        List<CostOfCapital> capitalList = List.of(new CostOfCapital());
        List<LargeBondSpread> largeList = List.of(new LargeBondSpread());
        List<SmallBondSpread> smallList = List.of(new SmallBondSpread());
        List<BondRating> bondList = List.of(new BondRating());
        List<FailureRate> failureList = List.of(new FailureRate());
        List<InputStatDistribution> statList = List.of(new InputStatDistribution());

        when(industryAveragesUSRepository.findAll()).thenReturn(usList);
        when(industryAveragesGlobalRepository.findAll()).thenReturn(globalList);
        when(countryEquityRepository.findAll()).thenReturn(countryList);
        when(regionEquityRepository.findAll()).thenReturn(regionList);
        when(rdConverterRepository.findAll()).thenReturn(rdList);
        when(sectorMappingRepository.findAll()).thenReturn(sectorList);
        when(riskFreeRateRepository.findAll()).thenReturn(rateList);
        when(costOfCapitalRepository.findAll()).thenReturn(capitalList);
        when(largeSpreadRepository.findAll()).thenReturn(largeList);
        when(smallSpreadRepository.findAll()).thenReturn(smallList);
        when(bondRatingRepository.findAll()).thenReturn(bondList);
        when(failureRateRepository.findAll()).thenReturn(failureList);
        when(inputStatRepository.findAll()).thenReturn(statList);

        assertEquals(usList, commonService.getAllIndustryUS());
        assertEquals(globalList, commonService.getAllIndustryGlo());
        assertEquals(countryList, commonService.getAllCountryEquity());
        assertEquals(regionList, commonService.getAllRegionEquity());
        assertEquals(rdList, commonService.getAllRDConverter());
        assertEquals(sectorList, commonService.getAllSectorMapping());
        assertEquals(rateList, commonService.getAllRiskFreeRate());
        assertEquals(capitalList, commonService.getAllCostOfCapital());
        assertEquals(largeList, commonService.getAllLargeSpread());
        assertEquals(smallList, commonService.getAllSmallSpread());
        assertEquals(bondList, commonService.getAllBondRating());
        assertEquals(failureList, commonService.getAllFailureRate());
        assertEquals(statList, commonService.getAllInputStat());
    }

    @Test
    void saveInputDataDeleteInputAndSaveSingleInputMapPastExpenses() {
        InputRequestDTO input = new InputRequestDTO(
                "2026-03-10",
                "Example Corp",
                "EXMP",
                "USD",
                "Software",
                "Software",
                10.0,
                100.0,
                20.0,
                true,
                25.0,
                List.of(new PastExpenseRequestDTO(3.0), new PastExpenseRequestDTO(2.0)));

        commonService.saveInputData(List.of(input));
        ArgumentCaptor<List<Input>> batchCaptor = ArgumentCaptor.forClass(List.class);
        verify(inputRepository).saveAll(batchCaptor.capture());
        assertEquals(1, batchCaptor.getValue().size());
        assertEquals(2, batchCaptor.getValue().get(0).getPastExpense().size());
        assertEquals("EXMP", batchCaptor.getValue().get(0).getTicker());

        commonService.saveSingleInputData(input);
        ArgumentCaptor<Input> singleCaptor = ArgumentCaptor.forClass(Input.class);
        verify(inputRepository).save(singleCaptor.capture());
        assertEquals("Example Corp", singleCaptor.getValue().getCompanyName());
        assertEquals(2, singleCaptor.getValue().getPastExpense().size());
        for (PastExpense pastExpense : singleCaptor.getValue().getPastExpense()) {
            assertEquals(singleCaptor.getValue(), pastExpense.getInput());
        }

        when(inputRepository.findAll()).thenReturn(List.of(singleCaptor.getValue()));
        assertEquals(1, commonService.getAllInputData().size());

        when(inputRepository.existsById(1L)).thenReturn(true);
        commonService.deleteInput(1L);
        verify(inputRepository).deleteById(1L);

        when(inputRepository.existsById(2L)).thenReturn(false);
        assertThrows(RuntimeException.class, () -> commonService.deleteInput(2L));
    }

    @Test
    void leaseConversionDividendParsingAndRdValuesCoverUtilityBranches() {
        when(valuationAssumptionProperties.getPreTaxCostOfDebt()).thenReturn(0.05);

        assertEquals(0.0, commonService.calculateOperatingLeaseConverter().getAdjustmentToTotalDebt());
        assertEquals(0.0, commonService.calculateOperatingLeaseConverter(null, new Double[]{1.0}, 1.0).getAdjustmentToTotalDebt());
        assertEquals(0.0, commonService.calculateOperatingLeaseConverter(10.0, new Double[]{}, 1.0).getAdjustmentToTotalDebt());
        assertEquals(0.0, commonService.calculateOperatingLeaseConverter(10.0, new Double[]{0.0, 0.0}, 10.0).getAdjustmentToTotalDebt());

        LeaseResultDTO result = commonService.calculateOperatingLeaseConverter(
                100.0,
                new Double[]{50.0, 40.0, 30.0, 20.0, 10.0},
                60.0);
        assertNotNull(result);
        assertEquals(result.getDepreciationOnOperatingLease(), result.getAdjustmentToDepreciation());
        assertEquals(42.0 / Math.pow(1.05, 6), commonService.calculateValue(0, 42.0, 0.05), 1e-9);

        Map<String, Object> dividendPayload = new LinkedHashMap<>();
        dividendPayload.put("dividendRate", "2.5");
        dividendPayload.put("dividendYield", 0.03);
        dividendPayload.put("payoutRatio", "0.55");
        dividendPayload.put("trailingAnnualDividendRate", 2.4);
        dividendPayload.put("trailingAnnualDividendYield", "0.028");
        dividendPayload.put("exDividendDate", "1700000000");
        dividendPayload.put("lastDividendValue", "0.62");
        dividendPayload.put("lastDividendDate", 1700000001L);
        dividendPayload.put("fiveYearAvgDividendYield", "0.025");
        dividendPayload.put("dividendGrowthRate", "0.06");
        dividendPayload.put("dividendHistory", Map.of("2024-01-01", "0.62", "2023-10-01", 0.60));
        when(dataProvider.getDividendData("KO")).thenReturn(dividendPayload);

        DividendDataDTO dividendData = commonService.fetchDividendData("KO");
        assertEquals(2.5, dividendData.getDividendRate());
        assertEquals(0.03, dividendData.getDividendYield());
        assertEquals(0.55, dividendData.getPayoutRatio());
        assertEquals(1700000000L, dividendData.getExDividendDate());
        assertEquals(2, dividendData.getDividendHistory().size());

        when(dataProvider.getDividendData("NONE")).thenReturn(Map.of());
        assertNull(commonService.fetchDividendData("NONE"));

        when(dataProvider.getDividendData("ERR")).thenThrow(new IllegalStateException("boom"));
        assertNull(commonService.fetchDividendData("ERR"));

        assertEquals(Map.of(
                "totalResearchAsset", 0.0,
                "totalAmortization", 0.0,
                "adjustmentToOperatingIncome", 0.0), commonService.getR_DValues("AAPL", false));
        assertEquals(Map.of(), commonService.getR_DValues("AAPL", true));
    }

    @Test
    void convertExcelUtilitiesTransformWorkbookContentIntoJson() throws Exception {
        List<Map<String, Object>> countryRows = objectMapper.readValue(
                commonService.convertExcelToJson(countryWorkbook()),
                new TypeReference<>() {
                });
        assertEquals("Sweden", countryRows.get(0).get("country"));
        assertEquals(12.0, ((Number) countryRows.get(0).get("equityRiskPremium")).doubleValue(), 1e-9);

        List<Map<String, Object>> singleObjectRows = objectMapper.readValue(
                commonService.convertExcelToJsonSingleObject(singleObjectWorkbook()),
                new TypeReference<>() {
                });
        assertEquals("Example Corp", singleObjectRows.get(0).get("companyName"));
        assertEquals(12.5, ((Number) singleObjectRows.get(0).get("revenueGrowth")).doubleValue(), 1e-9);
        assertEquals("03/10/2026", singleObjectRows.get(0).get("valuationDate"));

        List<Map<String, Object>> industryRows = objectMapper.readValue(
                commonService.convertIndustryAverageExcelToJson(industryAverageWorkbook()),
                new TypeReference<>() {
                });
        assertEquals("Software", industryRows.get(0).get("industryName"));
        assertEquals(25.0, ((Number) industryRows.get(0).get("preTaxOperatingMargin")).doubleValue(), 1e-9);

        List<Map<String, Object>> countryEquityRows = objectMapper.readValue(
                commonService.convertCountryEquityExcelToJson(countryEquityWorkbook()),
                new TypeReference<>() {
                });
        assertEquals("Sweden", countryEquityRows.get(0).get("country"));
        assertEquals(5.0, ((Number) countryEquityRows.get(0).get("countryRiskPremium")).doubleValue(), 1e-9);

        List<Map<String, List<Object>>> inputRows = objectMapper.readValue(
                commonService.convertInputExcelDataToJson(inputStatsWorkbook()),
                new TypeReference<>() {
                });
        assertEquals(List.of(10.0, 20.0, true), inputRows.get(0).get("revenueGrowth"));
    }

    private static MultipartFile jsonFile(String json) {
        return new MockMultipartFile("file", "data.json", "application/json", json.getBytes());
    }

    private static MultipartFile countryWorkbook() throws IOException {
        try (Workbook workbook = new XSSFWorkbook(); ByteArrayOutputStream outputStream = new ByteArrayOutputStream()) {
            for (int i = 0; i < 12; i++) {
                workbook.createSheet("Sheet" + i);
            }
            Sheet sheet = workbook.getSheetAt(11);
            Row header = sheet.createRow(3);
            header.createCell(0).setCellValue("Country");
            header.createCell(1).setCellValue("Moodys Rating");
            header.createCell(2).setCellValue("Adjusted Default Spread");
            header.createCell(3).setCellValue("Equity Risk Premium");
            header.createCell(4).setCellValue("Country Risk Premium");
            header.createCell(5).setCellValue("Corporate Tax Rate");
            header.createCell(6).setCellValue("GDP In Millions");

            Row data = sheet.createRow(4);
            data.createCell(0).setCellValue("Sweden");
            data.createCell(1).setCellValue("AAA");
            data.createCell(2).setCellValue(1.5);
            CellStyle percentStyle = workbook.createCellStyle();
            DataFormat dataFormat = workbook.createDataFormat();
            percentStyle.setDataFormat(dataFormat.getFormat("0.00%"));
            data.createCell(3).setCellValue(0.12);
            data.getCell(3).setCellStyle(percentStyle);
            data.createCell(4).setCellValue(2.0);
            data.createCell(5).setCellValue(21.0);
            data.createCell(6).setCellValue(500.0);

            workbook.write(outputStream);
            return new MockMultipartFile("file", "country.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    outputStream.toByteArray());
        }
    }

    private static MultipartFile singleObjectWorkbook() throws IOException {
        try (Workbook workbook = new XSSFWorkbook(); ByteArrayOutputStream outputStream = new ByteArrayOutputStream()) {
            Sheet sheet = workbook.createSheet("Sheet0");
            Row row0 = sheet.createRow(0);
            row0.createCell(0).setCellValue("Company Name");
            row0.createCell(1).setCellValue("Example Corp");

            Row row1 = sheet.createRow(1);
            row1.createCell(0).setCellValue("Revenue Growth");
            row1.createCell(1).setCellValue(12.5);

            Row row2 = sheet.createRow(2);
            row2.createCell(0).setCellValue("Valuation Date");
            row2.createCell(1).setCellValue(java.sql.Date.valueOf(LocalDate.of(2026, 3, 10)));
            CellStyle dateStyle = workbook.createCellStyle();
            dateStyle.setDataFormat(workbook.createDataFormat().getFormat("mm/dd/yyyy"));
            row2.getCell(1).setCellStyle(dateStyle);

            Row row3 = sheet.createRow(3);
            row3.createCell(0).setCellValue("If you don't understand this");
            row3.createCell(1).setCellValue("skip me");

            workbook.write(outputStream);
            return new MockMultipartFile("file", "single.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    outputStream.toByteArray());
        }
    }

    private static MultipartFile industryAverageWorkbook() throws IOException {
        try (Workbook workbook = new XSSFWorkbook(); ByteArrayOutputStream outputStream = new ByteArrayOutputStream()) {
            Sheet sheet = workbook.createSheet("Sheet0");
            Row header = sheet.createRow(0);
            header.createCell(0).setCellValue("Industry Name");
            header.createCell(1).setCellValue("Pre Tax Operating Margin");

            Row data = sheet.createRow(1);
            data.createCell(0).setCellValue("Software");
            CellStyle percentStyle = workbook.createCellStyle();
            percentStyle.setDataFormat(workbook.createDataFormat().getFormat("0.00%"));
            data.createCell(1).setCellValue(0.25);
            data.getCell(1).setCellStyle(percentStyle);

            workbook.write(outputStream);
            return new MockMultipartFile("file", "industry.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    outputStream.toByteArray());
        }
    }

    private static MultipartFile countryEquityWorkbook() throws IOException {
        try (Workbook workbook = new XSSFWorkbook(); ByteArrayOutputStream outputStream = new ByteArrayOutputStream()) {
            for (int i = 0; i < 12; i++) {
                workbook.createSheet("Sheet" + i);
            }
            Sheet sheet = workbook.getSheetAt(11);
            Row header = sheet.createRow(0);
            header.createCell(0).setCellValue("Country");
            header.createCell(1).setCellValue("Country Risk Premium");

            Row data = sheet.createRow(1);
            data.createCell(0).setCellValue("Sweden");
            CellStyle percentStyle = workbook.createCellStyle();
            percentStyle.setDataFormat(workbook.createDataFormat().getFormat("0.00%"));
            data.createCell(1).setCellValue(0.05);
            data.getCell(1).setCellStyle(percentStyle);

            workbook.write(outputStream);
            return new MockMultipartFile("file", "country-equity.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    outputStream.toByteArray());
        }
    }

    private static MultipartFile inputStatsWorkbook() throws IOException {
        try (Workbook workbook = new XSSFWorkbook(); ByteArrayOutputStream outputStream = new ByteArrayOutputStream()) {
            Sheet sheet = workbook.createSheet("Sheet0");
            Row row0 = sheet.createRow(0);
            row0.createCell(0).setCellValue("Revenue Growth");
            row0.createCell(1).setCellValue(10.0);
            row0.createCell(2).setCellValue(20.0);
            row0.createCell(3).setCellValue(true);

            Row row1 = sheet.createRow(1);
            row1.createCell(0).setCellValue("Numbers from your base year");
            row1.createCell(1).setCellValue(99.0);

            workbook.write(outputStream);
            return new MockMultipartFile("file", "input-stats.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    outputStream.toByteArray());
        }
    }
}
