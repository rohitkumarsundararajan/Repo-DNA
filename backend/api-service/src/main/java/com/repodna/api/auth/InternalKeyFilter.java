package com.repodna.api.auth;

import com.repodna.api.common.ApiAuthenticationEntryPoint;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Protects /internal/** with the X-Internal-Key header (the worker has no user login).
 * A valid key gets the INTERNAL role; anything else gets 401.
 */
@Component
public class InternalKeyFilter extends OncePerRequestFilter {

    public static final String HEADER = "X-Internal-Key";

    private final byte[] expectedKey;
    private final ApiAuthenticationEntryPoint entryPoint;

    public InternalKeyFilter(
            @Value("${app.security.internal-api-key}") String internalApiKey,
            ApiAuthenticationEntryPoint entryPoint) {
        this.expectedKey = internalApiKey.getBytes(StandardCharsets.UTF_8);
        this.entryPoint = entryPoint;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith("/internal/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        String provided = request.getHeader(HEADER);
        boolean valid = expectedKey.length > 0
                && provided != null
                && MessageDigest.isEqual(expectedKey, provided.getBytes(StandardCharsets.UTF_8));

        if (!valid) {
            entryPoint.commence(request, response, new BadCredentialsException("Invalid internal key"));
            return;
        }

        SecurityContextHolder.getContext().setAuthentication(
                new UsernamePasswordAuthenticationToken(
                        "worker", null, List.of(new SimpleGrantedAuthority("ROLE_INTERNAL"))));
        chain.doFilter(request, response);
    }
}