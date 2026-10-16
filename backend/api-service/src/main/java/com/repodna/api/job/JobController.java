package com.repodna.api.job;

import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/jobs")
public class JobController {

    private final JobService jobService;

    public JobController(JobService jobService) {
        this.jobService = jobService;
    }

    /** Submit a repo by URL: JSON body {"repo_url": "https://github.com/owner/repo"}. */
    @PostMapping(consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<JobCreatedResponse> submitUrl(@Valid @RequestBody CreateJobRequest request,
                                                        Authentication authentication) {
        Long userId = jobService.currentUserId(authentication);
        Job job = jobService.createFromUrl(userId, request.repoUrl());
        return ResponseEntity.status(HttpStatus.CREATED).body(new JobCreatedResponse(job.getId()));
    }

    /** Submit a repo as a ZIP: multipart form with a "file" part. */
    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<JobCreatedResponse> submitZip(@RequestParam("file") MultipartFile file,
                                                        Authentication authentication) {
        Long userId = jobService.currentUserId(authentication);
        Job job = jobService.createFromZip(userId, file);
        return ResponseEntity.status(HttpStatus.CREATED).body(new JobCreatedResponse(job.getId()));
    }

    @GetMapping
    public List<JobResponse> list(Authentication authentication) {
        Long userId = jobService.currentUserId(authentication);
        return jobService.listJobs(userId).stream().map(JobResponse::from).toList();
    }

    @GetMapping("/{id}")
    public JobResponse get(@PathVariable UUID id, Authentication authentication) {
        Long userId = jobService.currentUserId(authentication);
        return JobResponse.from(jobService.getOwnedJob(id, userId));
    }

    /** Local 400 handler so this task compiles without touching GlobalExceptionHandler. */
    @ExceptionHandler(InvalidJobRequestException.class)
    public ResponseEntity<Map<String, Object>> handleInvalidJob(InvalidJobRequestException ex) {
        return ResponseEntity.badRequest().body(Map.of(
                "status", 400,
                "error", "Bad Request",
                "message", ex.getMessage()));
    }
}