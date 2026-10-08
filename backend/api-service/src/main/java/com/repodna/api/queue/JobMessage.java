package com.repodna.api.queue;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.repodna.api.job.Job;
import com.repodna.api.job.SourceType;

/**
 * The message pushed to Redis. Must match contract/job_message.schema.json.
 * Exactly one of repoUrl / zipPath is set, the other is null (and still written as null).
 */
@JsonInclude(JsonInclude.Include.ALWAYS)
public record JobMessage(
        @JsonProperty("job_id") String jobId,
        @JsonProperty("source_type") String sourceType,
        @JsonProperty("repo_url") String repoUrl,
        @JsonProperty("zip_path") String zipPath) {

    private static final String UUID_PATTERN =
            "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$";

    public static JobMessage from(Job job) {
        boolean zip = job.getSourceType() == SourceType.ZIP;
        JobMessage message = new JobMessage(
                job.getId().toString(),
                zip ? "zip" : "git",
                zip ? null : job.getRepoUrl(),
                zip ? job.getZipPath() : null);
        message.validate();
        return message;
    }

    /** Same rules as the JSON schema, checked in plain Java. */
    public void validate() {
        if (jobId == null || !jobId.matches(UUID_PATTERN)) {
            throw new IllegalStateException("job_id is not a valid UUID");
        }
        if ("git".equals(sourceType)) {
            if (repoUrl == null || !repoUrl.startsWith("https://")) {
                throw new IllegalStateException("repo_url must be an https URL for source_type git");
            }
            if (zipPath != null) {
                throw new IllegalStateException("zip_path must be null for source_type git");
            }
        } else if ("zip".equals(sourceType)) {
            if (zipPath == null || zipPath.isBlank()) {
                throw new IllegalStateException("zip_path is required for source_type zip");
            }
            if (repoUrl != null) {
                throw new IllegalStateException("repo_url must be null for source_type zip");
            }
        } else {
            throw new IllegalStateException("source_type must be git or zip");
        }
    }
}