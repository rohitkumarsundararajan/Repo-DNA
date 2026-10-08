package com.repodna.api.user;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

/**
 * Spring generates the implementation at startup. Emails are stored lowercase,
 * so always pass User.normalize(email) when looking one up.
 */
public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByEmail(String email);

    boolean existsByEmail(String email);
}