package com.auto.service;

import com.auto.common.ApiException;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import software.amazon.awssdk.core.ResponseInputStream;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.Base64;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 内网软件分发服务。安装包本体及展示元数据均保存在对象存储中，
 * 无需额外数据库表，也不会因应用重启丢失。
 */
@Service
public class SoftwarePackageService {

    private static final String KEY_PREFIX = "software-packages/";
    private static final Set<String> ALLOWED_SUFFIXES = Set.of(
            ".exe", ".msi", ".msix", ".zip", ".7z", ".rar", ".tar", ".tar.gz", ".tgz");
    private static final int MAX_FILE_NAME_LENGTH = 180;
    private static final int MAX_VERSION_LENGTH = 60;
    private static final int MAX_NOTES_LENGTH = 500;

    private final StorageService storageService;

    public SoftwarePackageService(StorageService storageService) {
        this.storageService = storageService;
    }

    public List<PackageInfo> list() {
        return storageService.list(KEY_PREFIX).stream()
                .map(this::toPackageInfo)
                .sorted(Comparator.comparing(
                        PackageInfo::uploadedAt,
                        Comparator.nullsLast(Comparator.reverseOrder())))
                .toList();
    }

    public PackageInfo upload(MultipartFile file, String version, String notes) throws IOException {
        if (file == null || file.isEmpty()) {
            throw ApiException.badRequest("请选择要发布的安装包");
        }
        String fileName = cleanFileName(file.getOriginalFilename());
        validateFileName(fileName);
        String cleanVersion = normalize(version, MAX_VERSION_LENGTH, "版本号");
        String cleanNotes = normalize(notes, MAX_NOTES_LENGTH, "版本说明");
        String id = UUID.randomUUID().toString();
        String sha256 = sha256(file);

        Map<String, String> metadata = Map.of(
                "filename-b64", encode(fileName),
                "version-b64", encode(cleanVersion),
                "notes-b64", encode(cleanNotes),
                "sha256", sha256);
        String objectKey = KEY_PREFIX + id;
        storageService.uploadObject(objectKey, file, metadata);

        StorageService.StoredObject stored = storageService.getInfo(objectKey);
        if (stored == null) {
            throw ApiException.unavailable("安装包已上传，但暂时无法读取文件信息");
        }
        return toPackageInfo(stored);
    }

    public Download openDownload(String id) {
        String objectKey = objectKey(id);
        ResponseInputStream<GetObjectResponse> stream = storageService.getStream(objectKey);
        if (stream == null) {
            throw ApiException.notFound("安装包不存在或已被删除");
        }
        GetObjectResponse response = stream.response();
        PackageInfo info = fromMetadata(
                id,
                response.contentLength() != null ? response.contentLength() : 0L,
                response.lastModified(),
                response.contentType(),
                response.metadata());
        return new Download(info, stream);
    }

    public void delete(String id) {
        String objectKey = objectKey(id);
        if (storageService.getInfo(objectKey) == null) {
            throw ApiException.notFound("安装包不存在或已被删除");
        }
        storageService.delete(objectKey);
    }

    private PackageInfo toPackageInfo(StorageService.StoredObject object) {
        String id = object.key().substring(KEY_PREFIX.length());
        return fromMetadata(id, object.size(), object.lastModified(), object.contentType(), object.metadata());
    }

    private PackageInfo fromMetadata(
            String id,
            long size,
            Instant uploadedAt,
            String contentType,
            Map<String, String> metadata) {
        Map<String, String> safeMetadata = metadata != null ? metadata : Map.of();
        return new PackageInfo(
                id,
                decode(safeMetadata.get("filename-b64"), "未命名安装包"),
                decode(safeMetadata.get("version-b64"), ""),
                decode(safeMetadata.get("notes-b64"), ""),
                size,
                safeMetadata.getOrDefault("sha256", ""),
                uploadedAt,
                contentType != null ? contentType : "application/octet-stream");
    }

    private static String objectKey(String id) {
        try {
            return KEY_PREFIX + UUID.fromString(id);
        } catch (IllegalArgumentException | NullPointerException e) {
            throw ApiException.badRequest("安装包编号格式不正确");
        }
    }

    private static String cleanFileName(String originalName) {
        if (originalName == null || originalName.isBlank()) {
            return "";
        }
        String normalized = originalName.replace('\\', '/');
        String fileName = normalized.substring(normalized.lastIndexOf('/') + 1).trim();
        return fileName.replaceAll("[\\p{Cntrl}]", "");
    }

    private static void validateFileName(String fileName) {
        if (fileName.isBlank()) {
            throw ApiException.badRequest("无法识别安装包文件名");
        }
        if (fileName.length() > MAX_FILE_NAME_LENGTH) {
            throw ApiException.badRequest("安装包文件名不能超过 " + MAX_FILE_NAME_LENGTH + " 个字符");
        }
        String lowerName = fileName.toLowerCase(Locale.ROOT);
        boolean allowed = ALLOWED_SUFFIXES.stream().anyMatch(lowerName::endsWith);
        if (!allowed) {
            throw ApiException.badRequest("仅支持 EXE、MSI、MSIX、ZIP、7Z、RAR、TAR、TGZ 安装包");
        }
    }

    private static String normalize(String value, int maxLength, String fieldName) {
        String normalized = value == null ? "" : value.trim();
        if (normalized.length() > maxLength) {
            throw ApiException.badRequest(fieldName + "不能超过 " + maxLength + " 个字符");
        }
        return normalized;
    }

    private static String sha256(MultipartFile file) throws IOException {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream input = file.getInputStream()) {
                byte[] buffer = new byte[64 * 1024];
                int read;
                while ((read = input.read(buffer)) != -1) {
                    digest.update(buffer, 0, read);
                }
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("当前运行环境不支持 SHA-256", e);
        }
    }

    private static String encode(String value) {
        return Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8));
    }

    private static String decode(String value, String fallback) {
        if (value == null || value.isBlank()) {
            return fallback;
        }
        try {
            return new String(Base64.getDecoder().decode(value), StandardCharsets.UTF_8);
        } catch (IllegalArgumentException e) {
            return fallback;
        }
    }

    public record PackageInfo(
            String id,
            String fileName,
            String version,
            String notes,
            long size,
            String sha256,
            Instant uploadedAt,
            String contentType) {
    }

    public record Download(PackageInfo info, ResponseInputStream<GetObjectResponse> stream) {
    }
}
