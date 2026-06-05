package io.stockvaluation.provider.prospectus;

import io.stockvaluation.provider.sec.SecEdgarProviderProperties;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.zip.GZIPOutputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class SecProspectusDocumentClientTest {

    @Test
    void decodesGzippedSecHtmlBeforeReturningDocument() throws Exception {
        RestTemplate restTemplate = new RestTemplate();
        MockRestServiceServer server = MockRestServiceServer.bindTo(restTemplate).build();
        String url = "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm";
        String html = "<DOCUMENT><TYPE>S-1/A<TEXT><html><body>Revenue</body></html></TEXT></DOCUMENT>";
        server.expect(requestTo(url))
                .andExpect(header("User-Agent", "StockValuation.io Dev contact@example.com"))
                .andRespond(withSuccess(gzip(html), MediaType.TEXT_HTML)
                        .header(HttpHeaders.CONTENT_ENCODING, "gzip"));
        SecProspectusDocumentClient client = new SecProspectusDocumentClient(restTemplate, configuredProperties());

        ProspectusDocument document = client.fetch(url);

        assertEquals(url, document.sourceUrl());
        assertEquals(html, document.html());
        server.verify();
    }

    private static SecEdgarProviderProperties configuredProperties() {
        SecEdgarProviderProperties properties = new SecEdgarProviderProperties();
        properties.setEnabled(true);
        properties.setUserAgent("StockValuation.io Dev contact@example.com");
        properties.setCacheTtlSeconds(60);
        return properties;
    }

    private static byte[] gzip(String value) throws Exception {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        try (GZIPOutputStream gzip = new GZIPOutputStream(output)) {
            gzip.write(value.getBytes(StandardCharsets.UTF_8));
        }
        return output.toByteArray();
    }
}
