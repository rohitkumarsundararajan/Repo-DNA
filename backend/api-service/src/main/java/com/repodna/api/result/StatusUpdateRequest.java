package com.repodna.api.result;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

public record StatusUpdateRequest(
        @NotBlank @Pattern(regexp = "RUNNING|FAILED", message = "status must be RUNNING or FAILED")
        String status,
        String error) {
}