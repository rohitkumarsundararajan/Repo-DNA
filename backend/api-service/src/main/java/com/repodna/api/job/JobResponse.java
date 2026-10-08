package com.repodna.api.job;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.Instant;
import java.util.UUID;

/** What the API shows about a job. The server-side zip_path is deliberately not exposed. */
public record JobResponse(
        @JsonProperty("job_id") UUID jobId,
        @JsonProperty("status") String status,
        @JsonProperty("source_type") String sourceType,
        @JsonProperty("repo_url") String repoUrl,
        @JsonProperty("error") String error,
        @JsonProperty("created_at") Instant createdAt,
        @JsonProperty("finished_at") Instant finishedAt
) {

    public static JobResponse from(Job job) {
        return new JobResponse(
                job.getId(),
                job.getStatus().name(),
                job.getSourceType().value(),
                job.getRepoUrl(),
                job.getError(),
                job.getCreatedAt(),
                job.getFinishedAt());
    }
}