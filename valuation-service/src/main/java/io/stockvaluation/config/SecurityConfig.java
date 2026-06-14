package io.stockvaluation.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                        .requestMatchers("/public/**").permitAll() // no auth required
                        .requestMatchers("/actuator/health").permitAll()
                        .requestMatchers(HttpMethod.POST, "/api/v1/automated-dcf-analysis/*/valuation").permitAll()
                        .requestMatchers(HttpMethod.POST, "/api/v1/prospectus/extract").permitAll()
                        .requestMatchers(HttpMethod.POST, "/api/v1/prospectus/valuation").permitAll()
                        .requestMatchers(HttpMethod.POST, "/api/v1/segments/propose-mappings").permitAll()
                        .requestMatchers("/api-s/**").permitAll() // internal service-to-service
                        .anyRequest().authenticated()
                );

        return http.build();
    }
}
