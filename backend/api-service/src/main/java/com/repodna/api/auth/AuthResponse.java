package com.repodna.api.auth;

public record AuthResponse(String token, String tokenType, long expiresInSeconds) {

    public static AuthResponse bearer(String token, long expiresInSeconds) {
        return new AuthResponse(token, "Bearer", expiresInSeconds);
    }
}