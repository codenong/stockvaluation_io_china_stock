package io.stockvaluation.provider.sec;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Component
@Getter
@Setter
@ConfigurationProperties(prefix = "provider.sec")
public class SecEdgarProviderProperties {

    private boolean enabled = true;
    private String userAgent = "";
    private String dataBaseUrl = "https://data.sec.gov";
    private String secBaseUrl = "https://www.sec.gov";
    private int requestsPerSecond = 5;
    private long cacheTtlSeconds = 900;

    public boolean hasDeclaredUserAgent() {
        return userAgent != null
                && !userAgent.isBlank()
                && !"CHANGE_ME".equalsIgnoreCase(userAgent.trim());
    }
}
