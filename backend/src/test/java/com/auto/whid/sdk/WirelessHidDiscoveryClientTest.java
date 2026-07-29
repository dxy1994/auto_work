package com.auto.whid.sdk;

import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;

class WirelessHidDiscoveryClientTest {

    @Test
    void discoversAndValidatesUnicastResponse() throws Exception {
        try (DatagramSocket deviceSocket =
                     new DatagramSocket(0, InetAddress.getByName("127.0.0.1"))) {
            CompletableFuture<Void> responder = CompletableFuture.runAsync(() -> {
                try {
                    DatagramPacket request = new DatagramPacket(new byte[128], 128);
                    deviceSocket.receive(request);
                    String json = """
                            {
                              "protocol": 1,
                              "id": "284E4F1B5BF8",
                              "name": "WirelessHID-5BF8",
                              "ip": "192.168.6.167",
                              "controlPort": 39667,
                              "managementPort": 39668,
                              "firmware": "0.1.0",
                              "claimed": false,
                              "ch9329": true,
                              "rssi": -25
                            }
                            """;
                    byte[] response = json.getBytes(StandardCharsets.UTF_8);
                    deviceSocket.send(new DatagramPacket(
                            response,
                            response.length,
                            request.getAddress(),
                            request.getPort()));
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            });

            WirelessHidDiscoveryClient client =
                    new WirelessHidDiscoveryClient(new ObjectMapper(), deviceSocket.getLocalPort());
            List<WirelessHidDiscoveredDevice> devices = client.discoverUnicast(
                    "127.0.0.1",
                    Duration.ofMillis(400));

            assertEquals(1, devices.size());
            assertEquals("284E4F1B5BF8", devices.get(0).id());
            assertEquals("127.0.0.1", devices.get(0).ip());
            responder.get(1, TimeUnit.SECONDS);
        }
    }
}
