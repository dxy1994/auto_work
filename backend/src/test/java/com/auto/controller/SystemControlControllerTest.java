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
        control.setPageGuidesVisible(1);
        control.setUpdatedAt(LocalDateTime.of(2026, 7, 29, 21, 0));
        when(service.updateControls(false, null)).thenReturn(control);
        SystemControlController controller = new SystemControlController(service);

        Map<String, Object> response = controller.updateControl(
                new SystemControlController.UpdateControlRequest(false, null));

        assertEquals(false, response.get("auto_game_trade_enabled"));
        assertEquals(true, response.get("page_guides_visible"));
        assertEquals(control.getUpdatedAt(), response.get("updated_at"));
        verify(service).updateControls(false, null);
    }

    @Test
    void updatesPageGuideVisibilityWithoutChangingTradeControl() {
        SystemControlService service = mock(SystemControlService.class);
        SystemControl control = new SystemControl();
        control.setId(SystemControl.SINGLETON_ID);
        control.setAutoGameTradeEnabled(1);
        control.setPageGuidesVisible(0);
        when(service.updateControls(null, false)).thenReturn(control);
        SystemControlController controller = new SystemControlController(service);

        Map<String, Object> response = controller.updateControl(
                new SystemControlController.UpdateControlRequest(null, false));

        assertEquals(true, response.get("auto_game_trade_enabled"));
        assertEquals(false, response.get("page_guides_visible"));
        verify(service).updateControls(null, false);
    }

    @Test
    void rejectsMissingAutoGameTradeControlValue() {
        SystemControlController controller =
                new SystemControlController(mock(SystemControlService.class));

        ApiException error = assertThrows(
                ApiException.class,
                () -> controller.updateControl(
                        new SystemControlController.UpdateControlRequest(null, null)));

        assertEquals("至少提供一项系统控制设置", error.getMessage());
    }
}
