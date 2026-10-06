package com.repodna.api.result;

import com.fasterxml.jackson.annotation.JsonProperty;
import tools.jackson.databind.JsonNode;

import java.util.List;

public record DashboardResponse(JsonNode scores, List<Hotspot> hotspots) {

    public record Hotspot(String path,
                          int loc,
                          int cyclomatic,
                          int cognitive,
                          @JsonProperty("max_nesting") int maxNesting) {
    }
}