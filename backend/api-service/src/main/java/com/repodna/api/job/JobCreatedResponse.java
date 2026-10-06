package com.repodna.api.job;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.UUID;

public record JobCreatedResponse(
        @JsonProperty("job_id") UUID jobId
) {
}