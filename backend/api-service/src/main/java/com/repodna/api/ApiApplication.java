package com.repodna.api;

import java.util.TimeZone;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class ApiApplication {

    public static void main(String[] args) {
        // Must run before any DB connection is opened. UTC avoids the
        // "Asia/Calcutta" alias that newer Postgres images reject.
        TimeZone.setDefault(TimeZone.getTimeZone("UTC"));
        SpringApplication.run(ApiApplication.class, args);
    }
}