package com.repodna.api.common;

/**
 * Throw from any controller or service when something does not exist.
 * GlobalExceptionHandler turns it into a 404 ApiError.
 */
public class ResourceNotFoundException extends RuntimeException {

    public ResourceNotFoundException(String message) {
        super(message);
    }

    public ResourceNotFoundException(String resource, Object id) {
        super(resource + " not found: " + id);
    }
}