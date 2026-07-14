package com.auto.controller;

import com.auto.service.StorageService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.core.io.InputStreamResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import software.amazon.awssdk.core.ResponseInputStream;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;

import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;

/**
 * 上传文件访问：兼容历史 /uploads/** URL 规则，从对象存储流式读取。
 *
 * <p>对象键为 URL 中 /uploads/ 之后的部分（如 /uploads/images/xxx.png -> images/xxx.png）。
 */
@RestController
public class StorageController {

    private static final String PREFIX = "/uploads/";

    private final StorageService storageService;

    public StorageController(StorageService storageService) {
        this.storageService = storageService;
    }

    @GetMapping("/uploads/**")
    public ResponseEntity<InputStreamResource> serve(HttpServletRequest request) {
        String uri = request.getRequestURI();
        int idx = uri.indexOf(PREFIX);
        if (idx < 0) {
            return ResponseEntity.notFound().build();
        }
        String objectKey = URLDecoder.decode(uri.substring(idx + PREFIX.length()), StandardCharsets.UTF_8);
        if (objectKey.isBlank()) {
            return ResponseEntity.notFound().build();
        }
        ResponseInputStream<GetObjectResponse> stream = storageService.getStream(objectKey);
        if (stream == null) {
            return ResponseEntity.notFound().build();
        }
        String contentType = stream.response().contentType();
        MediaType mediaType = contentType != null
                ? MediaType.parseMediaType(contentType)
                : MediaType.APPLICATION_OCTET_STREAM;
        Long length = stream.response().contentLength();
        ResponseEntity.BodyBuilder builder = ResponseEntity.status(HttpStatus.OK)
                .contentType(mediaType)
                .header(HttpHeaders.CACHE_CONTROL, "public, max-age=86400");
        if (length != null) {
            builder.contentLength(length);
        }
        return builder.body(new InputStreamResource(stream));
    }
}
