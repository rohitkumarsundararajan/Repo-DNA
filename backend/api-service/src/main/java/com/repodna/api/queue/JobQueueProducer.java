package com.repodna.api.queue;

import com.repodna.api.job.Job;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import tools.jackson.databind.ObjectMapper;

import java.util.UUID;

/**
 * Pushes job messages to the Redis list that the analysis worker reads.
 * The push happens only after the job row is committed, so the worker never sees a job
 * that is not in the database yet. If the push fails, the job is marked FAILED.
 */
@Component
public class JobQueueProducer {

    private static final Logger log = LoggerFactory.getLogger(JobQueueProducer.class);

    private final StringRedisTemplate redis;
    private final ObjectMapper objectMapper;
    private final JdbcTemplate jdbc;
    private final String queueKey;

    public JobQueueProducer(StringRedisTemplate redis,
                            ObjectMapper objectMapper,
                            JdbcTemplate jdbc,
                            @Value("${app.queue.jobs-key:repodna:jobs}") String queueKey) {
        this.redis = redis;
        this.objectMapper = objectMapper;
        this.jdbc = jdbc;
        this.queueKey = queueKey;
    }

    /** Call this right after saving the job. Never throws. */
    public void enqueueAfterCommit(Job job) {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    enqueue(job);
                }
            });
        } else {
            // No surrounding transaction: the save() before this call has already committed.
            enqueue(job);
        }
    }

    private void enqueue(Job job) {
        UUID jobId = job.getId();
        try {
            String json = objectMapper.writeValueAsString(JobMessage.from(job));
            redis.opsForList().leftPush(queueKey, json);
            log.info("Queued job {} on {}", jobId, queueKey);
        } catch (IllegalStateException e) {
            log.error("Job {} has an invalid queue message: {}", jobId, e.getMessage());
            markFailed(jobId, "invalid_job_message: " + e.getMessage());
        } catch (RuntimeException e) {
            log.error("Could not push job {} to Redis", jobId, e);
            markFailed(jobId, "queue_unavailable: could not push job to Redis");
        }
    }

    private void markFailed(UUID jobId, String error) {
        try {
            // status = 'QUEUED' guard: never overwrite a job a worker already picked up.
            jdbc.update("UPDATE jobs SET status = 'FAILED', error = ?, finished_at = now() "
                    + "WHERE id = ? AND status = 'QUEUED'", error, jobId);
        } catch (RuntimeException e) {
            log.error("Could not mark job {} as FAILED", jobId, e);
        }
    }
}