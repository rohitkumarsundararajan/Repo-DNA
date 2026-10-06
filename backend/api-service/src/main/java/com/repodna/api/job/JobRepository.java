package com.repodna.api.job;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface JobRepository extends JpaRepository<Job, UUID> {

    List<Job> findByUserIdOrderByCreatedAtDesc(Long userId);

    /** Ownership check built into the query: another user's job is simply "not found". */
    Optional<Job> findByIdAndUserId(UUID id, Long userId);
}