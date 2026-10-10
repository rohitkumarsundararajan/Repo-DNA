package com.repodna.api;

import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** Result-serving endpoints: 200 when the job is DONE, 409 when it is not ready. */
class ResultServingApiTest extends ApiTestBase {

    @ParameterizedTest
    @ValueSource(strings = {"result", "graph", "dashboard", "cycles", "violations"})
    void doneJobServesEveryEndpoint(String endpoint) throws Exception {
        String token = registerAndGetToken();
        UUID jobId = createDoneJob(token);

        getAs(token, "/jobs/" + jobId + "/" + endpoint).andExpect(status().isOk());
    }

    @ParameterizedTest
    @ValueSource(strings = {"result", "graph", "dashboard", "cycles", "violations"})
    void notReadyJobGives409(String endpoint) throws Exception {
        String token = registerAndGetToken();
        UUID jobId = createJob(token); // still QUEUED

        getAs(token, "/jobs/" + jobId + "/" + endpoint).andExpect(status().isConflict());
    }

    @Test
    void servedDataMatchesTheFixture() throws Exception {
        String token = registerAndGetToken();
        UUID jobId = createDoneJob(token);

        getAs(token, "/jobs/" + jobId + "/cycles")
                .andExpect(content().string(containsString("src/services/order_service.py")));
        getAs(token, "/jobs/" + jobId + "/violations")
                .andExpect(content().string(containsString("routes-must-not-access-db-directly")));
        getAs(token, "/jobs/" + jobId + "/dashboard")
                .andExpect(content().string(containsString("src/services/order_service.py")));
    }

    @Test
    void anotherUsersResultGives404() throws Exception {
        UUID jobId = createDoneJob(registerAndGetToken());
        String otherToken = registerAndGetToken();

        getAs(otherToken, "/jobs/" + jobId + "/result").andExpect(status().isNotFound());
    }

    @Test
    void noTokenGives401() throws Exception {
        mvc.perform(get("/jobs/" + UUID.randomUUID() + "/result")).andExpect(status().isUnauthorized());
    }

    @Test
    void badUuidGives400() throws Exception {
        String token = registerAndGetToken();
        getAs(token, "/jobs/not-a-uuid/result").andExpect(status().isBadRequest());
    }
}