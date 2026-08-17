package com.auto.whid.sdk;

import java.io.IOException;

/** A protocol, device status, or management API error. */
public class WirelessHidException extends IOException {

    private final Integer deviceStatus;
    private final Integer httpStatus;

    public WirelessHidException(String message) {
        this(message, null, null, null);
    }

    public WirelessHidException(String message, Throwable cause) {
        this(message, null, null, cause);
    }

    public WirelessHidException(String message, Integer deviceStatus, Integer httpStatus) {
        this(message, deviceStatus, httpStatus, null);
    }

    public WirelessHidException(
            String message,
            Integer deviceStatus,
            Integer httpStatus,
            Throwable cause) {
        super(message, cause);
        this.deviceStatus = deviceStatus;
        this.httpStatus = httpStatus;
    }

    public Integer getDeviceStatus() {
        return deviceStatus;
    }

    public Integer getHttpStatus() {
        return httpStatus;
    }
}
