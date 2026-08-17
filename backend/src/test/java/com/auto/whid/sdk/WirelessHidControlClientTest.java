package com.auto.whid.sdk;

import org.junit.jupiter.api.Test;

import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class WirelessHidControlClientTest {

    @Test
    void claimsHeartbeatsControlsAndReleases() throws Exception {
        AtomicReference<byte[]> keyboardPayload = new AtomicReference<>();
        AtomicInteger heartbeatCount = new AtomicInteger();
        try (ServerSocket server = new ServerSocket(
                0,
                1,
                InetAddress.getByName("127.0.0.1"))) {
            CompletableFuture<Void> device = CompletableFuture.runAsync(() -> {
                try (Socket socket = server.accept()) {
                    while (true) {
                        WirelessHidFrame frame = WirelessHidCodec.read(socket.getInputStream());
                        WirelessHidMessageType type = frame.type();
                        byte[] payload;
                        WirelessHidMessageType responseType;
                        if (type == WirelessHidMessageType.GET_STATUS) {
                            payload = ByteBuffer.allocate(8)
                                    .order(ByteOrder.LITTLE_ENDIAN)
                                    .put((byte) 1)
                                    .put((byte) 1)
                                    .put((byte) -42)
                                    .put((byte) 0)
                                    .putInt(1234)
                                    .array();
                            responseType = WirelessHidMessageType.STATUS;
                        } else if (type == WirelessHidMessageType.HEARTBEAT) {
                            heartbeatCount.incrementAndGet();
                            payload = new byte[0];
                            responseType = WirelessHidMessageType.HEARTBEAT;
                        } else {
                            if (type == WirelessHidMessageType.KEYBOARD
                                    && keyboardPayload.get() == null) {
                                keyboardPayload.set(frame.payload());
                            }
                            payload = new byte[]{(byte) type.code(), 0, 0, 0};
                            responseType = WirelessHidMessageType.ACK;
                        }
                        socket.getOutputStream().write(WirelessHidCodec.encode(
                                responseType,
                                frame.sequence(),
                                payload));
                        socket.getOutputStream().flush();
                        if (type == WirelessHidMessageType.RELEASE) {
                            break;
                        }
                    }
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            });

            WirelessHidControlClient client = new WirelessHidControlClient(
                    "127.0.0.1",
                    server.getLocalPort());
            client.connectAndClaim();
            client.sendKeyboard(0, 0x04);
            WirelessHidControlClient.Status status = client.getStatus();
            Thread.sleep(1200);
            client.disconnect();

            assertArrayEquals(
                    new byte[]{0, 0, 4, 0, 0, 0, 0, 0},
                    keyboardPayload.get());
            assertTrue(status.claimed());
            assertTrue(status.ch9329Online());
            assertEquals(-42, status.wifiRssi());
            assertEquals(1234, status.uptimeSeconds());
            assertTrue(heartbeatCount.get() >= 1);
            device.get(2, TimeUnit.SECONDS);
        }
    }
}
