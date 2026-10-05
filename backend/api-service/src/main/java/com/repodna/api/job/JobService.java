package com.repodna.api.job;

import com.repodna.api.common.ResourceNotFoundException;
import com.repodna.api.user.User;
import com.repodna.api.user.UserRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.UUID;

@Service
public class JobService {

    private static final byte[] ZIP_MAGIC = {0x50, 0x4B, 0x03, 0x04}; // "PK\3\4"

    private final JobRepository jobRepository;
    private final UserRepository userRepository;
    private final Path zipDir;

    public JobService(JobRepository jobRepository,
                      UserRepository userRepository,
                      @Value("${app.storage.zip-dir}") String zipDir) {
        this.jobRepository = jobRepository;
        this.userRepository = userRepository;
        this.zipDir = Path.of(zipDir).toAbsolutePath().normalize();
    }

    /**
     * Finds the id of the logged-in user. The JWT subject is assumed to be the user's email.
     * If your JwtAuthFilter puts something else in the Authentication, change ONLY this method.
     */
    public Long currentUserId(Authentication authentication) {
        String name = authentication.getName();
        if (name != null && !name.isEmpty() && name.chars().allMatch(Character::isDigit)) {
            return Long.valueOf(name);
        }
        String email = User.normalize(name);
        return userRepository.findByEmail(email)
                .map(User::getId)
                .orElseThrow(() -> new ResourceNotFoundException("User not found"));
    }

    public Job createFromUrl(Long userId, String repoUrl) {
        String url = repoUrl == null ? "" : repoUrl.trim();
        if (!RepoUrlValidator.isValid(url)) {
            throw new InvalidJobRequestException(
                    "repo_url must be an https GitHub or GitLab repository URL");
        }

        Job job = new Job();
        job.setId(UUID.randomUUID());
        job.setUserId(userId);
        job.setSourceType(SourceType.GIT);
        job.setRepoUrl(url);
        return jobRepository.save(job);
    }

    public Job createFromZip(Long userId, MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new InvalidJobRequestException("A ZIP file is required");
        }
        String name = file.getOriginalFilename();
        if (name == null || !name.toLowerCase().endsWith(".zip")) {
            throw new InvalidJobRequestException("The uploaded file must be a .zip file");
        }
        if (!looksLikeZip(file)) {
            throw new InvalidJobRequestException("The uploaded file is not a valid ZIP archive");
        }

        UUID jobId = UUID.randomUUID();
        Path target = zipDir.resolve(jobId + ".zip");
        try {
            Files.createDirectories(zipDir);
            try (InputStream in = file.getInputStream()) {
                Files.copy(in, target);
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Could not store the uploaded ZIP", e);
        }

        Job job = new Job();
        job.setId(jobId);
        job.setUserId(userId);
        job.setSourceType(SourceType.ZIP);
        job.setZipPath(target.toString());
        try {
            return jobRepository.save(job);
        } catch (RuntimeException e) {
            // Do not leave an orphan file behind if the row could not be saved.
            try {
                Files.deleteIfExists(target);
            } catch (IOException ignored) {
                // best effort
            }
            throw e;
        }
    }

    public Job getOwnedJob(UUID jobId, Long userId) {
        return jobRepository.findByIdAndUserId(jobId, userId)
                .orElseThrow(() -> new ResourceNotFoundException("Job not found"));
    }

    public List<Job> listJobs(Long userId) {
        return jobRepository.findByUserIdOrderByCreatedAtDesc(userId);
    }

    private boolean looksLikeZip(MultipartFile file) {
        try (InputStream in = file.getInputStream()) {
            byte[] head = in.readNBytes(ZIP_MAGIC.length);
            return java.util.Arrays.equals(head, ZIP_MAGIC);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not read the uploaded file", e);
        }
    }
}