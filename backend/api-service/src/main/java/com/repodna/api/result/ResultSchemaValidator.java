package com.repodna.api.result;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.networknt.schema.JsonSchema;
import com.networknt.schema.JsonSchemaFactory;
import com.networknt.schema.SpecVersion;
import com.networknt.schema.ValidationMessage;
import java.io.IOException;
import java.io.InputStream;
import java.util.List;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

/** Checks a worker result against contract/result.schema.json (copied into resources/contract). */
@Component
public class ResultSchemaValidator {

    public record Outcome(JsonNode root, List<String> errors) {
    }

    private final ObjectMapper mapper = new ObjectMapper();
    private final JsonSchema schema;

    public ResultSchemaValidator() {
        try (InputStream in = new ClassPathResource("contract/result.schema.json").getInputStream()) {
            this.schema = JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V7).getSchema(in);
        } catch (IOException e) {
            throw new IllegalStateException("Cannot load contract/result.schema.json from classpath", e);
        }
    }

    public Outcome validate(String body) {
        JsonNode root;
        try {
            root = mapper.readTree(body);
        } catch (JsonProcessingException e) {
            return new Outcome(null, List.of("body is not valid JSON"));
        }
        if (root == null || !root.isObject()) {
            return new Outcome(null, List.of("body must be a JSON object"));
        }
        List<String> errors = schema.validate(root).stream()
                .map(ValidationMessage::getMessage)
                .sorted()
                .toList();
        return new Outcome(root, errors);
    }
}