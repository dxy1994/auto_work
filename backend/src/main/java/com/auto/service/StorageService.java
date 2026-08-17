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
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;
import software.amazon.awssdk.services.s3.model.HeadObjectResponse;
import software.amazon.awssdk.services.s3.model.ListObjectsV2Request;
import software.amazon.awssdk.services.s3.model.NoSuchKeyException;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.S3Exception;

import java.io.IOException;
import java.net.URI;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
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
        uploadObject(objectKey, file, Map.of());
        return objectKey;
    }

    /**
     * 使用指定对象键上传文件，并保存供业务列表使用的自定义元数据。
     */
    public void uploadObject(String objectKey, MultipartFile file, Map<String, String> metadata) throws IOException {
        PutObjectRequest.Builder req = PutObjectRequest.builder()
                .bucket(props.getBucket())
                .key(objectKey)
                .metadata(metadata != null ? metadata : Map.of());
        if (file.getContentType() != null && !file.getContentType().isBlank()) {
            req.contentType(file.getContentType());
        }
        client.putObject(req.build(), RequestBody.fromInputStream(file.getInputStream(), file.getSize()));
    }

    /**
     * 列出指定前缀下的对象。对象元数据由 HEAD 请求补齐，适合数量较少的安装包目录。
     */
    public List<StoredObject> list(String keyPrefix) {
        List<StoredObject> result = new ArrayList<>();
        ListObjectsV2Request request = ListObjectsV2Request.builder()
                .bucket(props.getBucket())
                .prefix(keyPrefix)
                .build();
        client.listObjectsV2Paginator(request).contents().forEach(object -> {
            StoredObject info = getInfo(object.key());
            if (info != null) {
                result.add(new StoredObject(
                        info.key(),
                        object.size() != null ? object.size() : info.size(),
                        object.lastModified() != null ? object.lastModified() : info.lastModified(),
                        info.contentType(),
                        info.metadata()));
            }
        });
        return result;
    }

    /** 读取单个对象的元数据；对象不存在返回 null。 */
    public StoredObject getInfo(String objectKey) {
        try {
            HeadObjectResponse response = client.headObject(HeadObjectRequest.builder()
                    .bucket(props.getBucket())
                    .key(objectKey)
                    .build());
            return new StoredObject(
                    objectKey,
                    response.contentLength() != null ? response.contentLength() : 0L,
                    response.lastModified(),
                    response.contentType(),
                    response.metadata());
        } catch (NoSuchKeyException e) {
            return null;
        } catch (S3Exception e) {
            if (e.statusCode() == 404) {
                return null;
            }
            throw e;
        }
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
        } catch (S3Exception e) {
            if (e.statusCode() == 404) {
                return null;
            }
            throw e;
        }
    }

    public record StoredObject(
            String key,
            long size,
            Instant lastModified,
            String contentType,
            Map<String, String> metadata) {
    }
}
