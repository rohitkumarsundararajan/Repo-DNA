package com.repodna.api.auth;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.Optional;

/**
 * Creates and verifies JWTs (HS256). The signing secret comes only from the
 * JWT_SECRET environment variable (app.security.jwt.secret) and must be at
 * least 32 characters, otherwise the app refuses to start.
 */
@Service
public class JwtService {

    private static final int MIN_SECRET_BYTES = 32; // 256 bits, required by HS256

    private final SecretKey key;
    private final Duration expiry;

    public JwtService(
            @Value("${app.security.jwt.secret}") String secret,
            @Value("${app.security.jwt.expiry-minutes}") long expiryMinutes) {
        byte[] bytes = secret.getBytes(StandardCharsets.UTF_8);
        if (bytes.length < MIN_SECRET_BYTES) {
            throw new IllegalStateException(
                    "JWT_SECRET must be at least 32 characters long for HS256");
        }
        if (expiryMinutes <= 0) {
            throw new IllegalStateException("JWT_EXPIRY_MINUTES must be greater than 0");
        }
        this.key = Keys.hmacShaKeyFor(bytes);
        this.expiry = Duration.ofMinutes(expiryMinutes);
    }

    /** Signs a token whose subject is the user id. */
    public String generateToken(Long userId, String email) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(String.valueOf(userId))
                .claim("email", email)
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(expiry)))
                .signWith(key, Jwts.SIG.HS256)
                .compact();
    }

    /** Returns the user id if the token is valid and not expired, otherwise empty. */
    public Optional<Long> validateAndGetUserId(String token) {
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(key)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
            return Optional.of(Long.parseLong(claims.getSubject()));
        } catch (JwtException | IllegalArgumentException e) {
            // bad signature, expired, malformed, or non-numeric subject
            return Optional.empty();
        }
    }

    public long getExpirySeconds() {
        return expiry.toSeconds();
    }
}