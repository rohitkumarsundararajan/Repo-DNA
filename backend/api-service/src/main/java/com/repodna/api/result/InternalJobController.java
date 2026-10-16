package com.repodna.api.result;

import jakarta.validation.Valid;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Endpoints only the Python worker calls (protected by X-Internal-Key). */
@RestController
@RequestMapping("/internal/jobs")
public class InternalJobController {

    private final ResultIngestionService service;

    public InternalJobController(ResultIngestionService service) {
        this.service = service;
    }

    @PostMapping(value = "/{id}/status", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Void> status(@PathVariable UUID id,
                                       @Valid @RequestBody StatusUpdateRequest request) {
        service.updateStatus(id, request);
        return ResponseEntity.noContent().build();
    }

    // Raw body on purpose: it is validated against the schema and stored exactly as sent.
    @PostMapping(value = "/{id}/result", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Void> result(@PathVariable UUID id, @RequestBody String body) {
        service.ingestResult(id, body);
        return ResponseEntity.noContent().build();
    }

    @ExceptionHandler(InternalRequestException.class)
    public ResponseEntity<Map<String, String>> handle(InternalRequestException e) {
        return ResponseEntity.status(e.getStatus())
                .body(Map.of("error", e.getCode(), "message", e.getMessage()));
    }
}