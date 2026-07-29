package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.entity.SystemControl;
import com.auto.service.SystemControlService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/system-controls")
public class SystemControlController {

    private final SystemControlService controlService;

    public SystemControlController(SystemControlService controlService) {
        this.controlService = controlService;
    }

    @GetMapping
    public Map<String, Object> getControl() {
        return toResponse(controlService.getControl());
    }

    @PutMapping
    public Map<String, Object> updateControl(@RequestBody UpdateControlRequest request) {
        if (request == null || request.autoGameTradeEnabled() == null) {
            throw ApiException.badRequest("是否执行自动游戏交易不能为空");
        }
        return toResponse(controlService.updateAutoGameTradeEnabled(
                request.autoGameTradeEnabled()));
    }

    private Map<String, Object> toResponse(SystemControl control) {
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("auto_game_trade_enabled",
                Integer.valueOf(1).equals(control.getAutoGameTradeEnabled()));
        response.put("updated_at", control.getUpdatedAt());
        return response;
    }

    public record UpdateControlRequest(Boolean autoGameTradeEnabled) {
    }
}
