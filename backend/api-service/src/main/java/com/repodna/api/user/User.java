package com.repodna.api.user;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.Generated;
import org.hibernate.generator.EventType;

import java.time.Instant;
import java.util.Locale;

/**
 * Maps the {@code users} table created by db/migrations/V1__users.sql.
 * Hibernate only validates against the table (ddl-auto: validate); Flyway owns the schema.
 */
@Entity
@Table(name = "users")
@Getter
@Setter
@NoArgsConstructor
public class User {

    // Column is GENERATED ALWAYS AS IDENTITY, so Java must never send an id on insert.
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "email", nullable = false, unique = true)
    private String email;

    // BCrypt hash only, never the plain password. Never expose this in an API response.
    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    // Filled by the DB default now(). Read back after insert instead of being left null.
    @Column(name = "created_at", nullable = false, insertable = false, updatable = false)
    @Generated(event = EventType.INSERT)
    private Instant createdAt;

    public User(String email, String passwordHash) {
        setEmail(email);
        this.passwordHash = passwordHash;
    }

    public void setEmail(String email) {
        this.email = normalize(email);
    }

    /** Lowercase and trim so Rohit@x.com and rohit@x.com cannot become two accounts. */
    public static String normalize(String email) {
        return email == null ? null : email.trim().toLowerCase(Locale.ROOT);
    }

    @PrePersist
    @PreUpdate
    void normalizeBeforeSave() {
        this.email = normalize(this.email);
    }
}