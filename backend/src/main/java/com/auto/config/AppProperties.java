package com.auto.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 应用自定义配置项（对应原 Python config.Settings 与环境变量）。
 */
@Component
@ConfigurationProperties(prefix = "app")
@Getter
@Setter
public class AppProperties {

    /** AES 加密密钥（32 字节）。 */
    private String secretKey = "your-32-byte-secret-key-change-this!";

    /** CORS 允许来源，逗号分隔。 */
    private String corsOrigins = "http://localhost:5173,http://127.0.0.1:5173,http://192.168.1.24:5173";

    public String[] corsOriginArray() {
        return corsOrigins.split(",");
    }
}
