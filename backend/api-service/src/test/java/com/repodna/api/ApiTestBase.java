package com.repodna.api;

import com.jayway.jsonpath.JsonPath;
import com.jayway.jsonpath.PathNotFoundException;
import com.repodna.api.queue.JobQueueProducer;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.testcontainers.postgresql.PostgreSQLContainer;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Shared setup: a real Postgres in Docker (migrations run on it), a mocked Redis queue,
 * and helpers to register users, create jobs and call the worker endpoints.
 */
@SpringBootTest
@AutoConfigureMockMvc
public abstract class ApiTestBase {

    protected static final String INTERNAL_KEY = "test-internal-key-123";
    protected static final String PASSWORD = "password123";
    protected static final String FIXTURE_JOB_ID = "3f9c1a2e-6b3d-4e7a-9c1a-2e6b3d4e7a9c";
    protected static final String REPO_URL = "https://github.com/repodna-demo/mini-flask-shop";

    private static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer("postgres:16-alpine");

    static {
        POSTGRES.start();
    }

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        registry.add("app.security.jwt.secret", () -> "test-jwt-secret-test-jwt-secret-1234567890");
        registry.add("app.security.internal-api-key", () -> INTERNAL_KEY);
    }

    @Autowired
    protected MockMvc mvc;

    // Redis is not needed: the queue producer is replaced by a mock.
    @MockitoBean
    protected JobQueueProducer queueProducer;

    protected static String newEmail() {
        return "user-" + UUID.randomUUID() + "@example.com";
    }

    protected static String credentials(String email, String password) {
        return "{\"email\":\"" + email + "\",\"password\":\"" + password + "\"}";
    }

    protected static String bearer(String token) {
        return "Bearer " + token;
    }

    /** Reads the first JSON path that exists (the response field name may differ slightly). */
    protected static String pick(String json, String... paths) {
        for (String path : paths) {
            try {
                Object value = JsonPath.read(json, path);
                if (value != null) {
                    return value.toString();
                }
            } catch (PathNotFoundException ignored) {
                // try the next one
            }
        }
        throw new AssertionError("None of " + Arrays.toString(paths) + " found in: " + json);
    }

    /** Registers a new user and returns the JWT. */
    protected String registerAndGetToken() throws Exception {
        String body = mvc.perform(post("/auth/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(credentials(newEmail(), PASSWORD)))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        return pick(body, "$.token", "$.accessToken", "$.access_token");
    }

    /** Creates a job from a GitHub URL as this user and returns its id. */
    protected UUID createJob(String token) throws Exception {
        String body = mvc.perform(post("/jobs")
                        .header("Authorization", bearer(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"repo_url\":\"" + REPO_URL + "\"}"))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        return UUID.fromString(pick(body, "$.id", "$.job_id", "$.jobId"));
    }

    protected ResultActions getAs(String token, String path) throws Exception {
        return mvc.perform(get(path).header("Authorization", bearer(token)));
    }

    protected ResultActions internalStatus(UUID jobId, String json, String key) throws Exception {
        var request = post("/internal/jobs/" + jobId + "/status")
                .contentType(MediaType.APPLICATION_JSON)
                .content(json);
        if (key != null) {
            request.header("X-Internal-Key", key);
        }
        return mvc.perform(request);
    }

    protected ResultActions internalResult(UUID jobId, String json, String key) throws Exception {
        var request = post("/internal/jobs/" + jobId + "/result")
                .contentType(MediaType.APPLICATION_JSON)
                .content(json);
        if (key != null) {
            request.header("X-Internal-Key", key);
        }
        return mvc.perform(request);
    }

    /** The shared sample fixture, with its job_id swapped for the real job. */
    protected static String sampleResultFor(UUID jobId) throws IOException {
        String json = Files.readString(Path.of("../../contract/fixtures/sample_result.json"));
        return json.replace(FIXTURE_JOB_ID, jobId.toString());
    }

    /** Creates a job and plays the worker: RUNNING, then the sample result. Job ends up DONE. */
    protected UUID createDoneJob(String token) throws Exception {
        UUID jobId = createJob(token);
        internalStatus(jobId, "{\"status\":\"RUNNING\"}", INTERNAL_KEY).andExpect(status().isNoContent());
        internalResult(jobId, sampleResultFor(jobId), INTERNAL_KEY).andExpect(status().isNoContent());
        return jobId;
    }
}