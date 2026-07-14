package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.entity.WebsiteSchedule;
import com.auto.service.AccountService;
import com.auto.service.StorageService;
import com.auto.service.WebsiteScheduleService;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * 账号定时执行配置。
 *
 * <p>含调度配置 upsert/copy 与提醒音频上传。音频存放于对象存储（RustFS），
 * 对象键 audio/&lt;uuid&gt;.&lt;ext&gt;，数据库仍存相对路径 uploads/audio/&lt;uuid&gt;.&lt;ext&gt;。
 */
@RestController
@RequestMapping("/api/schedules")
public class ScheduleController {

    private static final Set<String> ALLOWED_AUDIO_EXTENSIONS =
            Set.of(".mp3", ".wav", ".ogg", ".flac", ".m4a", ".wma");
    private static final long MAX_AUDIO_SIZE = 10L * 1024 * 1024;
    private static final String AUDIO_PATH_PREFIX = "uploads/audio/";

    private final WebsiteScheduleService scheduleService;
    private final AccountService accountService;
    private final StorageService storageService;

    public ScheduleController(WebsiteScheduleService scheduleService, AccountService accountService,
                              StorageService storageService) {
        this.scheduleService = scheduleService;
        this.accountService = accountService;
        this.storageService = storageService;
    }

    private static String extension(String filename) {
        int idx = filename.lastIndexOf('.');
        return idx >= 0 ? filename.substring(idx).toLowerCase(Locale.ROOT) : "";
    }

    /** 校验提醒音频相对路径必须为系统上传的 uploads/audio 文件；为空返回 null。 */
    private String validateAudioPath(String relativePath) {
        if (relativePath == null || relativePath.isBlank()) {
            return null;
        }
        String normalized = relativePath.replace('\\', '/');
        String name = normalized.substring(normalized.lastIndexOf('/') + 1);
        if (!normalized.startsWith(AUDIO_PATH_PREFIX) || normalized.contains("..")
                || name.isBlank() || !ALLOWED_AUDIO_EXTENSIONS.contains(extension(name))) {
            throw ApiException.badRequest("提醒音频路径必须是系统上传的 uploads/audio 文件");
        }
        return normalized;
    }

    /** 相对路径 uploads/audio/xxx -> 对象键 audio/xxx。 */
    private String toObjectKey(String relativePath) {
        String validated = validateAudioPath(relativePath);
        return validated != null ? validated.substring("uploads/".length()) : null;
    }

    // ── 调度配置列表 ────────────────────────────────────────────

    @GetMapping
    public List<Map<String, Object>> list(
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "schedule_type", required = false) String scheduleType) {
        return scheduleService.searchWithRelations(keyword, scheduleType);
    }

    // ── 调度配置 CRUD ───────────────────────────────────────────

    @GetMapping("/{accountId}")
    public WebsiteSchedule get(@PathVariable Integer accountId) {
        WebsiteSchedule s = scheduleService.findByAccountId(accountId);
        if (s == null) throw ApiException.notFound("该账号暂无调度配置");
        return s;
    }

    @PutMapping("/{accountId}")
    public WebsiteSchedule upsert(@PathVariable Integer accountId, @RequestBody Upsert payload) {
        if (accountService.getById(accountId) == null) {
            throw ApiException.notFound("账号不存在");
        }
        validateAudioPath(payload.alertAudioPath);

        WebsiteSchedule s = scheduleService.findByAccountId(accountId);
        if (s != null) {
            // 更新：不修改 name/code
            s.setRefreshInterval(payload.refreshInterval);
            s.setScheduleType(payload.scheduleType);
            s.setScheduleTime(payload.scheduleTime);
            s.setScheduleCron(payload.scheduleCron != null ? String.valueOf(payload.scheduleCron) : null);
            s.setAlertAudioPath(payload.alertAudioPath);
            s.setIsEnabled(Boolean.TRUE.equals(payload.isEnabled) ? 1 : 0);
            scheduleService.updateById(s);
            return s;
        }
        s = new WebsiteSchedule();
        s.setAccountId(accountId);
        s.setName(payload.name);
        s.setCode(payload.code);
        s.setRefreshInterval(payload.refreshInterval);
        s.setScheduleType(payload.scheduleType);
        s.setScheduleTime(payload.scheduleTime);
        s.setScheduleCron(payload.scheduleCron != null ? String.valueOf(payload.scheduleCron) : null);
        s.setAlertAudioPath(payload.alertAudioPath);
        s.setIsEnabled(Boolean.TRUE.equals(payload.isEnabled) ? 1 : 0);
        scheduleService.save(s);
        return s;
    }

    @PostMapping("/{accountId}/copy")
    public Map<String, Object> copy(@PathVariable Integer accountId, @RequestBody CopyRequest payload) {
        WebsiteSchedule source = scheduleService.findByAccountId(accountId);
        if (source == null) throw ApiException.notFound("源账号暂无调度配置");

        List<Integer> skipped = new ArrayList<>();
        List<Integer> created = new ArrayList<>();
        List<Integer> targets = payload.targetAccountIds != null ? payload.targetAccountIds : List.of();
        for (Integer targetId : targets) {
            if (accountService.getById(targetId) == null) {
                skipped.add(targetId);
                continue;
            }
            if (scheduleService.findByAccountId(targetId) != null) {
                skipped.add(targetId);
                continue;
            }
            WebsiteSchedule s = new WebsiteSchedule();
            s.setAccountId(targetId);
            s.setName(source.getName());
            s.setCode(source.getCode());
            s.setRefreshInterval(source.getRefreshInterval());
            s.setScheduleType(source.getScheduleType());
            s.setScheduleTime(source.getScheduleTime());
            s.setScheduleCron(source.getScheduleCron());
            s.setAlertAudioPath(source.getAlertAudioPath());
            s.setIsEnabled(source.getIsEnabled());
            scheduleService.save(s);
            created.add(targetId);
        }
        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("status", "ok");
        resp.put("copied_count", created.size());
        resp.put("skipped_count", skipped.size());
        resp.put("created_ids", created);
        resp.put("skipped_ids", skipped);
        return resp;
    }

    // ── 音频文件上传 ────────────────────────────────────────────

    @PostMapping("/{accountId}/audio")
    public Map<String, Object> uploadAlertAudio(@PathVariable Integer accountId,
                                                @RequestParam("file") MultipartFile file) throws IOException {
        String ext = extension(file.getOriginalFilename() == null ? "" : file.getOriginalFilename());
        if (!ALLOWED_AUDIO_EXTENSIONS.contains(ext)) {
            throw ApiException.badRequest("不支持的音频格式，允许: " + String.join(", ", ALLOWED_AUDIO_EXTENSIONS));
        }

        WebsiteSchedule s = scheduleService.findByAccountId(accountId);
        if (s == null) throw ApiException.notFound("该账号暂无调度配置，请先在子功能配置中创建");

        if (file.getSize() > MAX_AUDIO_SIZE) {
            throw ApiException.badRequest("音频文件不能超过 10MB");
        }

        String objectKey = storageService.upload("audio", ext, file);
        String relativePath = "uploads/" + objectKey;

        // 先记录旧对象键，写库失败时删除新对象并保留旧配置，避免配置指向已删除资源。
        String oldObjectKey;
        try {
            oldObjectKey = toObjectKey(s.getAlertAudioPath());
        } catch (ApiException e) {
            oldObjectKey = null;
        }
        s.setAlertAudioPath(relativePath);
        try {
            scheduleService.updateById(s);
        } catch (RuntimeException e) {
            storageService.delete(objectKey);
            throw e;
        }
        if (oldObjectKey != null) {
            storageService.delete(oldObjectKey);
        }

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("status", "ok");
        resp.put("alert_audio_path", relativePath);
        resp.put("filename", file.getOriginalFilename());
        return resp;
    }

    /** 调度配置 upsert 入参。 */
    public static class Upsert {
        public String name;
        public String code;
        public Integer refreshInterval = -1;
        public String scheduleType = "none";
        public java.time.LocalDateTime scheduleTime;
        public Integer scheduleCron;
        public String alertAudioPath;
        public Boolean isEnabled = true;
    }

    /** 复制调度配置入参。 */
    public static class CopyRequest {
        public List<Integer> targetAccountIds;
    }
}
