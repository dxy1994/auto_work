package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.entity.SystemControl;
import com.auto.service.SystemControlService;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class SystemControlControllerTest {

    @Test
    void updatesAutoGameTradeControlAndReturnsPersistedState() {
        SystemControlService service = mock(SystemControlService.class);
        SystemControl control = new SystemControl();
        control.setId(SystemControl.SINGLETON_ID);
        control.setAutoGameTradeEnabled(0);
        control.setUpdatedAt(LocalDateTime.of(2026, 7, 29, 21, 0));
        when(service.updateAutoGameTradeEnabled(false)).thenReturn(control);
        SystemControlController controller = new SystemControlController(service);

        Map<String, Object> response = controller.updateControl(
                new SystemControlController.UpdateControlRequest(false));

        assertEquals(false, response.get("auto_game_trade_enabled"));
        assertEquals(control.getUpdatedAt(), response.get("updated_at"));
        verify(service).updateAutoGameTradeEnabled(false);
    }

    @Test
    void rejectsMissingAutoGameTradeControlValue() {
        SystemControlController controller =
                new SystemControlController(mock(SystemControlService.class));

        ApiException error = assertThrows(
                ApiException.class,
                () -> controller.updateControl(
                        new SystemControlController.UpdateControlRequest(null)));

        assertEquals("是否执行自动游戏交易不能为空", error.getMessage());
    }
}
