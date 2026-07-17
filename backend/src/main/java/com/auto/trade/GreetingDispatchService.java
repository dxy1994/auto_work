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
import com.auto.ws.AgentRegistry;
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
    private static final String ITEMMANIA_CHAT_URL = "https://www.itemmania.com/myroom/chat/new_chat.html";

    private final RegionScriptService regionScriptService;
    private final GameScriptService gameScriptService;
    private final AgentRegistry agentRegistry;
    private final GameItemOrderService orderService;
    private final GameItemOrderDetailService orderDetailService;
    private final TradeDispatchCoordinator tradeDispatchCoordinator;
    private final OrderDeliveryStateMachine stateMachine;

    public GreetingDispatchService(
            RegionScriptService regionScriptService,
            GameScriptService gameScriptService,
            AgentRegistry agentRegistry,
            GameItemOrderService orderService,
            GameItemOrderDetailService orderDetailService,
            TradeDispatchCoordinator tradeDispatchCoordinator,
            OrderDeliveryStateMachine stateMachine) {
        this.regionScriptService = regionScriptService;
        this.gameScriptService = gameScriptService;
        this.agentRegistry = agentRegistry;
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
            log.warn("[Greeting] 未找到招呼话术 order_id={} game_id={} region_id={}, 标记为异常",
                    orderId, gameId, regionId);
            stateMachine.fire(order, DeliveryEvent.NO_GREETING_SCRIPT, null);
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
            stateMachine.fire(order, DeliveryEvent.GREETING_SEND_FAILED, null);
        } else {
            log.info("[Greeting] 招呼指令已下发 machine_id={} order_id={} chat_url={}", machineId, orderId, chatUrl);
        }
    }

    /** 处理机器回馈的招呼结果，通过状态机驱动后续流程。 */
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

        if (!success) {
            log.warn("[Greeting] 招呼执行失败（保持greeting状态） order_id={} message={}",
                    orderId, message);
            stateMachine.fire(order, DeliveryEvent.GREETING_FAILED,
                    Map.of("message", message != null ? message : "招呼执行失败"));
            return;
        }

        // 招呼成功：检查子订单，决定后续流程
        List<GameItemOrderDetail> details = orderDetailService.findByOrderId(orderId);

        if (details.isEmpty()) {
            log.warn("[Greeting] 招呼成功但子订单未解析 order_id={}，标记异常", orderId);
            stateMachine.fire(order, DeliveryEvent.NO_SUB_ORDER, null);
            return;
        }

        // 子订单已解析：通过状态机转入 offered，然后自动发起交易指派
        stateMachine.fire(order, DeliveryEvent.GREETING_SUCCESS,
                Map.of("message", "招呼成功，开始自动交易指派"));

        try {
            TradeOffer offer = tradeDispatchCoordinator.dispatch(orderId);
            log.info("[Greeting] 自动交易指派已发起 order_id={} assignment_id={} machine_id={}",
                    orderId, offer.assignmentId(), offer.machineId());
        } catch (Exception e) {
            log.warn("[Greeting] 自动交易指派失败 order_id={}: {}", orderId, e.getMessage());
        }
    }
}
