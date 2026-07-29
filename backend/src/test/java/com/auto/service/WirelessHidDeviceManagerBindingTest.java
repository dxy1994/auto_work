package com.auto.service;

import com.auto.entity.Machine;
import com.auto.entity.MouseKeyboardDevice;
import com.auto.service.WirelessHidDeviceManager.WorkerBinding;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.anyInt;

class WirelessHidDeviceManagerBindingTest {

    private MouseKeyboardDeviceService deviceService;
    private MachineService machineService;
    private WirelessHidDeviceManager manager;

    @BeforeEach
    void setUp() {
        deviceService = mock(MouseKeyboardDeviceService.class);
        machineService = mock(MachineService.class);
        manager = new WirelessHidDeviceManager(
                deviceService,
                machineService,
                new ObjectMapper());
    }

    @Test
    void unboundMachineReturnsWaitingStateWithoutGuessingADevice() throws Exception {
        Machine machine = machine(7, null);
        when(machineService.getById(7)).thenReturn(machine);

        assertNull(manager.prepareWorkerBinding(7));
        verify(deviceService, never()).getById(anyInt());
    }

    @Test
    void boundMachineReturnsStableDeviceIdentityAndAddress() throws Exception {
        Machine machine = machine(7, 2);
        MouseKeyboardDevice device = new MouseKeyboardDevice();
        device.setId(2);
        device.setName("二号键鼠");
        device.setDeviceType(WirelessHidDeviceManager.DEVICE_TYPE);
        device.setIsActive(1);
        device.setDeviceInfo("""
                {
                  "protocol": 1,
                  "deviceId": "AABBCCDDEEFF",
                  "name": "二号键鼠",
                  "ip": "192.168.1.32",
                  "controlPort": 39667,
                  "managementPort": 39668,
                  "firmware": "1.0.0",
                  "claimed": false,
                  "ch9329": true,
                  "rssi": -42,
                  "lastSeen": null
                }
                """);
        when(machineService.getById(7)).thenReturn(machine);
        when(deviceService.getById(2)).thenReturn(device);

        WorkerBinding binding = manager.prepareWorkerBinding(7);

        assertEquals(2, binding.recordId());
        assertEquals("AABBCCDDEEFF", binding.deviceId());
        assertEquals("192.168.1.32", binding.ip());
        assertEquals(39667, binding.controlPort());
    }

    private Machine machine(int id, Integer mkDeviceId) {
        Machine machine = new Machine();
        machine.setId(id);
        machine.setIsActive(1);
        machine.setMkDeviceId(mkDeviceId);
        return machine;
    }
}
