package com.auto.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 对象存储（RustFS / S3 兼容）配置项，前缀 app.storage。
 */
@Component
@ConfigurationProperties(prefix = "app.storage")
@Getter
@Setter
public class StorageProperties {

    /** S3 兼容服务端点，例如 http://rustfs:9000。 */
    private String endpoint = "http://127.0.0.1:9000";

    /** 区域（RustFS 通常任意值即可）。 */
    private String region = "us-east-1";

    private String accessKey = "rustfsadmin";

    private String secretKey = "rustfsadmin";

    /** 存储桶名称。 */
    private String bucket = "auto-uploads";

    /** 对外访问基础 URL；为空时通过后端 /uploads/** 代理访问。 */
    private String publicBaseUrl = "";

    /** 是否使用 path-style 访问（RustFS/MinIO 需为 true）。 */
    private boolean pathStyleAccess = true;
}
