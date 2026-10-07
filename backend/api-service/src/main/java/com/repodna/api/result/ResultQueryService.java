package com.repodna.api.result;

import com.repodna.api.common.ResourceNotFoundException;
import com.repodna.api.job.Job;
import com.repodna.api.job.JobService;
import com.repodna.api.job.JobStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Service;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.util.List;
import java.util.UUID;

@Service
public class ResultQueryService {

    private static final int HOTSPOT_LIMIT = 10;

    private final JobService jobService;
    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public ResultQueryService(JobService jobService,
                              JdbcTemplate jdbcTemplate,
                              ObjectMapper objectMapper) {
        this.jobService = jobService;
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    /** Full stored result JSON. */
    public JsonNode getResult(UUID jobId, Authentication authentication) {
        Job job = loadReadyJob(jobId, authentication);
        return readResult(job.getId());
    }

    public JsonNode getGraph(UUID jobId, Authentication authentication) {
        return section(getResult(jobId, authentication), "graph");
    }

    public JsonNode getCycles(UUID jobId, Authentication authentication) {
        return section(getResult(jobId, authentication), "cycles");
    }

    public JsonNode getViolations(UUID jobId, Authentication authentication) {
        JsonNode violations = getResult(jobId, authentication).path("architecture").path("violations");
        return violations.isMissingNode() ? objectMapper.createArrayNode() : violations;
    }

    public DashboardResponse getDashboard(UUID jobId, Authentication authentication) {
        Job job = loadReadyJob(jobId, authentication);
        JsonNode result = readResult(job.getId());

        JsonNode scores = result.path("scores");
        if (scores.isMissingNode()) {
            scores = objectMapper.createObjectNode();
        }

        List<DashboardResponse.Hotspot> hotspots = jdbcTemplate.query(
                "SELECT path, loc, cyclomatic, cognitive, max_nesting "
                        + "FROM file_metrics WHERE job_id = ? "
                        + "ORDER BY cognitive DESC, cyclomatic DESC, path ASC LIMIT ?",
                (rs, rowNum) -> new DashboardResponse.Hotspot(
                        rs.getString("path"),
                        rs.getInt("loc"),
                        rs.getInt("cyclomatic"),
                        rs.getInt("cognitive"),
                        rs.getInt("max_nesting")),
                job.getId(), HOTSPOT_LIMIT);

        return new DashboardResponse(scores, hotspots);
    }

    // ---- helpers ----

    /** Ownership check (404 if not yours) then DONE check (409 if not finished). */
    private Job loadReadyJob(UUID jobId, Authentication authentication) {
        Long userId = jobService.currentUserId(authentication);
        Job job = jobService.getOwnedJob(jobId, userId);
        if (job.getStatus() != JobStatus.DONE) {
            throw new ResultNotReadyException(
                    "Result is not available yet (job status: " + job.getStatus() + ")");
        }
        return job;
    }

    private JsonNode readResult(UUID jobId) {
        List<String> rows = jdbcTemplate.query(
                "SELECT result::text FROM job_results WHERE job_id = ?",
                (rs, rowNum) -> rs.getString(1),
                jobId);
        if (rows.isEmpty()) {
            throw new ResourceNotFoundException("Result not found");
        }
        return objectMapper.readTree(rows.get(0));
    }

    private JsonNode section(JsonNode result, String name) {
        JsonNode node = result.path(name);
        return node.isMissingNode() ? objectMapper.createObjectNode() : node;
    }
}