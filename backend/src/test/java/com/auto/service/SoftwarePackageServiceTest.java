package com.auto.service;

import com.auto.common.ApiException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockMultipartFile;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class SoftwarePackageServiceTest {

    @Mock
    private StorageService storageService;

    private SoftwarePackageService service;

    @BeforeEach
    void setUp() {
        service = new SoftwarePackageService(storageService);
    }

    @Test
    void uploadStoresDisplayMetadataAndChecksum() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file",
                "总控客户端-1.4.2.zip",
                "application/zip",
                "hello package".getBytes(StandardCharsets.UTF_8));
        Instant uploadedAt = Instant.parse("2026-07-29T10:00:00Z");
        String expectedHash = "aee53fb342be0b0be4de05e96134f64af1f72b1d7909fb05dbe3887ac6244525";

        when(storageService.getInfo(anyString())).thenAnswer(invocation -> {
            String key = invocation.getArgument(0);
            return new StorageService.StoredObject(
                    key,
                    file.getSize(),
                    uploadedAt,
                    file.getContentType(),
                    Map.of(
                            "filename-b64", encoded("总控客户端-1.4.2.zip"),
                            "version-b64", encoded("1.4.2"),
                            "notes-b64", encoded("修复自动启动"),
                            "sha256", expectedHash));
        });

        SoftwarePackageService.PackageInfo result =
                service.upload(file, " 1.4.2 ", " 修复自动启动 ");

        assertEquals("总控客户端-1.4.2.zip", result.fileName());
        assertEquals("1.4.2", result.version());
        assertEquals("修复自动启动", result.notes());
        assertEquals(expectedHash, result.sha256());

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, String>> metadataCaptor = ArgumentCaptor.forClass(Map.class);
        ArgumentCaptor<String> keyCaptor = ArgumentCaptor.forClass(String.class);
        verify(storageService).uploadObject(keyCaptor.capture(), eq(file), metadataCaptor.capture());
        assertTrue(keyCaptor.getValue().matches(
                "software-packages/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"));
        assertEquals(expectedHash, metadataCaptor.getValue().get("sha256"));
        assertEquals("总控客户端-1.4.2.zip",
                decoded(metadataCaptor.getValue().get("filename-b64")));
    }

    @Test
    void listDecodesMetadataAndPutsNewestFirst() {
        StorageService.StoredObject older = stored(
                "11111111-1111-1111-1111-111111111111",
                "旧版本.msi",
                "1.0.0",
                Instant.parse("2026-07-27T10:00:00Z"));
        StorageService.StoredObject newer = stored(
                "22222222-2222-2222-2222-222222222222",
                "新版本.exe",
                "2.0.0",
                Instant.parse("2026-07-29T10:00:00Z"));
        when(storageService.list("software-packages/")).thenReturn(List.of(older, newer));

        List<SoftwarePackageService.PackageInfo> result = service.list();

        assertEquals(List.of("新版本.exe", "旧版本.msi"),
                result.stream().map(SoftwarePackageService.PackageInfo::fileName).toList());
        assertEquals("2.0.0", result.get(0).version());
    }

    @Test
    void uploadAcceptsOtherFileTypes() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file", "使用说明.txt", "text/plain", "distribution file".getBytes(StandardCharsets.UTF_8));
        Instant uploadedAt = Instant.parse("2026-07-29T11:00:00Z");
        when(storageService.getInfo(anyString())).thenAnswer(invocation -> new StorageService.StoredObject(
                invocation.getArgument(0),
                file.getSize(),
                uploadedAt,
                file.getContentType(),
                Map.of(
                        "filename-b64", encoded("使用说明.txt"),
                        "version-b64", encoded(""),
                        "notes-b64", encoded(""),
                        "sha256", "abc123")));

        SoftwarePackageService.PackageInfo result = service.upload(file, "", "");

        assertEquals("使用说明.txt", result.fileName());
        assertEquals("text/plain", result.contentType());
        verify(storageService).uploadObject(
                anyString(),
                eq(file),
                org.mockito.ArgumentMatchers.anyMap());
    }

    @Test
    void deleteRejectsMalformedPackageId() {
        ApiException error = assertThrows(ApiException.class, () -> service.delete("../images/demo"));
        assertEquals("文件编号格式不正确", error.getMessage());
        verify(storageService, never()).delete(anyString());
    }

    private static StorageService.StoredObject stored(
            String id,
            String fileName,
            String version,
            Instant uploadedAt) {
        return new StorageService.StoredObject(
                "software-packages/" + id,
                1024L,
                uploadedAt,
                "application/octet-stream",
                Map.of(
                        "filename-b64", encoded(fileName),
                        "version-b64", encoded(version),
                        "notes-b64", encoded(""),
                        "sha256", "abc123"));
    }

    private static String encoded(String value) {
        return Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8));
    }

    private static String decoded(String value) {
        return new String(Base64.getDecoder().decode(value), StandardCharsets.UTF_8);
    }
}
