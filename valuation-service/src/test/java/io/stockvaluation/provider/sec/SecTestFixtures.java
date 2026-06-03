package io.stockvaluation.provider.sec;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.io.InputStream;
import java.util.Map;

final class SecTestFixtures {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private SecTestFixtures() {
    }

    static Map<String, Object> json(String name) {
        try (InputStream stream = SecTestFixtures.class.getResourceAsStream("/sec/" + name)) {
            if (stream == null) {
                throw new IllegalArgumentException("Missing SEC test fixture: " + name);
            }
            return MAPPER.readValue(stream, new TypeReference<>() {
            });
        } catch (IOException e) {
            throw new IllegalStateException("Could not read SEC test fixture: " + name, e);
        }
    }
}
