package com.auto.whid.sdk;

import java.io.Closeable;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.time.Instant;
import java.util.Arrays;
import java.util.Set;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/** Stateful TCP control connection with serialized requests and an independent heartbeat. */
public final class WirelessHidControlClient implements Closeable {

    public static final int DEFAULT_PORT = 39667;
    private static final int CONNECT_TIMEOUT_MS = 2000;
    private static final int RESPONSE_TIMEOUT_MS = 1500;
    private static final byte[] EMPTY = new byte[0];

    private final String host;
    private final int port;
    private final ScheduledExecutorService scheduler;
    private final AtomicReference<String> lastError = new AtomicReference<>();

    private Socket socket;
    private InputStream input;
    private OutputStream output;
    private long nextSequence = 1;
    private ScheduledFuture<?> heartbeatTask;
    private volatile boolean claimed;
    private volatile Instant lastHeartbeatAt;

    public WirelessHidControlClient(String host, int port) {
        if (host == null || host.isBlank()) {
            throw new IllegalArgumentException("host 不能为空");
        }
        if (port < 1 || port > 65535) {
            throw new IllegalArgumentException("port 超出范围");
        }
        this.host = host;
        this.port = port;
        this.scheduler = Executors.newSingleThreadScheduledExecutor(runnable -> {
            Thread thread = new Thread(runnable, "whid-heartbeat-" + host);
            thread.setDaemon(true);
            return thread;
        });
    }

    public synchronized void connectAndClaim() throws IOException {
        if (isOpen()) {
            return;
        }
        Socket newSocket = new Socket();
        try {
            newSocket.connect(new InetSocketAddress(host, port), CONNECT_TIMEOUT_MS);
            newSocket.setTcpNoDelay(true);
            newSocket.setSoTimeout(RESPONSE_TIMEOUT_MS);
            socket = newSocket;
            input = newSocket.getInputStream();
            output = newSocket.getOutputStream();
            nextSequence = 1;
            request(
                    WirelessHidMessageType.CLAIM,
                    EMPTY,
                    Set.of(WirelessHidMessageType.ACK));
            claimed = true;
            lastError.set(null);
            heartbeatTask = scheduler.scheduleAtFixedRate(
                    this::heartbeatSafely,
                    1,
                    1,
                    TimeUnit.SECONDS);
        } catch (IOException | RuntimeException e) {
            closeSocket();
            throw e;
        }
    }

    public synchronized Status getStatus() throws IOException {
        WirelessHidFrame response = request(
                WirelessHidMessageType.GET_STATUS,
                EMPTY,
                Set.of(WirelessHidMessageType.STATUS));
        byte[] payload = response.payload();
        if (payload.length != 8) {
            throw new WirelessHidException("STATUS 负载长度必须为 8");
        }
        if (payload[3] != 0) {
            throw new WirelessHidException("STATUS reserved 字段不为 0");
        }
        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        int claimedValue = Byte.toUnsignedInt(buffer.get());
        int onlineValue = Byte.toUnsignedInt(buffer.get());
        int wifiRssi = buffer.get();
        buffer.get();
        long uptimeSeconds = Integer.toUnsignedLong(buffer.getInt());
        if ((claimedValue != 0 && claimedValue != 1)
                || (onlineValue != 0 && onlineValue != 1)
                || wifiRssi < -127
                || wifiRssi > 0) {
            throw new WirelessHidException("STATUS 状态字段超出协议范围");
        }
        return new Status(
                claimedValue == 1,
                onlineValue == 1,
                wifiRssi,
                uptimeSeconds,
                lastHeartbeatAt);
    }

    public synchronized void sendKeyboard(int modifier, int... keys) throws IOException {
        if (modifier < 0 || modifier > 0xFF) {
            throw new IllegalArgumentException("modifier 必须在 0..255");
        }
        if (keys == null || keys.length > 6) {
            throw new IllegalArgumentException("键盘报告最多包含 6 个按键");
        }
        byte[] payload = new byte[8];
        payload[0] = (byte) modifier;
        for (int index = 0; index < keys.length; index++) {
            if (keys[index] < 0 || keys[index] > 0xFF) {
                throw new IllegalArgumentException("HID Usage ID 必须在 0..255");
            }
            payload[index + 2] = (byte) keys[index];
        }
        expectAck(WirelessHidMessageType.KEYBOARD, payload);
    }

    public void tapKeyboard(int modifier, int... keys) throws IOException {
        try {
            sendKeyboard(modifier, keys);
        } finally {
            sendKeyboard(0);
        }
    }

    public void typeText(String text, int delayMillis) throws IOException {
        if (text == null || text.isEmpty()) {
            throw new IllegalArgumentException("输入文本不能为空");
        }
        if (text.length() > 500) {
            throw new IllegalArgumentException("单次输入文本不能超过 500 个字符");
        }
        if (delayMillis < 0 || delayMillis > 1000) {
            throw new IllegalArgumentException("按键间隔必须在 0..1000 毫秒");
        }
        try {
            for (char character : text.toCharArray()) {
                HidKeyboard.Keystroke key = HidKeyboard.forCharacter(character);
                tapKeyboard(key.modifier(), key.usageId());
                if (delayMillis > 0) {
                    try {
                        Thread.sleep(delayMillis);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        throw new IOException("文本输入被中断", e);
                    }
                }
            }
        } catch (IOException | RuntimeException e) {
            try {
                releaseAll();
            } catch (IOException ignored) {
                // Preserve the original failure.
            }
            throw e;
        }
    }

    public synchronized void sendRelativeMouse(
            int buttons,
            int x,
            int y,
            int wheel) throws IOException {
        requireByteRange("buttons", buttons, 0, 7);
        requireByteRange("x", x, -128, 127);
        requireByteRange("y", y, -128, 127);
        requireByteRange("wheel", wheel, -128, 127);
        expectAck(
                WirelessHidMessageType.MOUSE_REL,
                new byte[]{(byte) buttons, (byte) x, (byte) y, (byte) wheel});
    }

    public synchronized void sendAbsoluteMouse(
            int buttons,
            int x,
            int y,
            int wheel) throws IOException {
        requireByteRange("buttons", buttons, 0, 7);
        requireByteRange("x", x, 0, 4095);
        requireByteRange("y", y, 0, 4095);
        requireByteRange("wheel", wheel, -128, 127);
        ByteBuffer payload = ByteBuffer.allocate(6).order(ByteOrder.LITTLE_ENDIAN);
        payload.put((byte) buttons);
        payload.putShort((short) x);
        payload.putShort((short) y);
        payload.put((byte) wheel);
        expectAck(WirelessHidMessageType.MOUSE_ABS, payload.array());
    }

    public synchronized void releaseAll() throws IOException {
        expectAck(WirelessHidMessageType.RELEASE_ALL, EMPTY);
    }

    public void disconnect() throws IOException {
        ScheduledFuture<?> heartbeat = heartbeatTask;
        if (heartbeat != null) {
            heartbeat.cancel(false);
        }
        IOException failure = null;
        if (isOpen() && claimed) {
            try {
                releaseAll();
                synchronized (this) {
                    expectAck(WirelessHidMessageType.RELEASE, EMPTY);
                }
            } catch (IOException e) {
                failure = e;
            }
        }
        claimed = false;
        closeSocket();
        scheduler.shutdownNow();
        if (failure != null) {
            throw failure;
        }
    }

    public boolean isOpen() {
        Socket current = socket;
        return current != null && current.isConnected() && !current.isClosed() && claimed;
    }

    public Instant getLastHeartbeatAt() {
        return lastHeartbeatAt;
    }

    public String getLastError() {
        return lastError.get();
    }

    @Override
    public void close() {
        try {
            disconnect();
        } catch (IOException ignored) {
            closeSocket();
        }
    }

    private synchronized WirelessHidFrame request(
            WirelessHidMessageType requestType,
            byte[] payload,
            Set<WirelessHidMessageType> expectedTypes) throws IOException {
        if (socket == null || socket.isClosed()) {
            throw new IOException("Wireless HID 控制连接尚未建立");
        }
        long sequence = takeSequence();
        output.write(WirelessHidCodec.encode(requestType, sequence, payload));
        output.flush();
        WirelessHidFrame response = WirelessHidCodec.read(input);
        if (response.sequence() != sequence) {
            throw new WirelessHidException(
                    "响应 sequence 不匹配: expected=%d actual=%d"
                            .formatted(sequence, response.sequence()));
        }
        if (response.type() == WirelessHidMessageType.ERROR) {
            throw parseAckError(response, requestType);
        }
        if (!expectedTypes.contains(response.type())) {
            throw new WirelessHidException(
                    "响应类型不正确: expected=%s actual=%s"
                            .formatted(expectedTypes, response.type()));
        }
        if (response.type() == WirelessHidMessageType.ACK) {
            validateAck(response.payload(), requestType);
        }
        return response;
    }

    private void expectAck(WirelessHidMessageType requestType, byte[] payload) throws IOException {
        request(requestType, payload, Set.of(WirelessHidMessageType.ACK));
    }

    private void heartbeatSafely() {
        try {
            synchronized (this) {
                request(
                        WirelessHidMessageType.HEARTBEAT,
                        EMPTY,
                        Set.of(WirelessHidMessageType.HEARTBEAT));
                lastHeartbeatAt = Instant.now();
            }
        } catch (Exception e) {
            lastError.compareAndSet(null, "心跳失败: " + safeMessage(e));
            claimed = false;
            closeSocket();
            ScheduledFuture<?> heartbeat = heartbeatTask;
            if (heartbeat != null) {
                heartbeat.cancel(false);
            }
        }
    }

    private static void validateAck(byte[] payload, WirelessHidMessageType requestType)
            throws WirelessHidException {
        if (payload.length != 4) {
            throw new WirelessHidException("ACK 负载长度必须为 4");
        }
        int actualRequestType = Byte.toUnsignedInt(payload[0]);
        int status = Byte.toUnsignedInt(payload[1]);
        if (actualRequestType != requestType.code()) {
            throw new WirelessHidException("ACK requestType 与请求不匹配");
        }
        if (payload[2] != 0 || payload[3] != 0) {
            throw new WirelessHidException("ACK reserved 字段不为 0");
        }
        if (status != 0) {
            throw statusException(status);
        }
    }

    private static WirelessHidException parseAckError(
            WirelessHidFrame frame,
            WirelessHidMessageType requestType) {
        byte[] payload = frame.payload();
        if (payload.length != 4) {
            return new WirelessHidException("ERROR 负载长度必须为 4");
        }
        if (Byte.toUnsignedInt(payload[0]) != requestType.code()) {
            return new WirelessHidException("ERROR requestType 与请求不匹配");
        }
        return statusException(Byte.toUnsignedInt(payload[1]));
    }

    private static WirelessHidException statusException(int status) {
        String description = switch (status) {
            case 1 -> "设备正被其他控制端占用";
            case 2 -> "尚未取得设备控制权";
            case 3 -> "设备拒绝了无效帧";
            case 4 -> "设备拒绝了无效负载";
            case 5 -> "CH9329 不在线或无响应";
            case 6 -> "固件不支持该消息类型";
            default -> "设备返回未知状态码 " + status;
        };
        return new WirelessHidException(description, status, null);
    }

    private synchronized long takeSequence() {
        long sequence = nextSequence;
        nextSequence = (nextSequence + 1) & 0xFFFF_FFFFL;
        if (nextSequence == 0) {
            nextSequence = 1;
        }
        return sequence;
    }

    private synchronized void closeSocket() {
        claimed = false;
        if (socket != null) {
            try {
                socket.close();
            } catch (IOException ignored) {
                // Best effort during failure cleanup.
            }
        }
        socket = null;
        input = null;
        output = null;
    }

    private static void requireByteRange(String name, int value, int minimum, int maximum) {
        if (value < minimum || value > maximum) {
            throw new IllegalArgumentException(
                    "%s 必须在 %d..%d".formatted(name, minimum, maximum));
        }
    }

    private static String safeMessage(Exception exception) {
        return exception.getMessage() == null
                ? exception.getClass().getSimpleName()
                : exception.getMessage();
    }

    public record Status(
            boolean claimed,
            boolean ch9329Online,
            int wifiRssi,
            long uptimeSeconds,
            Instant lastHeartbeatAt) {
    }
}
