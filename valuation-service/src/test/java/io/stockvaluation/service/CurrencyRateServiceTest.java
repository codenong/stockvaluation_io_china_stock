package io.stockvaluation.service;

import io.stockvaluation.config.CurrencyApiProperties;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CurrencyRateServiceTest {

    @Mock
    private RestTemplate restTemplate;

    @Mock
    private CurrencyApiProperties currencyApiProperties;

    @Test
    void fetchExchangeRatesSkipsWhenApiKeyIsMissing() {
        when(currencyApiProperties.getKey()).thenReturn(" ");

        CurrencyRateService service = new CurrencyRateService(restTemplate, currencyApiProperties);
        service.fetchExchangeRates();

        assertFalse(service.isReady());
    }

    @Test
    void initLoadsRatesAndConvertCurrencyUsesUsdBase() {
        when(currencyApiProperties.getKey()).thenReturn("secret");
        when(currencyApiProperties.getBaseUrl()).thenReturn("https://api.example.com/latest");
        when(restTemplate.getForEntity(eq("https://api.example.com/latest?apikey=secret"), eq(Map.class)))
                .thenReturn(ResponseEntity.ok(Map.of("data", Map.of("USD", 1.0, "SEK", 10.0, "EUR", 0.9))));

        CurrencyRateService service = new CurrencyRateService(restTemplate, currencyApiProperties);
        service.init();

        assertTrue(service.isReady());
        assertEquals(100.0, service.convertCurrency("USD", "SEK", 10.0), 1e-9);
        assertEquals(10.0, service.convertCurrency("SEK", "SEK", 10.0), 1e-9);
    }

    @Test
    void fetchExchangeRatesIgnoresUnexpectedPayloads() {
        when(currencyApiProperties.getKey()).thenReturn("secret");
        when(currencyApiProperties.getBaseUrl()).thenReturn("https://api.example.com/latest");
        when(restTemplate.getForEntity(anyString(), eq(Map.class)))
                .thenReturn(ResponseEntity.ok(Map.of("data", Map.of("USD", "invalid"))));

        CurrencyRateService service = new CurrencyRateService(restTemplate, currencyApiProperties);
        service.fetchExchangeRates();

        assertFalse(service.isReady());
    }

    @Test
    void convertCurrencyThrowsWhenEitherRateIsMissing() {
        when(currencyApiProperties.getKey()).thenReturn("secret");
        when(currencyApiProperties.getBaseUrl()).thenReturn("https://api.example.com/latest");
        when(restTemplate.getForEntity(anyString(), eq(Map.class)))
                .thenReturn(ResponseEntity.ok(Map.of("data", Map.of("USD", 1.0))));

        CurrencyRateService service = new CurrencyRateService(restTemplate, currencyApiProperties);
        service.fetchExchangeRates();

        assertThrows(IllegalArgumentException.class, () -> service.convertCurrency("USD", "SEK", 10.0));
    }
}
