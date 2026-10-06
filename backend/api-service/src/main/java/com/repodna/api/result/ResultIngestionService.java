package com.repodna.api.result;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class ResultIngestionService {

    private static final int BATCH_SIZE = 500;

    private final JdbcTemplate jdbc;
    private final TransactionTemplate tx;
    private final ResultSchemaValidator validator;

    public ResultIngestionService(JdbcTemplate jdbc,
                                  PlatformTransactionManager transactionManager,
                                  ResultSchemaValidator validator) {
        this.jdbc = jdbc;
        this.tx = new TransactionTemplate(transactionManager);
        this.validator = validator;
    }

    // ---------- status callback ----------

    public void updateStatus(UUID jobId, StatusUpdateRequest request) {
        requireOpenJob(jobId);

        int updated;
        if ("RUNNING".equals(request.status())) {
            updated = jdbc.update(
                    "UPDATE jobs SET status = 'RUNNING' WHERE id = ? AND status IN ('QUEUED', 'RUNNING')",
                    jobId);
        } else if ("FAILED".equals(request.status())) {
            String error = (request.error() == null || request.error().isBlank())
                    ? "worker_failed" : request.error();
            updated = jdbc.update(
                    "UPDATE jobs SET status = 'FAILED', error = ?, finished_at = now() "
                            + "WHERE id = ? AND status IN ('QUEUED', 'RUNNING')",
                    error, jobId);
        } else {
            throw new InternalRequestException(HttpStatus.BAD_REQUEST, "invalid_status",
                    "status must be RUNNING or FAILED");
        }

        if (updated == 0) {
            throw alreadyFinished();
        }
    }

    // ---------- result callback ----------

    public void ingestResult(UUID jobId, String body) {
        requireOpenJob(jobId);

        ResultSchemaValidator.Outcome outcome = validator.validate(body);
        List<String> errors = new ArrayList<>(outcome.errors());
        JsonNode root = outcome.root();

        if (root != null && errors.isEmpty()) {
            Set<String> seen = new HashSet<>();
            for (JsonNode f : root.path("files")) {
                if (!seen.add(f.path("path").asText())) {
                    errors.add("duplicate file path: " + f.path("path").asText());
                    break;
                }
            }
        }

        if (!errors.isEmpty()) {
            markInvalid(jobId);
            String detail = errors.stream().limit(5).collect(Collectors.joining("; "));
            throw new InternalRequestException(HttpStatus.BAD_REQUEST, "invalid_result", detail);
        }

        if (!jobId.toString().equalsIgnoreCase(root.path("job_id").asText())) {
            throw new InternalRequestException(HttpStatus.BAD_REQUEST, "job_id_mismatch",
                    "job_id in the body does not match the job in the URL");
        }

        // One transaction: everything is saved, or nothing is.
        tx.executeWithoutResult(status -> save(jobId, body, root));
    }

    private void save(UUID jobId, String body, JsonNode root) {
        // Row lock + guard first: a second result for the same job gets 409.
        int updated = jdbc.update(
                "UPDATE jobs SET status = 'DONE', error = NULL, finished_at = now() "
                        + "WHERE id = ? AND status <> 'DONE'",
                jobId);
        if (updated == 0) {
            throw alreadyFinished();
        }

        jdbc.update(
                "INSERT INTO job_results (job_id, schema_version, result) VALUES (?, ?, ?::jsonb)",
                jobId, root.path("schema_version").asText(), body);

        List<JsonNode> files = new ArrayList<>();
        root.path("files").forEach(files::add);
        jdbc.batchUpdate(
                "INSERT INTO file_metrics (job_id, path, loc, cyclomatic, cognitive, max_nesting) "
                        + "VALUES (?, ?, ?, ?, ?, ?)",
                files, BATCH_SIZE,
                (ps, f) -> {
                    ps.setObject(1, jobId);
                    ps.setString(2, f.path("path").asText());
                    ps.setInt(3, f.path("loc").asInt());
                    ps.setInt(4, f.path("cyclomatic").asInt());
                    ps.setInt(5, f.path("cognitive").asInt());
                    ps.setInt(6, f.path("max_nesting").asInt());
                });

        // One row per job, so a plain insert (a batch of one adds nothing).
        JsonNode scores = root.path("scores");
        jdbc.update(
                "INSERT INTO dna_scores (job_id, architecture, code, quality) VALUES (?, ?, ?, ?)",
                jobId,
                scores.path("architecture_dna").decimalValue(),
                scores.path("code_dna").decimalValue(),
                scores.path("quality_dna").decimalValue());
    }

    // ---------- helpers ----------

    /** 404 if the job does not exist, 409 if it is already DONE. */
    private void requireOpenJob(UUID jobId) {
        List<String> found = jdbc.query("SELECT status FROM jobs WHERE id = ?",
                (rs, i) -> rs.getString(1), jobId);
        if (found.isEmpty()) {
            throw new InternalRequestException(HttpStatus.NOT_FOUND, "job_not_found", "Job not found");
        }
        if ("DONE".equals(found.get(0))) {
            throw alreadyFinished();
        }
    }

    private void markInvalid(UUID jobId) {
        jdbc.update(
                "UPDATE jobs SET status = 'FAILED', error = 'invalid_result', finished_at = now() "
                        + "WHERE id = ? AND status IN ('QUEUED', 'RUNNING')",
                jobId);
    }

    private InternalRequestException alreadyFinished() {
        return new InternalRequestException(HttpStatus.CONFLICT, "job_already_finished",
                "Job is already finished");
    }
}