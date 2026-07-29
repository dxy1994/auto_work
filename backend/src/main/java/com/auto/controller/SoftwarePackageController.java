package com.auto.controller;

import com.auto.service.SoftwarePackageService;
import org.springframework.core.io.InputStreamResource;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

/**
 * 总控内网软件分发接口：发布、列出、下载和删除文件。
 */
@RestController
@RequestMapping("/api/software-packages")
public class SoftwarePackageController {

    private final SoftwarePackageService softwarePackageService;

    public SoftwarePackageController(SoftwarePackageService softwarePackageService) {
        this.softwarePackageService = softwarePackageService;
    }

    @GetMapping
    public List<SoftwarePackageService.PackageInfo> list() {
        return softwarePackageService.list();
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public SoftwarePackageService.PackageInfo upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "version", required = false) String version,
            @RequestParam(value = "notes", required = false) String notes) throws IOException {
        return softwarePackageService.upload(file, version, notes);
    }

    @GetMapping("/{id}/download")
    public ResponseEntity<InputStreamResource> download(@PathVariable String id) {
        SoftwarePackageService.Download download = softwarePackageService.openDownload(id);
        SoftwarePackageService.PackageInfo info = download.info();
        MediaType mediaType;
        try {
            mediaType = MediaType.parseMediaType(info.contentType());
        } catch (IllegalArgumentException e) {
            mediaType = MediaType.APPLICATION_OCTET_STREAM;
        }
        String disposition = ContentDisposition.attachment()
                .filename(info.fileName(), StandardCharsets.UTF_8)
                .build()
                .toString();

        return ResponseEntity.ok()
                .contentType(mediaType)
                .contentLength(info.size())
                .header(HttpHeaders.CONTENT_DISPOSITION, disposition)
                .header(HttpHeaders.CACHE_CONTROL, "private, no-cache, no-transform")
                .header("X-Content-Type-Options", "nosniff")
                .body(new InputStreamResource(download.stream()));
    }

    @DeleteMapping("/{id}")
    public Map<String, Object> delete(@PathVariable String id) {
        softwarePackageService.delete(id);
        return Map.of("message", "文件已删除");
    }
}
