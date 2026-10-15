package com.repodna.api;

import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;

import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class AuthApiTest extends ApiTestBase {

    @Test
    void registerReturnsTokenAndLoginWorks() throws Exception {
        String email = newEmail();

        mvc.perform(post("/auth/register").contentType(MediaType.APPLICATION_JSON)
                        .content(credentials(email, PASSWORD)))
                .andExpect(status().isCreated())
                .andExpect(content().string(containsString("ey")));

        mvc.perform(post("/auth/login").contentType(MediaType.APPLICATION_JSON)
                        .content(credentials(email, PASSWORD)))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("ey")));
    }

    @Test
    void duplicateEmailIsRejectedWith409() throws Exception {
        String email = newEmail();
        mvc.perform(post("/auth/register").contentType(MediaType.APPLICATION_JSON)
                        .content(credentials(email, PASSWORD)))
                .andExpect(status().isCreated());

        mvc.perform(post("/auth/register").contentType(MediaType.APPLICATION_JSON)
                        .content(credentials(email, PASSWORD)))
                .andExpect(status().isConflict());
    }

    @Test
    void wrongPasswordGives401() throws Exception {
        String email = newEmail();
        mvc.perform(post("/auth/register").contentType(MediaType.APPLICATION_JSON)
                        .content(credentials(email, PASSWORD)))
                .andExpect(status().isCreated());

        mvc.perform(post("/auth/login").contentType(MediaType.APPLICATION_JSON)
                        .content(credentials(email, "wrong-password-1")))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void shortPasswordGives400() throws Exception {
        mvc.perform(post("/auth/register").contentType(MediaType.APPLICATION_JSON)
                        .content(credentials(newEmail(), "short")))
                .andExpect(status().isBadRequest());
    }
}