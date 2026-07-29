package com.auto.whid.sdk;

/** One decoded Wireless HID V1 TCP frame. */
public record WirelessHidFrame(
        WirelessHidMessageType type,
        long sequence,
        byte[] payload) {

    public WirelessHidFrame {
        if (type == null) {
            throw new IllegalArgumentException("type 不能为空");
        }
        payload = payload == null ? new byte[0] : payload.clone();
    }

    @Override
    public byte[] payload() {
        return payload.clone();
    }
}
