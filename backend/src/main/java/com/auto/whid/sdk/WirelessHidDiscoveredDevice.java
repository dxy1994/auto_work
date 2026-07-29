package com.auto.whid.sdk;

/** Validated UDP discovery response. */
public record WirelessHidDiscoveredDevice(
        int protocol,
        String id,
        String name,
        String ip,
        int controlPort,
        int managementPort,
        String firmware,
        boolean claimed,
        boolean ch9329,
        int rssi) {
}
