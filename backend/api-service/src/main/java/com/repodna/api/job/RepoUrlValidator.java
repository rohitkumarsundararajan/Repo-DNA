package com.repodna.api.job;

import java.util.regex.Pattern;

/**
 * Accepts only https://github.com/<owner>/<repo> or https://gitlab.com/<owner>/<repo>,
 * with an optional .git suffix and an optional trailing slash. Everything else is rejected.
 */
public final class RepoUrlValidator {

    private static final Pattern ALLOWED = Pattern.compile(
            "^https://(github\\.com|gitlab\\.com)/"
                    + "[A-Za-z0-9](?:[A-Za-z0-9._-]*)/"
                    + "[A-Za-z0-9._-]+?(?:\\.git)?/?$");

    private static final int MAX_LENGTH = 300;

    private RepoUrlValidator() {
    }

    public static boolean isValid(String url) {
        return url != null
                && url.length() <= MAX_LENGTH
                && ALLOWED.matcher(url).matches();
    }
}