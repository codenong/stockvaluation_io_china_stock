package io.stockvaluation.provider.field;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

public record FinancialFieldDefinitionCatalog(
        List<FinancialFieldDefinition> definitions,
        Map<String, FinancialFieldDefinition> byFieldName) {

    private static final String DEFAULT_RESOURCE = "/data/financial_field_definitions.json";

    public FinancialFieldDefinitionCatalog(List<FinancialFieldDefinition> definitions) {
        this(List.copyOf(definitions), definitions.stream()
                .collect(Collectors.toUnmodifiableMap(
                        FinancialFieldDefinition::fieldName,
                        Function.identity())));
    }

    public static FinancialFieldDefinitionCatalog loadDefault() {
        try (InputStream stream = FinancialFieldDefinitionCatalog.class.getResourceAsStream(DEFAULT_RESOURCE)) {
            if (stream == null) {
                throw new IllegalStateException("Missing canonical financial field definition resource: " + DEFAULT_RESOURCE);
            }
            ObjectMapper mapper = new ObjectMapper().registerModule(new JavaTimeModule());
            Resource resource = mapper.readValue(stream, Resource.class);
            return new FinancialFieldDefinitionCatalog(resource.fields());
        } catch (IOException e) {
            throw new IllegalStateException("Could not load canonical financial field definitions.", e);
        }
    }

    public boolean hasField(String fieldName) {
        return byFieldName.containsKey(fieldName);
    }

    public FinancialFieldDefinition definition(String fieldName) {
        FinancialFieldDefinition definition = byFieldName.get(fieldName);
        if (definition == null) {
            throw new IllegalArgumentException("Unknown financial field definition: " + fieldName);
        }
        return definition;
    }

    public List<String> secConcepts(String fieldName) {
        return definition(fieldName).secPreferredConcepts();
    }

    public List<String> yahooKeys(String fieldName) {
        return definition(fieldName).yahooAcceptedKeys();
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    private record Resource(List<FinancialFieldDefinition> fields) {
    }
}
