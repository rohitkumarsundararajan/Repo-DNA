package com.repodna.api.result;

import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import tools.jackson.databind.JsonNode;

import java.util.UUID;

@RestController
@RequestMapping("/jobs/{id}")
public class ResultController {

    private final ResultQueryService resultQueryService;

    public ResultController(ResultQueryService resultQueryService) {
        this.resultQueryService = resultQueryService;
    }

    @GetMapping("/result")
    public JsonNode result(@PathVariable UUID id, Authentication authentication) {
        return resultQueryService.getResult(id, authentication);
    }

    @GetMapping("/graph")
    public JsonNode graph(@PathVariable UUID id, Authentication authentication) {
        return resultQueryService.getGraph(id, authentication);
    }

    @GetMapping("/dashboard")
    public DashboardResponse dashboard(@PathVariable UUID id, Authentication authentication) {
        return resultQueryService.getDashboard(id, authentication);
    }

    @GetMapping("/cycles")
    public JsonNode cycles(@PathVariable UUID id, Authentication authentication) {
        return resultQueryService.getCycles(id, authentication);
    }

    @GetMapping("/violations")
    public JsonNode violations(@PathVariable UUID id, Authentication authentication) {
        return resultQueryService.getViolations(id, authentication);
    }
}