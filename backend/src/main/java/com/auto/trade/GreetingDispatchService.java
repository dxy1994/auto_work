package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.GameItemOrderDetail;
import com.auto.entity.GameScript;
import com.auto.entity.RegionScript;
import com.auto.service.GameItemOrderDetailService;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameScriptService;
import com.auto.service.RegionScriptService;
import com.auto.trade.statemachine.DeliveryEvent;
import com.auto.trade.statemachine.OrderDeliveryStateMachine;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 订单招呼派发：查话术 → 下发 WS 指令 → 处理回馈。 */
@Service
public class GreetingDispatchService {

    private static final Logger log = LoggerFactory.getLogger(GreetingDispatchService.class);
    private static final int MAX_ERROR_MESSAGE_LENGTH = 500;

    private final RegionScriptService regionScriptService;
    private final GameScriptService gameScriptService;
    private final ChatDispatchService chatDispatchService;
    private final GameItemOrderService orderService;
    private final GameItemOrderDetailService orderDetailService;
    private final TradeDispatchCoordinator tradeDispatchCoordinator;
    private final OrderDeliveryStateMachine stateMachine;

    public GreetingDispatchService(
            RegionScriptService regionScriptService,
            GameScriptService gameScriptService,
            ChatDispatchService chatDispatchService,
            GameItemOrderService orderService,
            GameItemOrderDetailService orderDetailService,
            TradeDispatchCoordinator tradeDispatchCoordinator,
            OrderDeliveryStateMachine stateMachine) {
        this.regionScriptService = regionScriptService;
        this.gameScriptService = gameScriptService;
        this.chatDispatchService = chatDispatchService;
        this.orderService = orderService;
        this.orderDetailService = orderDetailService;
        this.tradeDispatchCoordinator = tradeDispatchCoordinator;
        this.stateMachine = stateMachine;
    }

    /** 派发招呼：查话术 + 下发 WS 指令（异步，不阻塞订单入库）。 */
    public void dispatch(int machineId, int orderId, int gameId, int regionId,
                         int websiteId, int accountId, String sourceOrderNo, String platform) {
        // 查话术：游戏话术列表（基础）+ 大区话术列表（补充），按 sort_order 排序发送
        List<Map<String, Object>> scripts = new ArrayList<>();

        // 1. 游戏话术（基础，总要查询）
        if (gameId != -1) {
            for (GameScript gs : gameScriptService.findAllByGameIdAndCategory(gameId, "招呼")) {
                if ((gs.getContent() != null && !gs.getContent().isEmpty())
                        || (gs.getImageUrl() != null && !gs.getImageUrl().isEmpty())) {
                    Map<String, Object> item = new LinkedHashMap<>();
                    if (gs.getContent() != null && !gs.getContent().isEmpty()) {
                        item.put("content", gs.getContent());
                    }
                    if (gs.getImageUrl() != null && !gs.getImageUrl().isEmpty()) {
                        item.put("image_url", gs.getImageUrl());
                    }
                    scripts.add(item);
                }
            }
        }

        // 2. 大区话术（补充，追加在游戏话术列表后）
        if (regionId != -1) {
            for (RegionScript rs : regionScriptService.findAllByRegionIdAndCategory(regionId, "招呼")) {
                if ((rs.getContent() != null && !rs.getContent().isEmpty())
                        || (rs.getImageUrl() != null && !rs.getImageUrl().isEmpty())) {
                    Map<String, Object> item = new LinkedHashMap<>();
                    if (rs.getContent() != null && !rs.getContent().isEmpty()) {
                        item.put("content", rs.getContent());
                    }
                    if (rs.getImageUrl() != null && !rs.getImageUrl().isEmpty()) {
                        item.put("image_url", rs.getImageUrl());
                    }
                    scripts.add(item);
                }
            }
        }

        GameItemOrder order = orderService.getById(orderId);
        if (order == null) {
            log.warn("[Greeting] 订单不存在 order_id={}", orderId);
            return;
        }

        if (scripts.isEmpty()) {
            log.warn("[Greeting] 未找到招呼话术 order_id={} game_id={} region_id={}; 原因：没有匹配且启用的话术；"
                            + "解决方案：在招呼话术管理中新增或启用对应游戏和大区的话术",
                    orderId, gameId, regionId);
            stateMachine.fire(order, DeliveryEvent.NO_GREETING_SCRIPT, null);
            return;
        }

        try {
            ChatDispatchService.DispatchReceipt receipt =
                    chatDispatchService.dispatchGreeting(
                            machineId,
                            orderId,
                            websiteId,
                            accountId,
                            sourceOrderNo,
                            platform,
                            scripts);
            log.info(
                    "[Greeting] 已通过聊天指令下发 machine_id={} order_id={} request_id={}",
                    machineId,
                    orderId,
                    receipt.requestId());
        } catch (RuntimeException e) {
            log.warn("[Greeting] 聊天指令下发失败 machine_id={} order_id={}; 原因：{}；"
                            + "解决方案：检查平台聊天配置、来源账号和监控机器连接后重试",
                    machineId, orderId, e.getMessage());
            stateMachine.fire(order, DeliveryEvent.GREETING_SEND_FAILED, null);
        }
    }

    /** 处理机器回馈的招呼结果，通过状态机驱动后续流程。 */
    public void handleResult(int orderId, boolean success, String message) {
        try {
            handleResultInternal(orderId, success, message);
        } catch (RuntimeException e) {
            persistProcessingError(orderId, e);
            throw e;
        }
    }

    private void handleResultInternal(int orderId, boolean success, String message) {
        GameItemOrder order = orderService.getById(orderId);
        if (order == null) {
            log.warn("[Greeting] 招呼回馈找不到订单 order_id={}", orderId);
            return;
        }
        if (!"greeting".equals(order.getDeliveryStatus())) {
            log.info("[Greeting] 订单状态已变更 order_id={} current={}, 忽略迟到回馈",
                    orderId, order.getDeliveryStatus());
            return;
        }

        if (!success) {
            String failureMessage = TradeErrorGuidance.ensureGuidance(
                    "GREETING_EXECUTION_FAILED", normalizeErrorMessage(message, "招呼执行失败"));
            log.warn("[Greeting] 招呼执行失败（保持greeting状态） order_id={} message={}",
                    orderId, failureMessage);
            stateMachine.fire(order, DeliveryEvent.GREETING_FAILED,
                    Map.of(
                            "message", failureMessage,
                            "errorCode", "GREETING_EXECUTION_FAILED",
                            "errorMessage", failureMessage));
            return;
        }

        try {
            continueAfterGreetingSuccess(order);
        } catch (Exception e) {
            log.warn("[Greeting] 自动交易指派失败 order_id={}; 原因：{}；"
                            + "解决方案：检查可用游戏执行机器、账号、大区和库存关联后重试",
                    orderId, e.getMessage());
            orderService.updateLastError(orderId, "TRADE_DISPATCH_FAILED",
                    TradeErrorGuidance.ensureGuidance("TRADE_DISPATCH_FAILED",
                            normalizeErrorMessage(e.getMessage(), "招呼成功，但自动交易指派失败")));
        }
    }

    /**
     * 执行招呼成功后原本应该执行的逻辑，不再次发送招呼。
     * 同时供正常招呼回馈和人工恢复流程复用，避免两条流程发生偏差。
     */
    public TradeOffer continueAfterGreetingSuccess(int orderId) {
        GameItemOrder order = orderService.getById(orderId);
        if (order == null) {
            throw new IllegalStateException("订单不存在");
        }
        if (!"greeting".equals(order.getDeliveryStatus())
                || !"pending".equals(order.getStatus())) {
            throw new IllegalStateException("订单不在招呼成功后的待继续状态");
        }
        TradeOffer offer = continueAfterGreetingSuccess(order);
        return offer;
    }

    private TradeOffer continueAfterGreetingSuccess(GameItemOrder order) {
        int orderId = order.getId();
        List<GameItemOrderDetail> details = orderDetailService.findByOrderId(orderId);
        if (details.isEmpty()) {
            log.warn("[Greeting] 招呼成功但子订单未解析 order_id={}; 原因：物品名称/编码未匹配或套装无子物品；"
                    + "解决方案：核对平台标题中的 %物品名或编码% 和游戏物品配置后重试", orderId);
            stateMachine.fire(order, DeliveryEvent.NO_SUB_ORDER, null);
            return null;
        }

        // 子订单已解析：由交易协调器完成 greeting → offered 的唯一状态迁移。
        TradeOffer offer = tradeDispatchCoordinator.dispatch(orderId);
        if (offer == null) {
            GameItemOrder queued = orderService.getById(orderId);
            log.info("[Greeting] 自动交易进入机器队列 order_id={} machine_id={}",
                    orderId, queued == null ? null : queued.getAssignedMachineId());
            return null;
        }
        log.info("[Greeting] 自动交易指派已发起 order_id={} assignment_id={} machine_id={}",
                orderId, offer.assignmentId(), offer.machineId());
        return offer;
    }

    private void persistProcessingError(int orderId, RuntimeException error) {
        String errorMessage = TradeErrorGuidance.ensureGuidance(
                "GREETING_RESULT_PROCESSING_ERROR",
                normalizeErrorMessage(error.getMessage(),
                        "处理招呼回馈异常: " + error.getClass().getSimpleName()));
        try {
            orderService.updateLastError(orderId, "GREETING_RESULT_PROCESSING_ERROR", errorMessage);
        } catch (Exception persistError) {
            log.error("[Greeting] 招呼回馈异常信息落库失败 order_id={}; 原因：{}；"
                            + "解决方案：检查订单表字段和数据库迁移，随后人工核对该订单状态",
                    orderId, persistError.getMessage(), persistError);
        }
    }

    private String normalizeErrorMessage(String message, String fallback) {
        String value = message == null || message.isBlank() ? fallback : message.trim();
        return value.length() <= MAX_ERROR_MESSAGE_LENGTH
                ? value
                : value.substring(0, MAX_ERROR_MESSAGE_LENGTH);
    }
}
