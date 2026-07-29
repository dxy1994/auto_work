package com.auto.service;

import com.auto.common.ApiException;
import com.auto.entity.Machine;
import com.auto.entity.MouseKeyboardDevice;
import com.auto.whid.sdk.WirelessHidControlClient;
import com.auto.whid.sdk.WirelessHidDiscoveredDevice;
import com.auto.whid.sdk.WirelessHidDiscoveryClient;
import com.auto.whid.sdk.WirelessHidManagementClient;
import jakarta.annotation.PreDestroy;
import org.springframework.stereotype.Service;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Bridges persisted mouse/keyboard devices to the stateful Wireless HID SDK.
 *
 * <p>Control and management sessions are process-memory only. PINs, proofs, and tokens
 * are never persisted.</p>
 */
@Service
public class WirelessHidDeviceManager {

    public static final String DEVICE_TYPE = "Wireless HID";

    private final MouseKeyboardDeviceService deviceService;
    private final MachineService machineService;
    private final ObjectMapper objectMapper;
    private final WirelessHidDiscoveryClient discoveryClient;
    private final Map<Integer, WirelessHidControlClient> controlClients =
            new ConcurrentHashMap<>();
    private final Map<Integer, WirelessHidManagementClient> managementClients =
            new ConcurrentHashMap<>();
    private final Map<Integer, String> lastErrors = new ConcurrentHashMap<>();

    public WirelessHidDeviceManager(
            MouseKeyboardDeviceService deviceService,
            MachineService machineService,
            ObjectMapper objectMapper) {
        this.deviceService = deviceService;
        this.machineService = machineService;
        this.objectMapper = objectMapper;
        this.discoveryClient = new WirelessHidDiscoveryClient(objectMapper);
    }

    public List<DeviceView> discover(String unicastIp, int timeoutMillis) throws IOException {
        Duration timeout = Duration.ofMillis(timeoutMillis);
        List<WirelessHidDiscoveredDevice> discovered =
                unicastIp == null || unicastIp.isBlank()
                        ? discoveryClient.discover(timeout)
                        : discoveryClient.discoverUnicast(unicastIp.strip(), timeout);
        Instant now = Instant.now();
        for (WirelessHidDiscoveredDevice device : discovered) {
            upsert(device, now);
        }
        return listDevices();
    }

    public List<DeviceView> listDevices() {
        List<DeviceView> result = new ArrayList<>();
        for (MouseKeyboardDevice device : deviceService.findAllActive()) {
            if (!DEVICE_TYPE.equalsIgnoreCase(device.getDeviceType())) {
                continue;
            }
            try {
                result.add(toView(device, readInfo(device)));
            } catch (IOException e) {
                result.add(new DeviceView(
                        device.getId(),
                        device.getName(),
                        device.getDeviceType(),
                        null,
                        null,
                        null,
                        null,
                        null,
                        null,
                        null,
                        null,
                        "invalid",
                        false,
                        machineName(device.getId()),
                        device.getRemark(),
                        device.getIsActive(),
                        "设备信息不是有效的 Wireless HID 配置"));
            }
        }
        result.sort(Comparator
                .comparing((DeviceView view) -> stateRank(view.connectionState()))
                .thenComparing(DeviceView::lastSeen, Comparator.nullsLast(Comparator.reverseOrder()))
                .thenComparing(DeviceView::id));
        return result;
    }

    public DeviceView getDevice(int id) throws IOException {
        MouseKeyboardDevice device = requireDevice(id);
        return toView(device, readInfo(device));
    }

    public synchronized DeviceView connect(int id) throws IOException {
        MouseKeyboardDevice device = requireDevice(id);
        StoredInfo info = readInfo(device);
        WirelessHidControlClient current = controlClients.get(id);
        if (current != null && current.isOpen()) {
            return toView(device, info);
        }
        if (current != null) {
            current.close();
            controlClients.remove(id, current);
        }

        WirelessHidControlClient client =
                new WirelessHidControlClient(info.ip(), info.controlPort());
        try {
            client.connectAndClaim();
            controlClients.put(id, client);
            info = info.withClaimed(true);
            writeInfo(device, info);
            deviceService.updateById(device);
            lastErrors.remove(id);
            return toView(device, info);
        } catch (IOException | RuntimeException e) {
            client.close();
            rememberError(id, e);
            throw e;
        }
    }

    public synchronized DeviceView disconnect(int id) throws IOException {
        MouseKeyboardDevice device = requireDevice(id);
        StoredInfo info = readInfo(device);
        WirelessHidControlClient client = controlClients.remove(id);
        if (client != null) {
            try {
                client.disconnect();
                info = info.withClaimed(false);
                writeInfo(device, info);
                deviceService.updateById(device);
                lastErrors.remove(id);
            } catch (IOException e) {
                rememberError(id, e);
                throw e;
            }
        }
        return toView(device, info);
    }

    public WirelessHidControlClient.Status controlStatus(int id) throws IOException {
        return withControl(id, WirelessHidControlClient::getStatus);
    }

    public void keyboardReport(int id, int modifier, int[] keys, boolean tap)
            throws IOException {
        withControl(id, client -> {
            if (tap) {
                client.tapKeyboard(modifier, keys);
            } else {
                client.sendKeyboard(modifier, keys);
            }
            return null;
        });
    }

    public void typeText(int id, String text, int delayMillis) throws IOException {
        withControl(id, client -> {
            client.typeText(text, delayMillis);
            return null;
        });
    }

    public void relativeMouse(int id, int buttons, int x, int y, int wheel)
            throws IOException {
        withControl(id, client -> {
            client.sendRelativeMouse(buttons, x, y, wheel);
            return null;
        });
    }

    public void absoluteMouse(int id, int buttons, int x, int y, int wheel)
            throws IOException {
        withControl(id, client -> {
            client.sendAbsoluteMouse(buttons, x, y, wheel);
            return null;
        });
    }

    public void releaseAll(int id) throws IOException {
        withControl(id, client -> {
            client.releaseAll();
            return null;
        });
    }

    public WirelessHidManagementClient.Session authenticate(int id, String pin)
            throws IOException {
        MouseKeyboardDevice device = requireDevice(id);
        StoredInfo info = readInfo(device);
        WirelessHidManagementClient client = new WirelessHidManagementClient(
                objectMapper,
                info.ip(),
                info.managementPort(),
                info.deviceId());
        try {
            WirelessHidManagementClient.Session session =
                    client.authenticate(pin == null ? null : pin.toCharArray());
            managementClients.put(id, client);
            lastErrors.remove(id);
            return session;
        } catch (IOException | RuntimeException e) {
            client.clearSession();
            rememberError(id, e);
            throw e;
        }
    }

    public JsonNode managementStatus(int id) throws IOException {
        return withManagement(id, WirelessHidManagementClient::getStatus);
    }

    public DeviceView rename(int id, String name) throws IOException {
        JsonNode ignored = withManagement(id, client -> client.rename(name));
        MouseKeyboardDevice device = requireDevice(id);
        StoredInfo info = readInfo(device).withName(name.strip());
        device.setName(name.strip());
        writeInfo(device, info);
        deviceService.updateById(device);
        return toView(device, info);
    }

    public JsonNode enterProvisioning(int id) throws IOException {
        JsonNode result = withManagement(id, WirelessHidManagementClient::enterProvisioning);
        closeControlQuietly(id);
        managementClients.remove(id);
        return result;
    }

    public JsonNode factoryReset(int id, String confirmationDeviceId) throws IOException {
        StoredInfo info = readInfo(requireDevice(id));
        if (!info.deviceId().equals(confirmationDeviceId)) {
            throw new IllegalArgumentException("确认设备 ID 不匹配");
        }
        JsonNode result = withManagement(id, WirelessHidManagementClient::factoryReset);
        closeControlQuietly(id);
        managementClients.remove(id);
        return result;
    }

    public WirelessHidManagementClient.OtaResult ota(
            int id,
            String filename,
            byte[] firmware) throws IOException {
        WirelessHidManagementClient.validateFirmware(firmware);
        closeControlQuietly(id);
        try {
            WirelessHidManagementClient.OtaResult result =
                    withManagement(id, client -> client.ota(filename, firmware));
            managementClients.remove(id);
            return result;
        } catch (IOException e) {
            rememberError(id, e);
            throw e;
        }
    }

    public JsonNode provisionAccessPoint(
            String gatewayIp,
            String currentPin,
            String ssid,
            String password,
            String name,
            String newPin) throws IOException {
        return WirelessHidManagementClient.provisionAccessPoint(
                objectMapper,
                gatewayIp,
                currentPin,
                ssid,
                password,
                name,
                newPin);
    }

    public synchronized void delete(int id) throws IOException {
        requireDevice(id);
        closeControlQuietly(id);
        WirelessHidManagementClient management = managementClients.remove(id);
        if (management != null) {
            management.clearSession();
        }
        lastErrors.remove(id);
        deviceService.removeById(id);
    }

    @PreDestroy
    public void shutdown() {
        for (Integer id : new ArrayList<>(controlClients.keySet())) {
            closeControlQuietly(id);
        }
        managementClients.values().forEach(WirelessHidManagementClient::clearSession);
        managementClients.clear();
    }

    private void upsert(WirelessHidDiscoveredDevice discovered, Instant seenAt)
            throws IOException {
        MouseKeyboardDevice existing = null;
        for (MouseKeyboardDevice candidate : deviceService.findAllActive()) {
            if (!DEVICE_TYPE.equalsIgnoreCase(candidate.getDeviceType())) {
                continue;
            }
            try {
                if (discovered.id().equals(readInfo(candidate).deviceId())) {
                    existing = candidate;
                    break;
                }
            } catch (IOException ignored) {
                // Leave malformed legacy rows untouched.
            }
        }

        StoredInfo info = StoredInfo.from(discovered, seenAt);
        if (existing == null) {
            MouseKeyboardDevice created = new MouseKeyboardDevice();
            created.setName(discovered.name());
            created.setDeviceType(DEVICE_TYPE);
            created.setRemark("");
            created.setIsActive(1);
            writeInfo(created, info);
            deviceService.save(created);
        } else {
            existing.setName(discovered.name());
            existing.setDeviceType(DEVICE_TYPE);
            writeInfo(existing, info);
            deviceService.updateById(existing);
        }
    }

    private DeviceView toView(MouseKeyboardDevice device, StoredInfo info) {
        WirelessHidControlClient control = controlClients.get(device.getId());
        boolean connected = control != null && control.isOpen();
        WirelessHidManagementClient management = managementClients.get(device.getId());
        boolean managementAuthenticated =
                management != null && management.hasValidSession();
        String connectionState;
        if (connected) {
            connectionState = "connected";
        } else if (control != null && control.getLastError() != null) {
            connectionState = "offline";
        } else if (info.claimed()) {
            connectionState = "occupied";
        } else if (info.lastSeen() == null
                || info.lastSeen().isBefore(Instant.now().minusSeconds(15))) {
            connectionState = "offline";
        } else {
            connectionState = "ready";
        }
        String error = lastErrors.get(device.getId());
        if (error == null && control != null) {
            error = control.getLastError();
        }
        return new DeviceView(
                device.getId(),
                device.getName(),
                device.getDeviceType(),
                info.deviceId(),
                info.ip(),
                info.controlPort(),
                info.managementPort(),
                info.firmware(),
                info.claimed(),
                info.ch9329(),
                info.rssi(),
                connectionState,
                managementAuthenticated,
                machineName(device.getId()),
                device.getRemark(),
                device.getIsActive(),
                error,
                info.lastSeen());
    }

    private MouseKeyboardDevice requireDevice(int id) {
        MouseKeyboardDevice device = deviceService.getById(id);
        if (device == null || !DEVICE_TYPE.equalsIgnoreCase(device.getDeviceType())) {
            throw ApiException.notFound("Wireless HID 设备不存在");
        }
        return device;
    }

    private StoredInfo readInfo(MouseKeyboardDevice device) throws IOException {
        try {
            StoredInfo info = objectMapper.readValue(
                    device.getDeviceInfo(),
                    StoredInfo.class);
            info.validate();
            return info;
        } catch (Exception e) {
            throw new IOException("设备连接信息无效，请重新发现设备", e);
        }
    }

    private void writeInfo(MouseKeyboardDevice device, StoredInfo info) throws IOException {
        device.setDeviceInfo(objectMapper.writeValueAsString(info));
    }

    private String machineName(int deviceId) {
        Machine machine = machineService.findByMkDeviceId(deviceId);
        if (machine == null) {
            return null;
        }
        return machine.getName() == null || machine.getName().isBlank()
                ? machine.getMacAddress()
                : machine.getName();
    }

    private <T> T withControl(int id, ControlOperation<T> operation) throws IOException {
        requireDevice(id);
        WirelessHidControlClient client = controlClients.get(id);
        if (client == null || !client.isOpen()) {
            throw new IOException("尚未取得该设备的 TCP 控制权");
        }
        try {
            T result = operation.run(client);
            lastErrors.remove(id);
            return result;
        } catch (IOException | RuntimeException e) {
            rememberError(id, e);
            throw e;
        }
    }

    private <T> T withManagement(int id, ManagementOperation<T> operation) throws IOException {
        requireDevice(id);
        WirelessHidManagementClient client = managementClients.get(id);
        if (client == null || !client.hasValidSession()) {
            managementClients.remove(id);
            throw new IOException("管理会话不存在或已过期，请重新认证");
        }
        try {
            T result = operation.run(client);
            lastErrors.remove(id);
            return result;
        } catch (IOException | RuntimeException e) {
            rememberError(id, e);
            throw e;
        }
    }

    private void closeControlQuietly(int id) {
        WirelessHidControlClient client = controlClients.remove(id);
        if (client != null) {
            try {
                client.disconnect();
            } catch (IOException ignored) {
                client.close();
            }
        }
    }

    private void rememberError(int id, Exception exception) {
        String message = exception.getMessage();
        lastErrors.put(
                id,
                message == null ? exception.getClass().getSimpleName() : message);
    }

    private static int stateRank(String state) {
        return switch (state) {
            case "connected" -> 0;
            case "ready" -> 1;
            case "occupied" -> 2;
            case "offline" -> 3;
            default -> 4;
        };
    }

    @FunctionalInterface
    private interface ControlOperation<T> {
        T run(WirelessHidControlClient client) throws IOException;
    }

    @FunctionalInterface
    private interface ManagementOperation<T> {
        T run(WirelessHidManagementClient client) throws IOException;
    }

    public record DeviceView(
            Integer id,
            String name,
            String deviceType,
            String deviceId,
            String ip,
            Integer controlPort,
            Integer managementPort,
            String firmware,
            Boolean claimed,
            Boolean ch9329,
            Integer rssi,
            String connectionState,
            boolean managementAuthenticated,
            String machineName,
            String remark,
            Integer isActive,
            String lastError,
            Instant lastSeen) {

        private DeviceView(
                Integer id,
                String name,
                String deviceType,
                String deviceId,
                String ip,
                Integer controlPort,
                Integer managementPort,
                String firmware,
                Boolean claimed,
                Boolean ch9329,
                Integer rssi,
                String connectionState,
                boolean managementAuthenticated,
                String machineName,
                String remark,
                Integer isActive,
                String lastError) {
            this(
                    id,
                    name,
                    deviceType,
                    deviceId,
                    ip,
                    controlPort,
                    managementPort,
                    firmware,
                    claimed,
                    ch9329,
                    rssi,
                    connectionState,
                    managementAuthenticated,
                    machineName,
                    remark,
                    isActive,
                    lastError,
                    null);
        }
    }

    public record StoredInfo(
            int protocol,
            String deviceId,
            String name,
            String ip,
            int controlPort,
            int managementPort,
            String firmware,
            boolean claimed,
            boolean ch9329,
            int rssi,
            Instant lastSeen) {

        static StoredInfo from(WirelessHidDiscoveredDevice device, Instant lastSeen) {
            return new StoredInfo(
                    device.protocol(),
                    device.id(),
                    device.name(),
                    device.ip(),
                    device.controlPort(),
                    device.managementPort(),
                    device.firmware(),
                    device.claimed(),
                    device.ch9329(),
                    device.rssi(),
                    lastSeen);
        }

        StoredInfo withName(String newName) {
            return new StoredInfo(
                    protocol,
                    deviceId,
                    newName,
                    ip,
                    controlPort,
                    managementPort,
                    firmware,
                    claimed,
                    ch9329,
                    rssi,
                    lastSeen);
        }

        StoredInfo withClaimed(boolean newClaimed) {
            return new StoredInfo(
                    protocol,
                    deviceId,
                    name,
                    ip,
                    controlPort,
                    managementPort,
                    firmware,
                    newClaimed,
                    ch9329,
                    rssi,
                    lastSeen);
        }

        void validate() {
            if (protocol != 1
                    || deviceId == null
                    || !deviceId.matches("[0-9A-F]{12}")
                    || ip == null
                    || controlPort < 1
                    || controlPort > 65535
                    || managementPort < 1
                    || managementPort > 65535) {
                throw new IllegalArgumentException("设备连接信息字段无效");
            }
        }
    }
}
