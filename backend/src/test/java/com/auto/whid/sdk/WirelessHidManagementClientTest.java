package com.auto.whid.sdk;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class WirelessHidManagementClientTest {

    @Test
    void calculatesProofWithBinaryVerifierKey() throws Exception {
        char[] pin = "123456".toCharArray();

        String proof = WirelessHidManagementClient.calculateProof(
                "284E4F1B5BF8",
                pin,
                "00112233445566778899aabbccddeeff");

        assertEquals(
                "bbbcb6514a44582eb434711fd52532b294caf2ca72801eb3707b148875458ee4",
                proof);
    }

    @Test
    void rejectsNonEspFirmware() {
        IllegalArgumentException error = assertThrows(
                IllegalArgumentException.class,
                () -> WirelessHidManagementClient.validateFirmware(
                        new byte[]{0x7F, 1, 2, 3}));

        assertEquals(true, error.getMessage().contains("0xE9"));
    }
}
