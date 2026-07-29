package com.auto.whid.sdk;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.InterfaceAddress;
import java.net.NetworkInterface;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

/** UDP discovery client with one bound socket per active IPv4 interface. */
public final class WirelessHidDiscoveryClient {

    public static final int DEFAULT_PORT = 39666;
    private static final byte[] DISCOVERY_REQUEST =
            "WHID_DISCOVER_V1".getBytes(StandardCharsets.UTF_8);
    private static final int MAX_RESPONSE_SIZE = 2048;

    private final ObjectMapper objectMapper;
    private final int port;

    public WirelessHidDiscoveryClient(ObjectMapper objectMapper) {
        this(objectMapper, DEFAULT_PORT);
    }

    public WirelessHidDiscoveryClient(ObjectMapper objectMapper, int port) {
        this.objectMapper = objectMapper;
        this.port = port;
    }

    public List<WirelessHidDiscoveredDevice> discover(Duration timeout) throws IOException {
        Duration checkedTimeout = checkedTimeout(timeout);
        List<DiscoveryTarget> targets = interfaceTargets();
        if (targets.isEmpty()) {
            targets.add(new DiscoveryTarget(null, InetAddress.getByName("255.255.255.255")));
        }

        ExecutorService executor = Executors.newFixedThreadPool(
                Math.min(targets.size(), 16),
                runnable -> {
                    Thread thread = new Thread(runnable, "whid-discovery");
                    thread.setDaemon(true);
                    return thread;
                });
        try {
            List<Callable<List<WirelessHidDiscoveredDevice>>> tasks = targets.stream()
                    .<Callable<List<WirelessHidDiscoveredDevice>>>map(target ->
                            () -> discoverFrom(target.localAddress(), target.targetAddress(), checkedTimeout))
                    .toList();
            Map<String, WirelessHidDiscoveredDevice> byId = new LinkedHashMap<>();
            for (Future<List<WirelessHidDiscoveredDevice>> future : executor.invokeAll(tasks)) {
                try {
                    for (WirelessHidDiscoveredDevice device : future.get()) {
                        byId.put(device.id(), device);
                    }
                } catch (Exception ignored) {
                    // One VPN or virtual interface may fail while physical interfaces still work.
                }
            }
            return new ArrayList<>(byId.values());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("设备发现被中断", e);
        } finally {
            executor.shutdownNow();
        }
    }

    public List<WirelessHidDiscoveredDevice> discoverUnicast(
            String ip,
            Duration timeout) throws IOException {
        InetAddress target = requireIpv4(ip);
        return discoverFrom(null, target, checkedTimeout(timeout));
    }

    private List<WirelessHidDiscoveredDevice> discoverFrom(
            InetAddress localAddress,
            InetAddress targetAddress,
            Duration timeout) throws IOException {
        long deadline = System.nanoTime() + timeout.toNanos();
        Map<String, WirelessHidDiscoveredDevice> byId = new LinkedHashMap<>();
        InetSocketAddress bindAddress = localAddress == null
                ? new InetSocketAddress(0)
                : new InetSocketAddress(localAddress, 0);

        try (DatagramSocket socket = new DatagramSocket(bindAddress)) {
            socket.setBroadcast(true);
            DatagramPacket request = new DatagramPacket(
                    DISCOVERY_REQUEST,
                    DISCOVERY_REQUEST.length,
                    targetAddress,
                    port);
            socket.send(request);

            while (System.nanoTime() < deadline) {
                int remaining = (int) Math.max(
                        1,
                        Math.min(250, Duration.ofNanos(deadline - System.nanoTime()).toMillis()));
                socket.setSoTimeout(remaining);
                byte[] buffer = new byte[MAX_RESPONSE_SIZE];
                DatagramPacket response = new DatagramPacket(buffer, buffer.length);
                try {
                    socket.receive(response);
                } catch (SocketTimeoutException ignored) {
                    continue;
                }
                WirelessHidDiscoveredDevice parsed = parse(
                        response.getData(),
                        response.getLength(),
                        response.getAddress().getHostAddress());
                if (parsed != null) {
                    byId.put(parsed.id(), parsed);
                }
            }
        }
        return new ArrayList<>(byId.values());
    }

    private WirelessHidDiscoveredDevice parse(
            byte[] bytes,
            int length,
            String sourceIp) {
        try {
            JsonNode root = objectMapper.readTree(
                    new String(bytes, 0, length, StandardCharsets.UTF_8));
            if (!root.isObject()
                    || !root.path("protocol").canConvertToInt()
                    || root.path("protocol").asInt() != 1) {
                return null;
            }

            String id = requiredText(root, "id", 12);
            if (!id.matches("[0-9A-F]{12}")) {
                return null;
            }
            String name = requiredText(root, "name", 96);
            String reportedIp = requiredText(root, "ip", 64);
            String ip = isIpv4(reportedIp) && reportedIp.equals(sourceIp)
                    ? reportedIp
                    : sourceIp;
            int controlPort = requiredPort(root, "controlPort");
            int managementPort = requiredPort(root, "managementPort");
            String firmware = requiredText(root, "firmware", 32);
            if (!root.path("claimed").isBoolean()
                    || !root.path("ch9329").isBoolean()
                    || !root.path("rssi").canConvertToInt()) {
                return null;
            }
            int rssi = root.path("rssi").asInt();
            if (rssi < -127 || rssi > 0) {
                return null;
            }
            return new WirelessHidDiscoveredDevice(
                    1,
                    id,
                    name,
                    ip,
                    controlPort,
                    managementPort,
                    firmware,
                    root.path("claimed").asBoolean(),
                    root.path("ch9329").asBoolean(),
                    rssi);
        } catch (Exception ignored) {
            return null;
        }
    }

    private static String requiredText(JsonNode root, String field, int maxLength) {
        JsonNode value = root.path(field);
        if (!value.isTextual() || value.asText().isBlank() || value.asText().length() > maxLength) {
            throw new IllegalArgumentException("字段无效: " + field);
        }
        return value.asText();
    }

    private static int requiredPort(JsonNode root, String field) {
        JsonNode value = root.path(field);
        if (!value.canConvertToInt()) {
            throw new IllegalArgumentException("端口字段无效: " + field);
        }
        int port = value.asInt();
        if (port < 1 || port > 65535) {
            throw new IllegalArgumentException("端口超出范围: " + field);
        }
        return port;
    }

    private static List<DiscoveryTarget> interfaceTargets() throws IOException {
        List<DiscoveryTarget> result = new ArrayList<>();
        for (NetworkInterface networkInterface
                : Collections.list(NetworkInterface.getNetworkInterfaces())) {
            try {
                if (!networkInterface.isUp() || networkInterface.isLoopback()) {
                    continue;
                }
            } catch (Exception ignored) {
                continue;
            }
            for (InterfaceAddress interfaceAddress : networkInterface.getInterfaceAddresses()) {
                InetAddress local = interfaceAddress.getAddress();
                if (!(local instanceof Inet4Address)) {
                    continue;
                }
                InetAddress broadcast = interfaceAddress.getBroadcast();
                result.add(new DiscoveryTarget(
                        local,
                        broadcast != null
                                ? broadcast
                                : InetAddress.getByName("255.255.255.255")));
            }
        }
        return result;
    }

    private static Duration checkedTimeout(Duration timeout) {
        if (timeout == null
                || timeout.compareTo(Duration.ofMillis(100)) < 0
                || timeout.compareTo(Duration.ofSeconds(5)) > 0) {
            throw new IllegalArgumentException("发现超时必须在 100 到 5000 毫秒之间");
        }
        return timeout;
    }

    public static InetAddress requireIpv4(String ip) throws IOException {
        if (!isIpv4(ip)) {
            throw new IllegalArgumentException("必须提供合法的 IPv4 地址");
        }
        return InetAddress.getByName(ip);
    }

    private static boolean isIpv4(String ip) {
        if (ip == null || !ip.matches("\\d{1,3}(\\.\\d{1,3}){3}")) {
            return false;
        }
        String[] parts = ip.split("\\.");
        for (String part : parts) {
            try {
                int value = Integer.parseInt(part);
                if (value < 0 || value > 255) {
                    return false;
                }
            } catch (NumberFormatException e) {
                return false;
            }
        }
        return true;
    }

    private record DiscoveryTarget(InetAddress localAddress, InetAddress targetAddress) {
    }
}
