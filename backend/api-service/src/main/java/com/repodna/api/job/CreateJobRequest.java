package com.repodna.api.job;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;

public record CreateJobRequest(
        @JsonProperty("repo_url") @NotBlank(message = "repo_url is required") String repoUrl
) {
}