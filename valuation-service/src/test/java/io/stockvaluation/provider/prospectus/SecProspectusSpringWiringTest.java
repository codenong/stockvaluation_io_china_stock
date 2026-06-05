package io.stockvaluation.provider.prospectus;

import io.stockvaluation.provider.sec.SecEdgarProviderProperties;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.web.client.RestTemplate;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.Mockito.mock;

class SecProspectusSpringWiringTest {

    @Test
    void springCanCreateSecProspectusDocumentClientWithProductionConstructor() {
        try (AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext()) {
            context.registerBean(RestTemplate.class, () -> mock(RestTemplate.class));
            context.registerBean(SecEdgarProviderProperties.class, SecEdgarProviderProperties::new);
            context.register(SecProspectusDocumentClient.class);

            assertDoesNotThrow(context::refresh);
            assertNotNull(context.getBean(SecProspectusDocumentClient.class));
        }
    }
}
