package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.service.WirelessHidDeviceManager;
import com.auto.whid.sdk.WirelessHidControlClient;
import com.auto.whid.sdk.WirelessHidException;
import com.auto.whid.sdk.WirelessHidManagementClient;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import tools.jackson.databind.JsonNode;

import java.io.IOException;
import java.util.List;
import java.util.Map;

/** Operator-facing Wireless HID discovery, control, management, and OTA API. */
@RestController
@RequestMapping("/api/wireless-hid")
public class WirelessHidController {

    private final WirelessHidDeviceManager manager;

    public WirelessHidController(WirelessHidDeviceManager manager) {
        this.manager = manager;
    }

    @GetMapping("/devices")
    public List<WirelessHidDeviceManager.DeviceView> devices() {
        return manager.listDevices();
    }

    @PostMapping("/discover")
    public List<WirelessHidDeviceManager.DeviceView> discover(
            @RequestBody(required = false) DiscoverRequest request) {
        String ip = request == null ? null : request.ip();
        int timeoutMillis =
                request == null || request.timeoutMillis() == null
                        ? 1500
                        : request.timeoutMillis();
        return perform(() -> manager.discover(ip, timeoutMillis));
    }

    @PostMapping("/{id}/connect")
    public WirelessHidDeviceManager.DeviceView connect(@PathVariable int id) {
        return perform(() -> manager.connect(id));
    }

    @PostMapping("/{id}/disconnect")
    public WirelessHidDeviceManager.DeviceView disconnect(@PathVariable int id) {
        return perform(() -> manager.disconnect(id));
    }

    @GetMapping("/{id}/status")
    public WirelessHidControlClient.Status status(@PathVariable int id) {
        return perform(() -> manager.controlStatus(id));
    }

    @PostMapping("/{id}/keyboard")
    public Map<String, Object> keyboard(
            @PathVariable int id,
            @RequestBody KeyboardRequest request) {
        if (request == null) {
            throw ApiException.badRequest("键盘请求不能为空");
        }
        perform(() -> {
            if (request.text() != null) {
                manager.typeText(
                        id,
                        request.text(),
                        request.delayMillis() == null ? 20 : request.delayMillis());
            } else {
                int[] keys = request.keys() == null
                        ? new int[0]
                        : request.keys().stream().mapToInt(Integer::intValue).toArray();
                manager.keyboardReport(
                        id,
                        request.modifier() == null ? 0 : request.modifier(),
                        keys,
                        request.tap() == null || request.tap());
            }
            return null;
        });
        return Map.of("ok", true);
    }

    @PostMapping("/{id}/mouse/relative")
    public Map<String, Object> relativeMouse(
            @PathVariable int id,
            @RequestBody RelativeMouseRequest request) {
        if (request == null) {
            throw ApiException.badRequest("相对鼠标请求不能为空");
        }
        perform(() -> {
            manager.relativeMouse(
                    id,
                    value(request.buttons()),
                    value(request.x()),
                    value(request.y()),
                    value(request.wheel()));
            return null;
        });
        return Map.of("ok", true);
    }

    @PostMapping("/{id}/mouse/absolute")
    public Map<String, Object> absoluteMouse(
            @PathVariable int id,
            @RequestBody AbsoluteMouseRequest request) {
        if (request == null || request.x() == null || request.y() == null) {
            throw ApiException.badRequest("绝对鼠标请求必须包含 x 和 y");
        }
        perform(() -> {
            manager.absoluteMouse(
                    id,
                    value(request.buttons()),
                    request.x(),
                    request.y(),
                    value(request.wheel()));
            return null;
        });
        return Map.of("ok", true);
    }

    @PostMapping("/{id}/release-all")
    public Map<String, Object> releaseAll(@PathVariable int id) {
        perform(() -> {
            manager.releaseAll(id);
            return null;
        });
        return Map.of("ok", true);
    }

    @PostMapping("/{id}/management/session")
    public WirelessHidManagementClient.Session authenticate(
            @PathVariable int id,
            @RequestBody AuthenticationRequest request) {
        if (request == null || request.pin() == null || request.pin().isEmpty()) {
            throw ApiException.badRequest("请输入管理 PIN/凭据");
        }
        return perform(() -> manager.authenticate(id, request.pin()));
    }

    @GetMapping("/{id}/management/status")
    public JsonNode managementStatus(@PathVariable int id) {
        return perform(() -> manager.managementStatus(id));
    }

    @PostMapping("/{id}/management/name")
    public WirelessHidDeviceManager.DeviceView rename(
            @PathVariable int id,
            @RequestBody RenameRequest request) {
        if (request == null || request.name() == null) {
            throw ApiException.badRequest("设备名称不能为空");
        }
        return perform(() -> manager.rename(id, request.name()));
    }

    @PostMapping("/{id}/management/provision")
    public JsonNode enterProvisioning(@PathVariable int id) {
        return perform(() -> manager.enterProvisioning(id));
    }

    @PostMapping("/{id}/management/factory-reset")
    public JsonNode factoryReset(
            @PathVariable int id,
            @RequestBody FactoryResetRequest request) {
        if (request == null || request.confirmDeviceId() == null) {
            throw ApiException.badRequest("请输入设备 ID 完成二次确认");
        }
        return perform(() -> manager.factoryReset(id, request.confirmDeviceId()));
    }

    @PostMapping("/{id}/management/ota")
    public WirelessHidManagementClient.OtaResult ota(
            @PathVariable int id,
            @RequestPart("file") MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw ApiException.badRequest("固件文件不能为空");
        }
        if (file.getSize() > WirelessHidManagementClient.MAX_FIRMWARE_SIZE) {
            throw ApiException.badRequest("固件不能超过 0x180000 字节（1536 KiB）");
        }
        return perform(() -> manager.ota(
                id,
                file.getOriginalFilename(),
                file.getBytes()));
    }

    @PostMapping("/ap/provision")
    public JsonNode provisionAccessPoint(@RequestBody ApProvisionRequest request) {
        if (request == null) {
            throw ApiException.badRequest("AP 配网参数不能为空");
        }
        return perform(() -> manager.provisionAccessPoint(
                request.gatewayIp(),
                request.currentPin(),
                request.ssid(),
                request.password(),
                request.name(),
                request.newPin()));
    }

    @DeleteMapping("/{id}")
    public Map<String, Object> delete(@PathVariable int id) {
        perform(() -> {
            manager.delete(id);
            return null;
        });
        return Map.of("ok", true);
    }

    private <T> T perform(IoOperation<T> operation) {
        try {
            return operation.run();
        } catch (ApiException e) {
            throw e;
        } catch (WirelessHidException e) {
            if (e.getHttpStatus() != null) {
                HttpStatus status = HttpStatus.resolve(e.getHttpStatus());
                throw new ApiException(
                        status == null ? HttpStatus.BAD_GATEWAY : status,
                        e.getMessage());
            }
            if (Integer.valueOf(1).equals(e.getDeviceStatus())) {
                throw ApiException.conflict(e.getMessage());
            }
            throw ApiException.unavailable(e.getMessage());
        } catch (IllegalArgumentException e) {
            throw ApiException.badRequest(e.getMessage());
        } catch (IOException e) {
            throw ApiException.unavailable(
                    e.getMessage() == null ? "Wireless HID 设备通信失败" : e.getMessage());
        }
    }

    private static int value(Integer value) {
        return value == null ? 0 : value;
    }

    @FunctionalInterface
    private interface IoOperation<T> {
        T run() throws IOException;
    }

    public record DiscoverRequest(String ip, Integer timeoutMillis) {
    }

    public record KeyboardRequest(
            String text,
            Integer modifier,
            List<Integer> keys,
            Boolean tap,
            Integer delayMillis) {
    }

    public record RelativeMouseRequest(
            Integer buttons,
            Integer x,
            Integer y,
            Integer wheel) {
    }

    public record AbsoluteMouseRequest(
            Integer buttons,
            Integer x,
            Integer y,
            Integer wheel) {
    }

    public record AuthenticationRequest(String pin) {
    }

    public record RenameRequest(String name) {
    }

    public record FactoryResetRequest(String confirmDeviceId) {
    }

    public record ApProvisionRequest(
            String gatewayIp,
            String currentPin,
            String ssid,
            String password,
            String name,
            String newPin) {
    }
}
