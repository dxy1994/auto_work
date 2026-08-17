package com.auto.whid.sdk;

import java.util.Arrays;

/** Wireless HID V1 TCP message types. */
public enum WirelessHidMessageType {
    CLAIM(0x01),
    RELEASE(0x02),
    HEARTBEAT(0x03),
    GET_STATUS(0x04),
    STATUS(0x05),
    KEYBOARD(0x10),
    MOUSE_REL(0x11),
    MOUSE_ABS(0x12),
    RELEASE_ALL(0x13),
    ACK(0x70),
    ERROR(0x71);

    private final int code;

    WirelessHidMessageType(int code) {
        this.code = code;
    }

    public int code() {
        return code;
    }

    public static WirelessHidMessageType fromCode(int code) throws WirelessHidException {
        return Arrays.stream(values())
                .filter(value -> value.code == code)
                .findFirst()
                .orElseThrow(() -> new WirelessHidException(
                        "不支持的 Wireless HID 消息类型: 0x%02X".formatted(code)));
    }
}
