package com.repodna.api.auth;

/** Thrown when registering an email that already exists. Should map to HTTP 409. */
public class EmailAlreadyExistsException extends RuntimeException {

    public EmailAlreadyExistsException() {
        super("An account with this email already exists");
    }
}