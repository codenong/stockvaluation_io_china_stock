package io.stockvaluation.service;

import io.stockvaluation.domain.CostOfCapital;
import io.stockvaluation.domain.IndustryAveragesGlobal;
import io.stockvaluation.domain.IndustryAveragesUS;
import io.stockvaluation.domain.SectorMapping;
import io.stockvaluation.dto.BasicInfoDataDTO;
import io.stockvaluation.dto.CompanyDataDTO;
import io.stockvaluation.dto.CompanyDriveDataDTO;
import io.stockvaluation.repository.CostOfCapitalRepository;
import io.stockvaluation.repository.IndustryAveragesGlobalRepository;
import io.stockvaluation.repository.IndustryAveragesUSRepository;
import io.stockvaluation.repository.SectorMappingRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CostOfCapitalServiceTest {

    @Mock
    private CostOfCapitalRepository costOfCapitalRepository;

    @Mock
    private IndustryAveragesUSRepository industryAveragesUSRepository;

    @Mock
    private IndustryAveragesGlobalRepository industryAveragesGlobalRepository;

    @Mock
    private CommonService commonService;

    @Mock
    private SectorMappingRepository sectorMappingRepository;

    @InjectMocks
    private CostOfCapitalService service;

    @Test
    void costOfCapitalBasedOnDecileReturnsKnownBucketsAndFallbacks() {
        CostOfCapital value = new CostOfCapital();
        value.setFirstQuartile("7.1");
        value.setFirstDecile("6.4");
        value.setMedian("8.0");
        value.setThirdQuartile("9.1");
        value.setNinthDecile("11.3");
        when(costOfCapitalRepository.findByRegion("US")).thenReturn(Optional.of(value));
        when(costOfCapitalRepository.findByRegion("EMEA")).thenReturn(Optional.empty());

        assertEquals("7.1", service.costOfCapitalBasedOnDecile("US", "First Quartile"));
        assertEquals("6.4", service.costOfCapitalBasedOnDecile("US", "First Decile"));
        assertEquals("8.0", service.costOfCapitalBasedOnDecile("US", "Median"));
        assertEquals("9.1", service.costOfCapitalBasedOnDecile("US", "Third Quartile"));
        assertEquals("11.3", service.costOfCapitalBasedOnDecile("US", "Ninth Decile"));
        assertEquals("Risk Grouping not Found! Please enter a valid Risk grouping",
                service.costOfCapitalBasedOnDecile("US", "Unknown"));
        assertEquals("Region not found", service.costOfCapitalBasedOnDecile("EMEA", "Median"));
    }

    @Test
    void costOfCapitalByIndustryReturnsAdjustedUsAndGlobalValues() {
        CompanyDataDTO companyData = companyData("software", "software-global", 6.0);
        when(commonService.getCompanyDataFromProvider("AAPL")).thenReturn(companyData);
        when(commonService.resolveBaselineRiskFreeRate()).thenReturn(4.0);

        SectorMapping usMapping = new SectorMapping();
        usMapping.setIndustryAsPerExcel("Software US");
        when(sectorMappingRepository.findByIndustryName("software")).thenReturn(usMapping);
        IndustryAveragesUS usAverage = new IndustryAveragesUS();
        usAverage.setCostOfCapital(8.5);
        when(industryAveragesUSRepository.findByIndustryName("Software US")).thenReturn(usAverage);

        SectorMapping globalMapping = new SectorMapping();
        globalMapping.setIndustryAsPerExcel("Software Global");
        when(sectorMappingRepository.findByIndustryName("software-global")).thenReturn(globalMapping);
        IndustryAveragesGlobal globalAverage = new IndustryAveragesGlobal();
        globalAverage.setCostOfCapital(9.25);
        when(industryAveragesGlobalRepository.findByIndustryName("Software Global")).thenReturn(globalAverage);

        assertEquals("10.50", service.costOfCapitalByIndustry("AAPL", "Single Business(US)"));
        assertEquals("11.25", service.costOfCapitalByIndustry("AAPL", "Single Business(Global)"));
    }

    @Test
    void costOfCapitalByIndustryThrowsWhenCompanyDataIsMissing() {
        when(commonService.getCompanyDataFromProvider("AAPL")).thenReturn(null);

        assertThrows(RuntimeException.class, () -> service.costOfCapitalByIndustry("AAPL", "Single Business(US)"));
    }

    @Test
    void privateWeightedCalculationsAndFormattingBehaveAsExpected() throws Exception {
        SectorMapping first = new SectorMapping();
        first.setIndustryAsPerExcel("Excel One");
        SectorMapping second = new SectorMapping();
        second.setIndustryAsPerExcel("Excel Two");
        when(sectorMappingRepository.findByIndustryName("one")).thenReturn(first);
        when(sectorMappingRepository.findByIndustryName("two")).thenReturn(second);

        IndustryAveragesUS firstUs = new IndustryAveragesUS();
        firstUs.setCostOfCapital(8.0);
        IndustryAveragesUS secondUs = new IndustryAveragesUS();
        secondUs.setCostOfCapital(12.0);
        when(industryAveragesUSRepository.findByIndustryName("Excel One")).thenReturn(firstUs);
        when(industryAveragesUSRepository.findByIndustryName("Excel Two")).thenReturn(secondUs);

        IndustryAveragesGlobal firstGlobal = new IndustryAveragesGlobal();
        firstGlobal.setCostOfCapital(7.0);
        IndustryAveragesGlobal secondGlobal = new IndustryAveragesGlobal();
        secondGlobal.setCostOfCapital(11.0);
        when(industryAveragesGlobalRepository.findByIndustryName("Excel One")).thenReturn(firstGlobal);
        when(industryAveragesGlobalRepository.findByIndustryName("Excel Two")).thenReturn(secondGlobal);

        assertEquals(10.8d, invoke("calculateWeightedCostOfCapitalUS",
                new Class[]{List.class, List.class},
                List.of("one", "two"),
                List.of(30.0, 70.0)), 1e-9);

        assertEquals(9.8d, invoke("calculateWeightedCostOfCapitalGlobal",
                new Class[]{List.class, List.class},
                List.of("one", "two"),
                List.of(30.0, 70.0)), 1e-9);

        assertEquals("12.35", invoke("formatIfValid", new Class[]{Number.class}, 12.345d));
        assertEquals("Value not available", invoke("formatIfValid", new Class[]{Number.class}, new Object[]{null}));
        InvocationTargetException exception = assertThrows(InvocationTargetException.class, () -> invoke("calculateWeightedCostOfCapitalUS",
                new Class[]{List.class, List.class},
                List.of("one"),
                List.of(0.0)));
        assertEquals("Total revenue is zero for multi-business calculation", exception.getCause().getMessage());
    }

    private static CompanyDataDTO companyData(String industryUs, String industryGlobal, double riskFreeRate) {
        BasicInfoDataDTO basicInfo = new BasicInfoDataDTO();
        basicInfo.setIndustryUs(industryUs);
        basicInfo.setIndustryGlobal(industryGlobal);

        CompanyDriveDataDTO driveData = new CompanyDriveDataDTO();
        driveData.setRiskFreeRate(riskFreeRate);

        CompanyDataDTO companyData = new CompanyDataDTO();
        companyData.setBasicInfoDataDTO(basicInfo);
        companyData.setCompanyDriveDataDTO(driveData);
        return companyData;
    }

    @SuppressWarnings("unchecked")
    private <T> T invoke(String name, Class<?>[] types, Object... args) throws Exception {
        Method method = CostOfCapitalService.class.getDeclaredMethod(name, types);
        method.setAccessible(true);
        return (T) method.invoke(service, args);
    }
}
