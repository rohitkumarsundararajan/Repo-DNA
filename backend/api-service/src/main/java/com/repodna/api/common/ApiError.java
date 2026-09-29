package com.repodna.api.common;

import com.fasterxml.jackson.annotation.JsonInclude;

import java.time.Instant;
import java.util.List;

/**
 * The single JSON shape returned for every error response.
 * {@code fieldErrors} is only present for validation failures (null is omitted).
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record ApiError(
        Instant timestamp,
        int status,
        String error,
        String message,
        String path,
        List<FieldError> fieldErrors
) {

    public record FieldError(String field, String message) {
    }

    public static ApiError of(int status, String error, String message, String path) {
        return new ApiError(Instant.now(), status, error, message, path, null);
    }

    public static ApiError of(int status, String error, String message, String path,
                              List<FieldError> fieldErrors) {
        return new ApiError(Instant.now(), status, error, message, path, fieldErrors);
    }
}