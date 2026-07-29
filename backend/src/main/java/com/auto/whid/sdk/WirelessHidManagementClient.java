package com.auto.whid.sdk;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.io.IOException;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

/** Authenticated HTTP management client for Wireless HID Firmware V1. */
public final class WirelessHidManagementClient {

    public static final int DEFAULT_PORT = 39668;
    public static final int MAX_FIRMWARE_SIZE = 0x180000;
    private static final Duration NORMAL_TIMEOUT = Duration.ofSeconds(15);
    private static final Duration OTA_TIMEOUT = Duration.ofSeconds(180);

    private final ObjectMapper objectMapper;
    private final HttpClient httpClient;
    private final String host;
    private final int port;
    private final String expectedDeviceId;

    private String token;
    private String role;
    private Instant expiresAt;

    public WirelessHidManagementClient(
            ObjectMapper objectMapper,
            String host,
            int port,
            String expectedDeviceId) {
        this.objectMapper = Objects.requireNonNull(objectMapper, "objectMapper");
        this.host = requireIpv4(host, true);
        if (port < 1 || port > 65535) {
            throw new IllegalArgumentException("管理端口超出范围");
        }
        if (expectedDeviceId == null || !expectedDeviceId.matches("[0-9A-F]{12}")) {
            throw new IllegalArgumentException("设备 ID 必须是 12 位大写十六进制");
        }
        this.port = port;
        this.expectedDeviceId = expectedDeviceId;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(2))
                .followRedirects(HttpClient.Redirect.NEVER)
                .build();
    }

    public synchronized Session authenticate(char[] pin) throws IOException {
        if (pin == null || pin.length == 0 || pin.length > 128) {
            throw new IllegalArgumentException("管理 PIN/凭据不能为空且不能超过 128 个字符");
        }
        try {
            JsonNode challengeBody = sendJson(HttpRequest.newBuilder(uri("/api/auth/challenge"))
                    .timeout(NORMAL_TIMEOUT)
                    .GET()
                    .build(), false);
            String deviceId = requiredText(challengeBody, "deviceId", 12);
            String challenge = requiredText(challengeBody, "challenge", 32);
            String algorithm = requiredText(challengeBody, "algorithm", 32);
            if (!expectedDeviceId.equals(deviceId)) {
                throw new WirelessHidException("认证挑战的设备 ID 与发现结果不一致");
            }
            if (!challenge.matches("[0-9a-f]{32}") || !"HMAC-SHA256".equals(algorithm)) {
                throw new WirelessHidException("设备返回了不支持的认证挑战");
            }

            String proof = calculateProof(deviceId, pin, challenge);
            HttpRequest request = HttpRequest.newBuilder(uri("/api/auth/session"))
                    .timeout(NORMAL_TIMEOUT)
                    .header("Content-Type", "application/x-www-form-urlencoded")
                    .POST(HttpRequest.BodyPublishers.ofString(
                            form(Map.of("proof", proof)),
                            StandardCharsets.UTF_8))
                    .build();
            JsonNode sessionBody = sendJson(request, false);
            String sessionToken = requiredText(sessionBody, "token", 64);
            String sessionRole = requiredText(sessionBody, "role", 16);
            int expiresIn = sessionBody.path("expiresIn").asInt(0);
            if (!sessionToken.matches("[0-9a-f]{64}")
                    || (!"user".equals(sessionRole) && !"factory".equals(sessionRole))
                    || expiresIn < 1
                    || expiresIn > 3600) {
                throw new WirelessHidException("设备返回了无效的管理会话");
            }
            token = sessionToken;
            role = sessionRole;
            expiresAt = Instant.now().plusSeconds(expiresIn);
            return session();
        } finally {
            java.util.Arrays.fill(pin, '\0');
        }
    }

    public synchronized JsonNode getStatus() throws IOException {
        return sendProtected("GET", "/api/status", null, NORMAL_TIMEOUT);
    }

    public synchronized JsonNode rename(String name) throws IOException {
        if (name == null
                || name.isBlank()
                || name.getBytes(StandardCharsets.UTF_8).length > 32) {
            throw new IllegalArgumentException("设备名称 UTF-8 长度必须为 1..32 字节");
        }
        return sendProtected(
                "POST",
                "/api/device/name",
                form(Map.of("name", name.strip())),
                NORMAL_TIMEOUT);
    }

    public synchronized JsonNode enterProvisioning() throws IOException {
        return sendProtected(
                "POST",
                "/api/device/provision",
                "",
                NORMAL_TIMEOUT);
    }

    public synchronized JsonNode factoryReset() throws IOException {
        if (!"factory".equals(role)) {
            throw new WirelessHidException("恢复出厂设置需要 factory 管理会话", null, 401);
        }
        return sendProtected(
                "POST",
                "/api/device/factory-reset",
                "",
                NORMAL_TIMEOUT);
    }

    public synchronized OtaResult ota(String filename, byte[] firmware) throws IOException {
        requireSession();
        validateFirmware(firmware);
        String digest = sha256Hex(firmware);
        String boundary = "----WHID" + UUID.randomUUID().toString().replace("-", "");
        String safeFilename = filename == null || filename.isBlank()
                ? "firmware.bin"
                : filename.replaceAll("[^A-Za-z0-9._-]", "_");
        byte[] prefix = (
                "--" + boundary + "\r\n"
                        + "Content-Disposition: form-data; name=\"file\"; filename=\""
                        + safeFilename + "\"\r\n"
                        + "Content-Type: application/octet-stream\r\n\r\n")
                .getBytes(StandardCharsets.UTF_8);
        byte[] suffix = ("\r\n--" + boundary + "--\r\n")
                .getBytes(StandardCharsets.UTF_8);
        List<byte[]> parts = new ArrayList<>();
        parts.add(prefix);
        parts.add(firmware);
        parts.add(suffix);

        HttpRequest request = HttpRequest.newBuilder(uri("/api/ota"))
                .timeout(OTA_TIMEOUT)
                .header("X-WHID-Token", token)
                .header("X-WHID-SHA256", digest)
                .header("Content-Type", "multipart/form-data; boundary=" + boundary)
                .POST(HttpRequest.BodyPublishers.ofByteArrays(parts))
                .build();
        JsonNode response = sendJson(request, true);
        touchSession();
        return new OtaResult(digest, firmware.length, response);
    }

    public synchronized boolean hasValidSession() {
        return token != null && expiresAt != null && Instant.now().isBefore(expiresAt);
    }

    public synchronized Session session() {
        return new Session(role, expiresAt, hasValidSession());
    }

    public synchronized void clearSession() {
        token = null;
        role = null;
        expiresAt = null;
    }

    public static JsonNode provisionAccessPoint(
            ObjectMapper objectMapper,
            String gatewayIp,
            String currentPin,
            String ssid,
            String password,
            String name,
            String newPin) throws IOException {
        String host = requireIpv4(gatewayIp, true);
        if (ssid == null || ssid.isBlank()) {
            throw new IllegalArgumentException("Wi-Fi SSID 不能为空");
        }
        if (newPin != null && !newPin.isBlank() && !newPin.matches("\\d{6}")) {
            throw new IllegalArgumentException("新用户 PIN 必须是 6 位数字");
        }
        if (name != null && name.getBytes(StandardCharsets.UTF_8).length > 32) {
            throw new IllegalArgumentException("设备名称 UTF-8 长度不能超过 32 字节");
        }

        Map<String, String> fields = new java.util.LinkedHashMap<>();
        fields.put("current_pin", currentPin == null ? "" : currentPin);
        fields.put("ssid", ssid);
        fields.put("password", password == null ? "" : password);
        fields.put("name", name == null ? "" : name);
        fields.put("new_pin", newPin == null ? "" : newPin);
        HttpClient client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(3))
                .followRedirects(HttpClient.Redirect.NEVER)
                .build();
        HttpRequest request = HttpRequest.newBuilder(
                        URI.create("http://" + host + ":80/save"))
                .timeout(NORMAL_TIMEOUT)
                .header("Content-Type", "application/x-www-form-urlencoded")
                .POST(HttpRequest.BodyPublishers.ofString(
                        form(fields),
                        StandardCharsets.UTF_8))
                .build();
        HttpResponse<String> response;
        try {
            response = client.send(
                    request,
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("AP 配网请求被中断", e);
        }
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new WirelessHidException(
                    "AP 配网失败，设备返回 HTTP " + response.statusCode(),
                    null,
                    response.statusCode());
        }
        return objectMapper.createObjectNode()
                .put("ok", true)
                .put("action", "provisioning_saved");
    }

    public static String calculateProof(
            String deviceId,
            char[] pin,
            String challenge) throws WirelessHidException {
        try {
            byte[] verifierInput =
                    (deviceId + ":" + new String(pin)).getBytes(StandardCharsets.UTF_8);
            byte[] verifier = MessageDigest.getInstance("SHA-256").digest(verifierInput);
            java.util.Arrays.fill(verifierInput, (byte) 0);
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(verifier, "HmacSHA256"));
            java.util.Arrays.fill(verifier, (byte) 0);
            byte[] proof = mac.doFinal(
                    (deviceId + ":" + challenge).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(proof);
        } catch (Exception e) {
            throw new WirelessHidException("无法计算管理认证 proof", e);
        }
    }

    public static void validateFirmware(byte[] firmware) {
        if (firmware == null || firmware.length == 0) {
            throw new IllegalArgumentException("固件文件不能为空");
        }
        if (firmware.length > MAX_FIRMWARE_SIZE) {
            throw new IllegalArgumentException(
                    "固件不能超过 0x180000 字节（1536 KiB）");
        }
        if (Byte.toUnsignedInt(firmware[0]) != 0xE9) {
            throw new IllegalArgumentException("固件首字节不是 ESP 镜像 Magic 0xE9");
        }
    }

    public static String sha256Hex(byte[] bytes) throws WirelessHidException {
        try {
            return HexFormat.of().formatHex(
                    MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException e) {
            throw new WirelessHidException("当前 Java 运行时不支持 SHA-256", e);
        }
    }

    private JsonNode sendProtected(
            String method,
            String path,
            String body,
            Duration timeout) throws IOException {
        requireSession();
        HttpRequest.Builder builder = HttpRequest.newBuilder(uri(path))
                .timeout(timeout)
                .header("X-WHID-Token", token);
        if ("GET".equals(method)) {
            builder.GET();
        } else {
            builder.header("Content-Type", "application/x-www-form-urlencoded")
                    .POST(HttpRequest.BodyPublishers.ofString(
                            body == null ? "" : body,
                            StandardCharsets.UTF_8));
        }
        JsonNode result = sendJson(builder.build(), true);
        touchSession();
        return result;
    }

    private JsonNode sendJson(HttpRequest request, boolean protectedRequest) throws IOException {
        HttpResponse<String> response;
        try {
            response = httpClient.send(
                    request,
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("管理请求被中断", e);
        }
        JsonNode body = null;
        if (response.body() != null && !response.body().isBlank()) {
            try {
                body = objectMapper.readTree(response.body());
            } catch (Exception ignored) {
                // The status code remains authoritative; never include the raw body.
            }
        }
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            if (protectedRequest && response.statusCode() == 401) {
                clearSession();
            }
            String error = body != null && body.path("error").isTextual()
                    ? body.path("error").asText()
                    : "http_" + response.statusCode();
            throw new WirelessHidException(
                    managementErrorMessage(error, response.statusCode()),
                    null,
                    response.statusCode());
        }
        if (body == null || !body.isObject()) {
            throw new WirelessHidException("管理接口没有返回有效 JSON");
        }
        return body;
    }

    private void requireSession() throws WirelessHidException {
        if (!hasValidSession()) {
            clearSession();
            throw new WirelessHidException("管理会话不存在或已过期，请重新认证", null, 401);
        }
    }

    private void touchSession() {
        expiresAt = Instant.now().plusSeconds(300);
    }

    private URI uri(String path) {
        return URI.create("http://" + host + ":" + port + path);
    }

    private static String form(Map<String, String> fields) {
        return fields.entrySet().stream()
                .map(entry -> encode(entry.getKey()) + "=" + encode(entry.getValue()))
                .collect(java.util.stream.Collectors.joining("&"));
    }

    private static String encode(String value) {
        return URLEncoder.encode(value == null ? "" : value, StandardCharsets.UTF_8);
    }

    private static String requiredText(JsonNode node, String field, int exactOrMaximumLength)
            throws WirelessHidException {
        JsonNode value = node.path(field);
        if (!value.isTextual()
                || value.asText().isBlank()
                || value.asText().length() > exactOrMaximumLength) {
            throw new WirelessHidException("管理接口字段无效: " + field);
        }
        return value.asText();
    }

    private static String requireIpv4(String ip, boolean requirePrivate) {
        try {
            if (ip == null || !ip.matches("\\d{1,3}(\\.\\d{1,3}){3}")) {
                throw new IllegalArgumentException("必须提供合法的 IPv4 地址");
            }
            InetAddress address = InetAddress.getByName(ip);
            if (!(address instanceof Inet4Address)
                    || !address.getHostAddress().equals(ip)) {
                throw new IllegalArgumentException("必须提供规范格式的 IPv4 地址");
            }
            if (address.isAnyLocalAddress()
                    || address.isLoopbackAddress()
                    || address.isMulticastAddress()) {
                throw new IllegalArgumentException("不允许使用本机、通配或组播地址");
            }
            if (requirePrivate && !address.isSiteLocalAddress()) {
                throw new IllegalArgumentException("AP 网关必须是局域网 IPv4 地址");
            }
            return ip;
        } catch (IOException e) {
            throw new IllegalArgumentException("无法解析 IPv4 地址", e);
        }
    }

    private static String managementErrorMessage(String error, int statusCode) {
        return switch (error) {
            case "challenge_invalid" -> "认证挑战不存在、已过期或客户端 IP 不匹配";
            case "authentication_failed" -> "管理 PIN/凭据不正确";
            case "authentication_locked" -> "认证失败次数过多，请至少等待 60 秒";
            case "unauthorized" -> "管理会话无效或权限不足";
            case "invalid_device_name" -> "设备名称不符合固件要求";
            case "ota_failed" -> "OTA 写入或镜像校验失败";
            case "configuration_clear_failed" -> "设备配置存储异常";
            default -> "设备管理请求失败（HTTP %d，%s）".formatted(statusCode, error);
        };
    }

    public record Session(String role, Instant expiresAt, boolean valid) {
    }

    public record OtaResult(String sha256, int size, JsonNode response) {
    }
}
