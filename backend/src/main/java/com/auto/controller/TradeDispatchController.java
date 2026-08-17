package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.entity.GameItemOrder;
import com.auto.service.GameItemOrderService;
import com.auto.trade.TradeDispatchCoordinator;
import com.auto.trade.TradeOffer;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

/** 第一阶段交易指派的受控验证接口。 */
@RestController
@RequestMapping("/api/trades")
public class TradeDispatchController {

    private final TradeDispatchCoordinator coordinator;
    private final GameItemOrderService orderService;

    public TradeDispatchController(
            TradeDispatchCoordinator coordinator,
            GameItemOrderService orderService) {
        this.coordinator = coordinator;
        this.orderService = orderService;
    }

    @PostMapping("/{orderId}/dispatch")
    public Map<String, Object> dispatch(@PathVariable Integer orderId) {
        try {
            TradeOffer offer = coordinator.dispatch(orderId);
            Map<String, Object> response = new LinkedHashMap<>();
            if (offer == null) {
                GameItemOrder queued = orderService.getById(orderId);
                response.put("assignment_id", null);
                response.put("order_id", orderId);
                response.put("machine_id", queued == null ? null : queued.getAssignedMachineId());
                response.put("game_account_id", queued == null ? null : queued.getGameAccountId());
                response.put("lease_expires_at", null);
                response.put("delivery_status", "queued");
                return response;
            }
            response.put("assignment_id", offer.assignmentId());
            response.put("order_id", offer.orderId());
            response.put("machine_id", offer.machineId());
            response.put("game_account_id", offer.gameAccountId());
            response.put("lease_expires_at", offer.leaseExpiresAt());
            response.put("delivery_status", "offered");
            return response;
        } catch (IllegalStateException e) {
            throw ApiException.conflict(e.getMessage());
        }
    }

    @GetMapping("/{orderId}/status")
    public Map<String, Object> status(@PathVariable Integer orderId) {
        GameItemOrder order = orderService.getById(orderId);
        if (order == null) {
            throw ApiException.notFound("订单不存在");
        }
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("order_id", order.getId());
        response.put("assignment_id", order.getAssignmentId());
        response.put("delivery_status", order.getDeliveryStatus());
        response.put("last_error_code", order.getLastErrorCode());
        response.put("last_error_message", order.getLastErrorMessage());
        return response;
    }
}
