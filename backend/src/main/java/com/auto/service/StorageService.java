package com.auto.service;

import com.auto.config.StorageProperties;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.core.ResponseInputStream;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.BucketAlreadyExistsException;
import software.amazon.awssdk.services.s3.model.BucketAlreadyOwnedByYouException;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;
import software.amazon.awssdk.services.s3.model.NoSuchKeyException;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.S3Exception;

import java.io.IOException;
import java.net.URI;
import java.util.UUID;

/**
 * 对象存储服务（RustFS / S3 兼容）。封装 AWS SDK v2 S3Client，
 * 提供上传、删除、流式读取，并在启动时确保存储桶存在。
 */
@Service
public class StorageService {

    private static final Logger log = LoggerFactory.getLogger(StorageService.class);

    private final StorageProperties props;
    private S3Client client;

    public StorageService(StorageProperties props) {
        this.props = props;
    }

    @PostConstruct
    void init() {
        this.client = S3Client.builder()
                .endpointOverride(URI.create(props.getEndpoint()))
                .region(Region.of(props.getRegion()))
                .credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create(props.getAccessKey(), props.getSecretKey())))
                .forcePathStyle(props.isPathStyleAccess())
                .build();
        ensureBucket();
    }

    /** 启动时确保 bucket 存在。 */
    private void ensureBucket() {
        try {
            client.headBucket(b -> b.bucket(props.getBucket()));
        } catch (S3Exception e) {
            try {
                client.createBucket(b -> b.bucket(props.getBucket()));
                log.info("已创建对象存储桶: {}", props.getBucket());
            } catch (BucketAlreadyOwnedByYouException | BucketAlreadyExistsException ignored) {
                // 并发或已存在，忽略
            } catch (S3Exception createErr) {
                log.warn("确保存储桶失败（后续上传可能报错）: {}", createErr.getMessage());
            }
        }
    }

    /**
     * 上传文件，对象键为 {@code keyPrefix/<uuid><extension>}。
     *
     * @param keyPrefix 对象键前缀（如 images、audio）
     * @param extension 文件后缀（含点，如 .png）
     * @return 生成的对象键
     */
    public String upload(String keyPrefix, String extension, MultipartFile file) throws IOException {
        String objectKey = keyPrefix + "/" + UUID.randomUUID().toString().replace("-", "") + extension;
        PutObjectRequest.Builder req = PutObjectRequest.builder()
                .bucket(props.getBucket())
                .key(objectKey);
        if (file.getContentType() != null) {
            req.contentType(file.getContentType());
        }
        client.putObject(req.build(), RequestBody.fromInputStream(file.getInputStream(), file.getSize()));
        return objectKey;
    }

    /** 删除对象；对象不存在时静默忽略。 */
    public void delete(String objectKey) {
        if (objectKey == null || objectKey.isBlank()) {
            return;
        }
        try {
            client.deleteObject(b -> b.bucket(props.getBucket()).key(objectKey));
        } catch (S3Exception e) {
            log.warn("删除对象失败 {}: {}", objectKey, e.getMessage());
        }
    }

    /** 流式读取对象；对象不存在返回 null。调用方负责关闭流。 */
    public ResponseInputStream<GetObjectResponse> getStream(String objectKey) {
        try {
            return client.getObject(GetObjectRequest.builder()
                    .bucket(props.getBucket())
                    .key(objectKey)
                    .build());
        } catch (NoSuchKeyException e) {
            return null;
        }
    }
}
