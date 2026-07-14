package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.service.StorageService;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 系统级端点：健康检查与图片上传。
 *
 * <p>对应原 Python main.py 的 /api/health 与 /api/upload。图片上传到对象存储（RustFS），
 * 对象键 images/&lt;uuid&gt;.&lt;ext&gt;，返回 URL 仍为 /uploads/images/&lt;uuid&gt;.&lt;ext&gt;。
 */
@RestController
@RequestMapping("/api")
public class SystemController {

    private static final Map<String, String> IMAGE_EXTENSIONS = Map.of(
            "image/jpeg", ".jpg",
            "image/png", ".png",
            "image/gif", ".gif",
            "image/webp", ".webp",
            "image/bmp", ".bmp");

    private final StorageService storageService;

    public SystemController(StorageService storageService) {
        this.storageService = storageService;
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("status", "ok");
        resp.put("version", "1.0.0");
        return resp;
    }

    @PostMapping("/upload")
    public Map<String, Object> upload(@RequestParam("file") MultipartFile file) throws IOException {
        if (file == null || file.isEmpty()) {
            throw ApiException.badRequest("上传文件不能为空");
        }
        String ext = IMAGE_EXTENSIONS.get(file.getContentType());
        if (ext == null) {
            throw ApiException.badRequest("仅支持 JPEG/PNG/GIF/WebP/BMP 格式");
        }
        String objectKey = storageService.upload("images", ext, file);

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("code", 0);
        resp.put("url", "/uploads/" + objectKey);
        return resp;
    }
}
