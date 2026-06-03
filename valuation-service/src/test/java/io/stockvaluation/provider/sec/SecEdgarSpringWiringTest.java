package io.stockvaluation.provider.sec;

import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.web.client.RestTemplate;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.Mockito.mock;

class SecEdgarSpringWiringTest {

    @Test
    void springCanCreateSecEdgarHttpClientWithProductionConstructor() {
        try (AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext()) {
            context.registerBean(RestTemplate.class, () -> mock(RestTemplate.class));
            context.registerBean(SecEdgarProviderProperties.class, SecEdgarProviderProperties::new);
            context.register(SecEdgarHttpClient.class);

            assertDoesNotThrow(context::refresh);
            assertNotNull(context.getBean(SecEdgarHttpClient.class));
        }
    }
}
