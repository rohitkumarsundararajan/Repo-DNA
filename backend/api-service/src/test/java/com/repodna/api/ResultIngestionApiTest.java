package com.repodna.api;

import java.util.UUID;
import org.junit.jupiter.api.Test;

import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** The worker side: status updates and result ingestion, using the shared sample fixture. */
class ResultIngestionApiTest extends ApiTestBase {

    @Test
    void internalEndpointsNeedTheInternalKey() throws Exception {
        UUID jobId = createJob(registerAndGetToken());

        internalStatus(jobId, "{\"status\":\"RUNNING\"}", null).andExpect(status().isUnauthorized());
        internalStatus(jobId, "{\"status\":\"RUNNING\"}", "wrong-key").andExpect(status().isUnauthorized());
    }

    @Test
    void userTokenCannotCallInternalEndpoints() throws Exception {
        String token = registerAndGetToken();
        UUID jobId = createJob(token);

        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders
                        .post("/internal/jobs/" + jobId + "/status")
                        .header("Authorization", bearer(token))
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content("{\"status\":\"RUNNING\"}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void unknownJobGives404() throws Exception {
        internalStatus(UUID.randomUUID(), "{\"status\":\"RUNNING\"}", INTERNAL_KEY)
                .andExpect(status().isNotFound());
    }

    @Test
    void badStatusValueGives400() throws Exception {
        UUID jobId = createJob(registerAndGetToken());
        internalStatus(jobId, "{\"status\":\"DONE\"}", INTERNAL_KEY).andExpect(status().isBadRequest());
    }

    @Test
    void sampleFixtureIsIngestedAndJobBecomesDone() throws Exception {
        String token = registerAndGetToken();
        UUID jobId = createJob(token);

        internalStatus(jobId, "{\"status\":\"RUNNING\"}", INTERNAL_KEY).andExpect(status().isNoContent());
        getAs(token, "/jobs/" + jobId).andExpect(content().string(containsString("RUNNING")));

        internalResult(jobId, sampleResultFor(jobId), INTERNAL_KEY).andExpect(status().isNoContent());
        getAs(token, "/jobs/" + jobId).andExpect(content().string(containsString("DONE")));

        // sending the same result again is rejected
        internalResult(jobId, sampleResultFor(jobId), INTERNAL_KEY).andExpect(status().isConflict());
    }

    @Test
    void invalidResultGives400AndJobFails() throws Exception {
        String token = registerAndGetToken();
        UUID jobId = createJob(token);
        internalStatus(jobId, "{\"status\":\"RUNNING\"}", INTERNAL_KEY).andExpect(status().isNoContent());

        internalResult(jobId, "{\"job_id\":\"" + jobId + "\"}", INTERNAL_KEY)
                .andExpect(status().isBadRequest());

        getAs(token, "/jobs/" + jobId).andExpect(content().string(containsString("FAILED")));
    }
}