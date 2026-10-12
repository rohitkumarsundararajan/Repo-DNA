package com.repodna.api;

import com.repodna.api.job.Job;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;

import static org.hamcrest.Matchers.containsString;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class JobApiTest extends ApiTestBase {

    @Test
    void noTokenGives401() throws Exception {
        mvc.perform(get("/jobs")).andExpect(status().isUnauthorized());
        mvc.perform(post("/jobs").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"repo_url\":\"" + REPO_URL + "\"}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void createJobReturns201AndQueuesIt() throws Exception {
        String token = registerAndGetToken();
        UUID jobId = createJob(token);

        verify(queueProducer).enqueueAfterCommit(any(Job.class));

        getAs(token, "/jobs/" + jobId)
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("QUEUED")));

        getAs(token, "/jobs")
                .andExpect(status().isOk())
                .andExpect(content().string(containsString(jobId.toString())));
    }

    @Test
    void badRepoUrlGives400() throws Exception {
        String token = registerAndGetToken();
        mvc.perform(post("/jobs")
                        .header("Authorization", bearer(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"repo_url\":\"not-a-url\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void anotherUsersJobGives404() throws Exception {
        UUID jobId = createJob(registerAndGetToken());
        String otherToken = registerAndGetToken();

        getAs(otherToken, "/jobs/" + jobId).andExpect(status().isNotFound());
    }
}