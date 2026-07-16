package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.GameScript;
import com.auto.entity.RegionScript;
import com.auto.entity.TradeEvent;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameScriptService;
import com.auto.service.RegionScriptService;
import com.auto.service.TradeEventService;
import com.auto.ws.AgentRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 订单招呼派发：查话术 → 下发 WS 指令 → 处理回馈。 */
@Service
public class GreetingDispatchService {

    private static final Logger log = LoggerFactory.getLogger(GreetingDispatchService.class);
    private static final String ITEMMANIA_CHAT_URL = "https://www.itemmania.com/myroom/chat/new_chat.html";

    private final RegionScriptService regionScriptService;
    private final GameScriptService gameScriptService;
    private final AgentRegistry agentRegistry;
    private final GameItemOrderService orderService;
    private final TradeEventService eventService;

    public GreetingDispatchService(
            RegionScriptService regionScriptService,
            GameScriptService gameScriptService,
            AgentRegistry agentRegistry,
            GameItemOrderService orderService,
            TradeEventService eventService) {
        this.regionScriptService = regionScriptService;
        this.gameScriptService = gameScriptService;
        this.agentRegistry = agentRegistry;
        this.orderService = orderService;
        this.eventService = eventService;
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

        if (scripts.isEmpty()) {
            log.warn("[Greeting] 未找到招呼话术 order_id={} game_id={} region_id={}, 直接跳过招呼",
                    orderId, gameId, regionId);
            updateOrderStatus(orderId, "waiting_assignment", null, null);
            return;
        }

        // 构造聊天页面 URL（仅 itemmania 使用 Web 聊天）
        String chatUrl = null;
        if ("itemmania".equals(platform)) {
            chatUrl = ITEMMANIA_CHAT_URL + "?tid=" + sourceOrderNo + "&type=sell&c_type=apl";
        }

        boolean sent = agentRegistry.sendGreeting(machineId, orderId, websiteId, accountId, scripts, chatUrl);
        if (!sent) {
            log.warn("[Greeting] 招呼指令下发失败 machine_id={} order_id={}", machineId, orderId);
            updateOrderStatus(orderId, "suspended", "GREETING_FAILED", "招呼指令下发失败（机器离线）");
        } else {
            log.info("[Greeting] 招呼指令已下发 machine_id={} order_id={} chat_url={}", machineId, orderId, chatUrl);
        }
    }

    /** 处理机器回馈的招呼结果，更新订单状态。 */
    @Transactional
    public void handleResult(int orderId, boolean success, String message) {
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

        String targetStatus;
        String errorCode = null;
        String errorMessage = null;
        if (success) {
            targetStatus = "waiting_assignment";
        } else {
            targetStatus = "suspended";
            errorCode = "GREETING_FAILED";
            errorMessage = message != null ? message : "招呼执行失败";
        }

        String fromStatus = order.getDeliveryStatus();
        order.setDeliveryStatus(targetStatus);
        if (errorCode != null) {
            order.setLastErrorCode(errorCode);
            order.setLastErrorMessage(errorMessage);
        }
        orderService.updateById(order);

        TradeEvent event = new TradeEvent();
        event.setOrderId(orderId);
        event.setEventType("greeting_result");
        event.setFromStatus(fromStatus);
        event.setToStatus(targetStatus);
        event.setMessage(message);
        eventService.save(event);

        log.info("[Greeting] 招呼结果已处理 order_id={} success={} status={}→{}",
                orderId, success, fromStatus, targetStatus);
    }

    private void updateOrderStatus(int orderId, String targetStatus, String errorCode, String errorMessage) {
        GameItemOrder order = orderService.getById(orderId);
        if (order == null || !"greeting".equals(order.getDeliveryStatus())) {
            return;
        }
        String fromStatus = order.getDeliveryStatus();
        order.setDeliveryStatus(targetStatus);
        if (errorCode != null) {
            order.setLastErrorCode(errorCode);
            order.setLastErrorMessage(errorMessage);
        }
        orderService.updateById(order);

        TradeEvent event = new TradeEvent();
        event.setOrderId(orderId);
        event.setEventType("greeting_result");
        event.setFromStatus(fromStatus);
        event.setToStatus(targetStatus);
        event.setMessage(errorMessage);
        eventService.save(event);
    }
}
