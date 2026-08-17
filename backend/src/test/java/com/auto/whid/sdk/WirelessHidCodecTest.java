package com.auto.whid.sdk;

import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.util.HexFormat;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class WirelessHidCodecTest {

    @Test
    void encodesDocumentedKeyboardExample() {
        byte[] payload = new byte[]{0, 0, 4, 0, 0, 0, 0, 0};

        byte[] encoded = WirelessHidCodec.encode(
                WirelessHidMessageType.KEYBOARD,
                1,
                payload);

        assertEquals(
                "5748494401100800010000007f9db3fe0000040000000000",
                HexFormat.of().formatHex(encoded));
    }

    @Test
    void roundTripsUnsignedSequenceAndPayload() throws IOException {
        byte[] payload = new byte[]{1, -128, 127, -1};
        byte[] encoded = WirelessHidCodec.encode(
                WirelessHidMessageType.MOUSE_REL,
                0xFFFF_FFFEL,
                payload);

        WirelessHidFrame decoded = WirelessHidCodec.decode(encoded);

        assertEquals(WirelessHidMessageType.MOUSE_REL, decoded.type());
        assertEquals(0xFFFF_FFFEL, decoded.sequence());
        assertArrayEquals(payload, decoded.payload());
    }

    @Test
    void rejectsCorruptedPayload() {
        byte[] encoded = WirelessHidCodec.encode(
                WirelessHidMessageType.KEYBOARD,
                7,
                new byte[8]);
        encoded[encoded.length - 1] = 1;

        WirelessHidException error = assertThrows(
                WirelessHidException.class,
                () -> WirelessHidCodec.decode(encoded));

        assertEquals(true, error.getMessage().contains("CRC32"));
    }
}
