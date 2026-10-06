package com.repodna.api.job;

/** Thrown when the submitted repo URL or ZIP is not acceptable. Mapped to HTTP 400. */
public class InvalidJobRequestException extends RuntimeException {

    public InvalidJobRequestException(String message) {
        super(message);
    }
}