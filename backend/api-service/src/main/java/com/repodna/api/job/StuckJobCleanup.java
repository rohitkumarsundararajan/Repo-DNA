package com.repodna.api.job;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/** Safety net: fails jobs that stay RUNNING too long (for example, the worker crashed). */
@Slf4j
@Component
@EnableScheduling
public class StuckJobCleanup {

    private final JdbcTemplate jdbc;
    private final int timeoutMinutes;

    public StuckJobCleanup(JdbcTemplate jdbc,
                           @Value("${app.jobs.running-timeout-minutes:10}") int timeoutMinutes) {
        this.jdbc = jdbc;
        this.timeoutMinutes = timeoutMinutes;
    }

    @Scheduled(initialDelay = 60_000, fixedDelay = 60_000)
    public void failStuckJobs() {
        int failed = jdbc.update(
                "UPDATE jobs SET status = 'FAILED', error = 'worker_timeout', finished_at = now() "
                        + "WHERE status = 'RUNNING' "
                        + "AND COALESCE(started_at, created_at) < now() - (? * interval '1 minute')",
                timeoutMinutes);
        if (failed > 0) {
            log.warn("Marked {} stuck job(s) as FAILED (worker_timeout, limit {} min)", failed, timeoutMinutes);
        }
    }
}
