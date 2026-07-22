package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.*;
import com.auto.service.*;
import com.auto.trade.GreetingDispatchRequested;
import com.auto.trade.GreetingDispatchService;
import com.auto.trade.ManualOrderStatusService;
import com.auto.trade.OrderRecoveryService;
import com.auto.trade.TradeDispatchCoordinator;
import com.auto.trade.statemachine.DeliveryEvent;
import com.auto.trade.statemachine.DeliveryState;
import com.auto.trade.statemachine.OrderDeliveryStateMachine;
import com.auto.ws.AgentRegistry;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.http.HttpStatus;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import tools.jackson.databind.ObjectMapper;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.*;

/** 订单管理（主子表联动）。 */
@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private static final Set<String> DELETABLE_STATUSES = Set.of("pending", "abnormal", "cancelled");
    private static final Set<String> ORDER_STATUSES =
            Set.of("pending", "assigned", "processing", "completed", "cancelled");
    private static final Set<String> DETAIL_STATUSES =
            Set.of("pending", "processing", "completed", "failed");
    private static final Set<DeliveryState> COPY_INITIAL_STATES =
            EnumSet.of(DeliveryState.DETECTED, DeliveryState.GREETING,
                    DeliveryState.GREETING_ABNORMAL, DeliveryState.WAITING_ASSIGNMENT,
                    DeliveryState.SUSPENDED);
    private static final java.time.format.DateTimeFormatter TS =
            java.time.format.DateTimeFormatter.ofPattern("yyyyMMddHHmmss");

    enum RetryStage {
        GREETING,
        SUB_ORDER_GENERATION,
        ASSIGNMENT
    }

    private final GameItemOrderService orderService;
    private final GameItemOrderDetailService detailService;
    private final GameItemService itemService;
    private final GameRegionService regionService;
    private final GameRegionInventoryService inventoryService;
    private final GameRegionInventoryShopPriceService shopPriceService;
    private final ApplicationEventPublisher eventPublisher;
    private final PlatformAccountService accountService;
    private final MachinePlatformAccountService machinePlatformAccountService;
    private final PlatformService websiteService;
    private final AgentRegistry registry;
    private final ObjectMapper objectMapper;
    private final OrderDeliveryStateMachine deliveryStateMachine;
    private final TradeAssignmentService tradeAssignmentService;
    private final TradeDispatchCoordinator tradeCoordinator;
    private final OrderRecoveryService orderRecoveryService;
    private final GreetingDispatchService greetingDispatchService;
    private final ManualOrderStatusService manualOrderStatusService;
    private final TradeEventService tradeEventService;

    public OrderController(GameItemOrderService orderService, GameItemOrderDetailService detailService,
                           GameItemService itemService, GameRegionService regionService,
                           GameRegionInventoryService inventoryService,
                           GameRegionInventoryShopPriceService shopPriceService,
                           ApplicationEventPublisher eventPublisher,
                           PlatformAccountService accountService,
                           MachinePlatformAccountService machinePlatformAccountService,
                           PlatformService websiteService,
                           AgentRegistry registry,
                           ObjectMapper objectMapper,
                           OrderDeliveryStateMachine deliveryStateMachine,
                           TradeAssignmentService tradeAssignmentService,
                           TradeDispatchCoordinator tradeCoordinator,
                           OrderRecoveryService orderRecoveryService,
                           GreetingDispatchService greetingDispatchService,
                           ManualOrderStatusService manualOrderStatusService,
                           TradeEventService tradeEventService) {
        this.orderService = orderService;
        this.detailService = detailService;
        this.itemService = itemService;
        this.regionService = regionService;
        this.inventoryService = inventoryService;
        this.shopPriceService = shopPriceService;
        this.eventPublisher = eventPublisher;
        this.accountService = accountService;
        this.machinePlatformAccountService = machinePlatformAccountService;
        this.websiteService = websiteService;
        this.registry = registry;
        this.objectMapper = objectMapper;
        this.deliveryStateMachine = deliveryStateMachine;
        this.tradeAssignmentService = tradeAssignmentService;
        this.tradeCoordinator = tradeCoordinator;
        this.orderRecoveryService = orderRecoveryService;
        this.greetingDispatchService = greetingDispatchService;
        this.manualOrderStatusService = manualOrderStatusService;
        this.tradeEventService = tradeEventService;
    }

    private String genOrderNo() {
        return LocalDateTime.now().format(TS) + UUID.randomUUID().toString().replace("-", "").substring(0, 8).toUpperCase();
    }

    /** 以订单明细为准重算总额。 */
    private void recalculateOrderTotal(GameItemOrder order) {
        BigDecimal total = detailService.sumSubtotalByOrderId(order.getId());
        order.setTotalAmount(total != null ? total : BigDecimal.ZERO);
    }

    /** 组装订单详情响应：订单字段（snake_case）+ details 列表。 */
    @SuppressWarnings("unchecked")
    private Map<String, Object> toFullMap(GameItemOrder order, List<GameItemOrderDetail> details) {
        Map<String, Object> map = objectMapper.convertValue(order, Map.class);
        map.put("details", details);
        TradeAssignment review = latestBuyerReview(order.getId());
        map.put("buyer_review", review == null ? null : toBuyerReviewMap(review));
        appendRetryMetadata(map, order);
        return map;
    }

    // ── 订单主表 CRUD ────────────────────────────────────────────

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "game_id", required = false) Integer gameId,
            @RequestParam(name = "status", required = false) String status,
            @RequestParam(name = "delivery_status", required = false) String deliveryStatus,
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize) {
        IPage<GameItemOrder> result = orderService.search(
                gameId, status, deliveryStatus, keyword, PageRequests.of(page, pageSize));
        List<Map<String, Object>> items = result.getRecords().stream()
                .map(this::toOrderListMap)
                .toList();
        return Map.of("total", result.getTotal(), "items", items);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> toOrderListMap(GameItemOrder order) {
        Map<String, Object> map = objectMapper.convertValue(order, Map.class);
        map.remove("game_trade_screenshot");
        map.remove("gameTradeScreenshot");
        appendRetryMetadata(map, order);
        return map;
    }

    private static void appendRetryMetadata(Map<String, Object> map, GameItemOrder order) {
        try {
            RetryStage stage = resolveRetryStage(order);
            map.put("retryable", true);
            map.put("retry_stage", stage.name().toLowerCase(Locale.ROOT));
        } catch (ApiException ignored) {
            map.put("retryable", false);
            map.put("retry_stage", null);
        }
    }

    /**
     * 全局待人工处理消息。不提供“已读即消失”语义；
     * 只有订单真正离开异常状态，该提示才会消失。
     */
    @GetMapping("/manual-alerts")
    public Map<String, Object> manualAlerts() {
        LambdaQueryWrapper<GameItemOrder> query = manualAlertQuery()
                .orderByAsc(GameItemOrder::getUpdatedAt)
                .last("LIMIT 200");
        List<Map<String, Object>> items = new ArrayList<>(orderService.list(query).stream()
                .map(this::toManualAlert)
                .toList());
        List<TradeAssignment> buyerReviews = tradeAssignmentService.list(
                new LambdaQueryWrapper<TradeAssignment>()
                        .eq(TradeAssignment::getBuyerReviewStatus, "pending")
                        .orderByAsc(TradeAssignment::getBuyerReviewRequestedAt)
                        .last("LIMIT 200"));
        buyerReviews.stream().map(this::toBuyerReviewAlert).forEach(items::add);
        items.sort(Comparator.comparing(
                item -> String.valueOf(item.getOrDefault("occurred_at", ""))));
        long total = orderService.count(manualAlertQuery())
                + tradeAssignmentService.count(new LambdaQueryWrapper<TradeAssignment>()
                        .eq(TradeAssignment::getBuyerReviewStatus, "pending"));
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("total", total);
        response.put("items", items);
        response.put("polled_at", LocalDateTime.now());
        return response;
    }

    private LambdaQueryWrapper<GameItemOrder> manualAlertQuery() {
        return new LambdaQueryWrapper<GameItemOrder>()
                .notIn(GameItemOrder::getStatus, "completed", "cancelled")
                .and(q -> q.and(greeting -> greeting
                                .eq(GameItemOrder::getDeliveryStatus, "greeting")
                                .eq(GameItemOrder::getStatus, "abnormal"))
                        .or().in(GameItemOrder::getDeliveryStatus,
                                "suspended", "review_required"));
    }

    private Map<String, Object> toManualAlert(GameItemOrder order) {
        String deliveryStatus = order.getDeliveryStatus();
        String title;
        String severity;
        if ("review_required".equals(deliveryStatus)) {
            title = "交易结果需要人工复核";
            severity = "critical";
        } else if ("suspended".equals(deliveryStatus)) {
            title = "订单交付已挂起";
            severity = "danger";
        } else {
            title = "订单招呼异常";
            severity = "warning";
        }
        String message = order.getLastErrorMessage();
        if (message == null || message.isBlank()) {
            message = switch (deliveryStatus) {
                case "review_required" -> "交易结果不确定，请核对游戏和平台订单";
                case "suspended" -> "自动交付无法继续，请人工处理";
                default -> "请检查招呼话术、订单明细或 Worker 状态";
            };
        }
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", "order:" + order.getId());
        item.put("entity_type", "order");
        item.put("entity_id", order.getId());
        item.put("order_no", order.getOrderNo());
        item.put("source_order_no", order.getSourceOrderNo());
        item.put("buyer_character", order.getBuyerCharacter());
        item.put("delivery_status", deliveryStatus);
        item.put("order_status", order.getStatus());
        item.put("severity", severity);
        item.put("title", title);
        item.put("message", message);
        item.put("error_code", order.getLastErrorCode());
        item.put("occurred_at", order.getUpdatedAt());
        return item;
    }

    private Map<String, Object> toBuyerReviewAlert(TradeAssignment assignment) {
        GameItemOrder order = orderService.getById(assignment.getOrderId());
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", "buyer_review:" + assignment.getBuyerReviewId());
        item.put("entity_type", "buyer_review");
        item.put("entity_id", assignment.getOrderId());
        item.put("assignment_id", assignment.getAssignmentId());
        item.put("review_id", assignment.getBuyerReviewId());
        item.put("order_no", order == null ? null : order.getOrderNo());
        item.put("source_order_no", order == null ? null : order.getSourceOrderNo());
        item.put("buyer_character", assignment.getExpectedBuyerName());
        item.put("expected_buyer", assignment.getExpectedBuyerName());
        item.put("observed_buyer", assignment.getObservedBuyerName());
        item.put("ocr_confidence", assignment.getBuyerOcrConfidence());
        item.put("screenshot_data_url", assignment.getBuyerReviewScreenshot());
        item.put("severity", "critical");
        item.put("title", "交易客户需要人工确认");
        item.put("message", "OCR 置信度不足或玩家名不匹配，请根据用户名和游戏截图决定是否接受交易");
        item.put("occurred_at", assignment.getBuyerReviewRequestedAt());
        return item;
    }

    private TradeAssignment latestBuyerReview(Integer orderId) {
        return tradeAssignmentService.getOne(
                new LambdaQueryWrapper<TradeAssignment>()
                        .eq(TradeAssignment::getOrderId, orderId)
                        .isNotNull(TradeAssignment::getBuyerReviewId)
                        .orderByDesc(
                                TradeAssignment::getBuyerReviewRequestedAt,
                                TradeAssignment::getId)
                        .last("LIMIT 1"), false);
    }

    private Map<String, Object> toBuyerReviewMap(TradeAssignment assignment) {
        Map<String, Object> review = new LinkedHashMap<>();
        review.put("review_id", assignment.getBuyerReviewId());
        review.put("status", assignment.getBuyerReviewStatus());
        review.put("expected_buyer", assignment.getExpectedBuyerName());
        review.put("observed_buyer", assignment.getObservedBuyerName());
        review.put("ocr_confidence", assignment.getBuyerOcrConfidence());
        review.put("screenshot_data_url", assignment.getBuyerReviewScreenshot());
        review.put("requested_at", assignment.getBuyerReviewRequestedAt());
        review.put("decided_at", assignment.getBuyerReviewDecidedAt());
        return review;
    }

    @GetMapping("/{orderId}")
    public Map<String, Object> get(@PathVariable Integer orderId) {
        GameItemOrder o = orderService.getById(orderId);
        if (o == null) throw ApiException.notFound("订单不存在");
        return toFullMap(o, detailService.findByOrderIdOrderById(orderId));
    }

    /** 查询订单关联的自动交付事件，最新事件优先，最多返回 200 条。 */
    @GetMapping("/{orderId}/logs")
    public Map<String, Object> logs(@PathVariable Integer orderId) {
        GameItemOrder order = orderService.getById(orderId);
        if (order == null) throw ApiException.notFound("订单不存在");

        LambdaQueryWrapper<TradeEvent> condition = new LambdaQueryWrapper<TradeEvent>()
                .eq(TradeEvent::getOrderId, orderId);
        long total = tradeEventService.count(condition);
        List<TradeEvent> items = tradeEventService.list(
                new LambdaQueryWrapper<TradeEvent>()
                        .eq(TradeEvent::getOrderId, orderId)
                        .orderByDesc(TradeEvent::getCreatedAt, TradeEvent::getId)
                        .last("LIMIT 200"));

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("order_id", orderId);
        response.put("order_no", order.getOrderNo());
        response.put("total", total);
        response.put("items", items);
        return response;
    }

    @PostMapping("/{orderId}/buyer-review")
    public Map<String, Object> decideBuyerReview(
            @PathVariable Integer orderId,
            @RequestBody Map<String, Object> body) {
        String reviewId = body.get("review_id") == null
                ? null : body.get("review_id").toString();
        if (reviewId == null || reviewId.isBlank() || !(body.get("approved") instanceof Boolean)) {
            throw ApiException.badRequest("review_id 和 approved 不能为空");
        }
        try {
            TradeAssignment assignment = tradeCoordinator.decideBuyerReview(
                    orderId, reviewId, Boolean.TRUE.equals(body.get("approved")));
            return Map.of(
                    "review_id", reviewId,
                    "status", assignment.getBuyerReviewStatus(),
                    "message", Boolean.TRUE.equals(body.get("approved"))
                            ? "已同意，交易流程继续" : "已拒绝，Worker 将继续等待买家");
        } catch (IllegalStateException e) {
            throw ApiException.conflict(e.getMessage());
        }
    }

    /** 按失败阶段继续执行；不会重新执行已经成功完成的前置步骤。 */
    @PostMapping("/{orderId}/retry")
    public Map<String, Object> retry(@PathVariable Integer orderId) {
        GameItemOrder order = orderService.getById(orderId);
        if (order == null) throw ApiException.notFound("订单不存在");

        RetryStage stage = resolveRetryStage(order);
        if (stage == RetryStage.GREETING) {
            return retryGreeting(order, "订单失败后人工重新尝试");
        }

        boolean recoveredSubOrder = false;
        if (stage == RetryStage.SUB_ORDER_GENERATION) {
            try {
                orderRecoveryService.recoverMissingSubOrder(orderId);
                recoveredSubOrder = true;
            } catch (IllegalStateException e) {
                throw ApiException.badRequest("子订单生成仍未完成：" + e.getMessage());
            }
        }

        if (stage == RetryStage.ASSIGNMENT) {
            if ("suspended".equals(order.getDeliveryStatus())
                    || "greeting".equals(order.getDeliveryStatus())) {
                deliveryStateMachine.fire(
                        order,
                        DeliveryEvent.RETRY_ASSIGNMENT,
                        Map.of("message", "恢复到交易指派出错前的状态"));
            }
        }
        try {
            var offer = recoveredSubOrder
                    ? greetingDispatchService.continueAfterGreetingSuccess(orderId)
                    : tradeCoordinator.dispatch(orderId);
            Map<String, Object> response = new LinkedHashMap<>();
            if (offer == null) {
                GameItemOrder queued = orderService.getById(orderId);
                response.put("status", "queued");
                response.put("stage", "assignment_queue");
                response.put("assignment_id", null);
                response.put("machine_id", queued == null ? null : queued.getAssignedMachineId());
                response.put("message", "目标交易机器正在执行前序订单，当前订单已按时间进入队列");
                return response;
            }
            response.put("status", "started");
            response.put("stage", "assignment");
            response.put("assignment_id", offer.assignmentId());
            response.put("machine_id", offer.machineId());
            response.put("message", recoveredSubOrder
                    ? "子订单已生成，已从交易指派阶段继续执行"
                    : "已从交易指派阶段继续执行");
            return response;
        } catch (IllegalStateException e) {
            GameItemOrder latest = orderService.getById(orderId);
            if (latest != null
                    && "abnormal".equals(latest.getStatus())
                    && "SUB_ORDER_MISSING".equals(latest.getLastErrorCode())) {
                throw ApiException.badRequest("子订单生成仍未完成：" + e.getMessage());
            }
            String message = recoveredSubOrder
                    ? "子订单已生成，但交易指派尚未完成：" + e.getMessage()
                    : e.getMessage();
            orderService.updateLastError(orderId, "TRADE_DISPATCH_FAILED", message);
            throw ApiException.conflict(message);
        }
    }

    static RetryStage resolveRetryStage(GameItemOrder order) {
        String status = order.getStatus();
        if ("completed".equals(status) || "cancelled".equals(status)) {
            throw ApiException.badRequest("订单已" + ("completed".equals(status) ? "完成" : "取消") + "，不能重新尝试");
        }

        String deliveryStatus = order.getDeliveryStatus();
        if ("review_required".equals(deliveryStatus)) {
            throw ApiException.conflict("交易结果不确定，请先人工复核，不能直接重新尝试");
        }
        if ("offered".equals(deliveryStatus) || "assigned".equals(deliveryStatus)) {
            throw ApiException.conflict("订单仍在交易执行中，请勿重复尝试");
        }
        if ("wait_web_confirm".equals(deliveryStatus)) {
            throw ApiException.conflict("游戏内交易已经完成，当前仅等待网站确认，不能重新执行交易");
        }
        if ("waiting_assignment".equals(deliveryStatus)) {
            return RetryStage.ASSIGNMENT;
        }
        if ("suspended".equals(deliveryStatus)) {
            if (order.getAssignmentId() != null) {
                return RetryStage.ASSIGNMENT;
            }
            if (Set.of("GREETING_FAILED", "GREETING_SEND_FAILED")
                    .contains(order.getLastErrorCode())) {
                return RetryStage.GREETING;
            }
            throw ApiException.badRequest("该异常需要先修正订单配置，不能直接重新尝试");
        }
        if ("greeting".equals(deliveryStatus)) {
            if ("abnormal".equals(status)) {
                if ("SUB_ORDER_MISSING".equals(order.getLastErrorCode())) {
                    return RetryStage.SUB_ORDER_GENERATION;
                }
                return RetryStage.GREETING;
            }
            if ("TRADE_DISPATCH_FAILED".equals(order.getLastErrorCode())) {
                return RetryStage.ASSIGNMENT;
            }
            if (order.getLastErrorCode() != null) {
                return RetryStage.GREETING;
            }
            throw ApiException.badRequest("订单当前没有可重新尝试的失败步骤");
        }
        throw ApiException.badRequest("当前交付状态不支持重新尝试: " + deliveryStatus);
    }

    /** 重新招呼：适用于订单交付状态为 greeting 且总订单未完成/未取消。 */
    @PostMapping("/{orderId}/re-greeting")
    @Transactional
    public Map<String, Object> reGreeting(@PathVariable Integer orderId) {
        GameItemOrder order = orderService.getById(orderId);
        if (order == null) throw ApiException.notFound("订单不存在");

        if (!"greeting".equals(order.getDeliveryStatus())) {
            throw ApiException.badRequest("当前交付状态不是待招呼，无法重新招呼");
        }
        String orderStatus = order.getStatus();
        if ("completed".equals(orderStatus) || "cancelled".equals(orderStatus)) {
            throw ApiException.badRequest("订单已" + ("completed".equals(orderStatus) ? "完成" : "取消") + "，无法重新招呼");
        }

        return retryGreeting(order, "人工重新招呼");
    }

    private Map<String, Object> retryGreeting(GameItemOrder order, String reason) {
        // 严格使用订单来源平台账号，避免同一平台多账号时串号发送招呼。
        Integer accountId = order.getPlatformAccountId();
        if (accountId == null) {
            throw ApiException.badRequest("历史订单缺少来源平台账号，请先补充 platform_account_id");
        }
        PlatformAccount sourceAccount = accountService.getById(accountId);
        if (sourceAccount == null
                || !order.getWebsiteId().equals(sourceAccount.getWebsiteId())
                || !Integer.valueOf(1).equals(sourceAccount.getIsActive())) {
            throw ApiException.badRequest("订单来源平台账号不存在、已停用或与来源平台不匹配");
        }

        Integer machineId = null;
        for (MachinePlatformAccount ma : machinePlatformAccountService.findByAccountIdActive(accountId)) {
            if (registry.pickAgent(ma.getMachineId()) != null) {
                machineId = ma.getMachineId();
                break;
            }
        }
        if (machineId == null) {
            throw ApiException.badRequest("订单来源账号没有已绑定且在线的 Web 端机器");
        }

        // 根据网站 URL 判断平台类型
        Platform website = websiteService.getById(order.getWebsiteId());
        String platform = "";
        if (website != null && website.getUrl() != null) {
            String url = website.getUrl();
            if (url.contains("itemmania")) platform = "itemmania";
            else if (url.contains("itembay")) platform = "itembay";
            else if (url.contains("barotem")) platform = "barotem";
        }

        // 所有前置条件都通过后再退出 abnormal；任何失败都保留告警。
        if ("abnormal".equals(order.getStatus())
                || "suspended".equals(order.getDeliveryStatus())) {
            deliveryStateMachine.fire(
                    order,
                    DeliveryEvent.RESET_TO_GREETING,
                    Map.of("message", reason));
        } else if ("greeting".equals(order.getDeliveryStatus())
                && order.getLastErrorCode() != null) {
            deliveryStateMachine.fire(
                    order,
                    DeliveryEvent.RETRY_GREETING,
                    Map.of("message", "恢复到招呼出错前的状态"));
        }

        eventPublisher.publishEvent(new GreetingDispatchRequested(
                machineId,
                order.getId(),
                order.getGameId() != null ? order.getGameId() : -1,
                order.getRegionId() != null ? order.getRegionId() : -1,
                order.getWebsiteId(),
                accountId,
                order.getSourceOrderNo() != null ? order.getSourceOrderNo() : "",
                platform));

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("status", "started");
        resp.put("stage", "greeting");
        resp.put("message", "已重新触发招呼");
        return resp;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @Transactional
    public Map<String, Object> create(@RequestBody OrderCreate payload) {
        validateCreate(payload);
        GameRegion region = regionService.getById(payload.regionId);
        if (region == null) {
            throw ApiException.badRequest("大区不存在: " + payload.regionId);
        }
        if (!payload.gameId.equals(region.getGameId())) {
            throw ApiException.badRequest("所选大区不属于订单游戏");
        }
        List<Integer> itemIds = payload.details.stream().map(d -> d.itemId).distinct().toList();
        Map<Integer, GameItem> itemsById = new LinkedHashMap<>();
        itemService.listByIds(itemIds).forEach(item -> itemsById.put(item.getId(), item));
        List<Integer> missingIds = itemIds.stream().filter(id -> !itemsById.containsKey(id)).toList();
        if (!missingIds.isEmpty()) {
            throw ApiException.badRequest("物品不存在: " + missingIds);
        }
        List<Integer> crossGameItemIds = itemsById.values().stream()
                .filter(item -> !payload.gameId.equals(item.getGameId()))
                .map(GameItem::getId).toList();
        if (!crossGameItemIds.isEmpty()) {
            throw ApiException.badRequest("物品不属于订单游戏: " + crossGameItemIds);
        }

        GameItemOrder order = new GameItemOrder();
        order.setOrderNo(genOrderNo());
        order.setGameId(payload.gameId);
        order.setRegionId(payload.regionId);
        order.setCustomerName(payload.customerName);
        order.setCustomerContact(payload.customerContact);
        order.setRemark(payload.remark);
        orderService.save(order);

        for (OrderDetailCreate d : payload.details) {
            GameItem item = itemsById.get(d.itemId);
            int qty = d.quantity != null ? d.quantity : 1;
            BigDecimal unitPrice = d.unitPrice != null ? d.unitPrice
                    : (item.getPrice() != null ? item.getPrice() : BigDecimal.ZERO);
            // 从大区物品库存获取进货价/出货价快照
            GameRegionInventory inventory = findInventory(payload.regionId, d.itemId);
            GameItemOrderDetail detail = new GameItemOrderDetail();
            detail.setOrderId(order.getId());
            detail.setItemId(d.itemId);
            detail.setItemName(item.getName());
            detail.setItemImage(item.getImage());
            detail.setItemSelectedImage(item.getSelectedImage());
            detail.setQuantity(qty);
            detail.setUnitPrice(unitPrice);
            detail.setSubtotal(unitPrice.multiply(BigDecimal.valueOf(qty)));
            if (inventory != null) {
                detail.setPurchasePrice(inventory.getPurchasePrice());
            }
            detail.setRemark(d.remark);
            detailService.save(detail);
        }
        recalculateOrderTotal(order);
        orderService.updateById(order);
        return toFullMap(order, detailService.findByOrderId(order.getId()));
    }

    /**
     * 复制既有订单。复制的是订单业务数据和子订单，不复制交易指派、错误、截图、完成时间等运行态数据。
     * 默认由前端传入 waiting_assignment|pending，表示招呼已经完成，可直接继续交易指派。
     */
    @PostMapping("/{orderId}/copy")
    @ResponseStatus(HttpStatus.CREATED)
    @Transactional
    public Map<String, Object> copy(@PathVariable Integer orderId, @RequestBody OrderCopy payload) {
        GameItemOrder source = orderService.getById(orderId);
        if (source == null) throw ApiException.notFound("原订单不存在");
        applyCopyNumberDefaults(payload, source);
        validateCopy(payload, source);

        GameRegion region = regionService.getById(payload.regionId);
        if (region == null) {
            throw ApiException.badRequest("大区不存在: " + payload.regionId);
        }
        if (!payload.gameId.equals(region.getGameId())) {
            throw ApiException.badRequest("所选大区不属于订单游戏");
        }
        validateCopyAccount(payload);

        List<Integer> itemIds = payload.details.stream().map(d -> d.itemId).distinct().toList();
        Map<Integer, GameItem> itemsById = new LinkedHashMap<>();
        itemService.listByIds(itemIds).forEach(item -> itemsById.put(item.getId(), item));
        List<Integer> missingIds = itemIds.stream().filter(id -> !itemsById.containsKey(id)).toList();
        if (!missingIds.isEmpty()) {
            throw ApiException.badRequest("物品不存在: " + missingIds);
        }
        List<Integer> crossGameItemIds = itemsById.values().stream()
                .filter(item -> !payload.gameId.equals(item.getGameId()))
                .map(GameItem::getId).toList();
        if (!crossGameItemIds.isEmpty()) {
            throw ApiException.badRequest("物品不属于订单游戏: " + crossGameItemIds);
        }

        DeliveryState initialState = DeliveryState.from(payload.deliveryStatus, payload.status);
        GameItemOrder order = new GameItemOrder();
        order.setOrderNo(payload.orderNo.trim());
        order.setWebsiteId(payload.websiteId);
        order.setPlatformAccountId(payload.platformAccountId);
        order.setSourceOrderNo(trimToNull(payload.sourceOrderNo));
        order.setGameId(payload.gameId);
        order.setRegionId(payload.regionId);
        order.setGameAccountId(payload.gameAccountId);
        order.setBuyerCharacter(payload.buyerCharacter);
        order.setAssetType(payload.assetType);
        order.setAssetAmount(payload.assetAmount);
        order.setDeliveryStatus(initialState.getDeliveryStatus());
        order.setStatus(initialState.getOrderStatus());
        order.setCustomerName(payload.customerName);
        order.setCustomerContact(payload.customerContact);
        order.setRemark(payload.remark);
        order.setPlatformOrderTime(payload.platformOrderTime);
        order.setPlatformPrice(payload.platformPrice);
        order.setPlatformItemType(payload.platformItemType);
        order.setProductTitle(payload.productTitle);
        order.setTradeItemName(payload.tradeItemName);
        order.setQuantity(payload.quantity);
        order.setSaleQuantity(payload.saleQuantity);
        orderService.save(order);

        for (OrderDetailCopy itemPayload : payload.details) {
            GameItem item = itemsById.get(itemPayload.itemId);
            int quantity = itemPayload.quantity != null ? itemPayload.quantity : 1;
            BigDecimal unitPrice = itemPayload.unitPrice != null ? itemPayload.unitPrice
                    : (item.getPrice() != null ? item.getPrice() : BigDecimal.ZERO);
            GameRegionInventory inventory = findInventory(payload.regionId, itemPayload.itemId);

            GameItemOrderDetail detail = new GameItemOrderDetail();
            detail.setOrderId(order.getId());
            detail.setItemId(item.getId());
            detail.setItemName(item.getName());
            detail.setItemImage(item.getImage());
            detail.setItemSelectedImage(item.getSelectedImage());
            detail.setQuantity(quantity);
            detail.setUnitPrice(unitPrice);
            detail.setSubtotal(unitPrice.multiply(BigDecimal.valueOf(quantity)));
            detail.setPurchasePrice(itemPayload.purchasePrice != null
                    ? itemPayload.purchasePrice
                    : inventory == null ? null : inventory.getPurchasePrice());
            detail.setSellingPrice(itemPayload.sellingPrice);
            detail.setStatus("pending");
            detail.setRemark(itemPayload.remark);
            detail.setBundleName(itemPayload.bundleName);
            detailService.save(detail);
        }
        recalculateOrderTotal(order);
        orderService.updateById(order);

        TradeEvent event = new TradeEvent();
        event.setOrderId(order.getId());
        event.setEventType("order_copied");
        event.setToStatus(order.getDeliveryStatus());
        event.setMessage("复制订单创建，默认从“招呼已完成”之后继续");
        event.setPayload(Map.of(
                "source_order_id", source.getId(),
                "source_order_no", source.getOrderNo() == null ? "" : source.getOrderNo()));
        tradeEventService.save(event);

        return toFullMap(order, detailService.findByOrderId(order.getId()));
    }

    @PutMapping("/{orderId}")
    public GameItemOrder update(@PathVariable Integer orderId, @RequestBody OrderUpdate payload) {
        if (payload == null) {
            throw ApiException.badRequest("请求参数不能为空");
        }
        if (payload.status != null && !ORDER_STATUSES.contains(payload.status)) {
            throw ApiException.badRequest("订单状态无效: " + payload.status);
        }
        GameItemOrder o = orderService.getById(orderId);
        if (o == null) throw ApiException.notFound("订单不存在");
        if (payload.customerName != null) o.setCustomerName(payload.customerName);
        if (payload.customerContact != null) o.setCustomerContact(payload.customerContact);
        if (payload.assignedMachineId != null) o.setAssignedMachineId(payload.assignedMachineId);
        if (payload.remark != null) o.setRemark(payload.remark);
        if (payload.status != null) {
            String newStatus = payload.status;
            if ("assigned".equals(newStatus) && "pending".equals(o.getStatus())) {
                o.setAssignedAt(LocalDateTime.now());
            } else if ("completed".equals(newStatus)) {
                o.setCompletedAt(LocalDateTime.now());
            }
            o.setStatus(newStatus);
        }
        orderService.updateById(o);
        return o;
    }

    @PostMapping("/{orderId}/complete")
    public GameItemOrder complete(@PathVariable Integer orderId) {
        try {
            GameItemOrder order = orderService.getById(orderId);
            if (order == null) throw new IllegalArgumentException("订单不存在");
            return Set.of("queued", "offered", "assigned").contains(order.getDeliveryStatus())
                    ? tradeCoordinator.completeOrderManually(orderId)
                    : manualOrderStatusService.complete(orderId);
        } catch (IllegalArgumentException e) {
            throw ApiException.notFound(e.getMessage());
        } catch (IllegalStateException e) {
            throw ApiException.badRequest(e.getMessage());
        }
    }

    @PostMapping("/{orderId}/cancel")
    public GameItemOrder cancel(@PathVariable Integer orderId) {
        try {
            GameItemOrder order = orderService.getById(orderId);
            if (order == null) throw new IllegalArgumentException("订单不存在");
            return Set.of("queued", "offered", "assigned").contains(order.getDeliveryStatus())
                    ? tradeCoordinator.cancelOrderManually(orderId)
                    : manualOrderStatusService.cancel(orderId);
        } catch (IllegalArgumentException e) {
            throw ApiException.notFound(e.getMessage());
        } catch (IllegalStateException e) {
            throw ApiException.badRequest(e.getMessage());
        }
    }

    @DeleteMapping("/{orderId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Transactional
    public void delete(@PathVariable Integer orderId) {
        GameItemOrder o = orderService.getById(orderId);
        if (o == null) throw ApiException.notFound("订单不存在");
        if (!DELETABLE_STATUSES.contains(o.getStatus())
                || ("pending".equals(o.getStatus())
                && Set.of("queued", "offered", "assigned", "review_required", "wait_web_confirm")
                        .contains(o.getDeliveryStatus()))) {
            throw ApiException.badRequest("只能删除未在交易中的待处理/异常订单，或已取消的订单");
        }
        List<GameItemOrderDetail> details = detailService.findByOrderId(orderId);
        if (!details.isEmpty()) {
            detailService.removeByIds(details.stream().map(GameItemOrderDetail::getId).toList());
        }
        orderService.removeById(orderId);
    }

    // ── 订单子表操作 ─────────────────────────────────────────────

    @PostMapping("/{orderId}/details")
    @ResponseStatus(HttpStatus.CREATED)
    @Transactional
    public GameItemOrderDetail addDetail(@PathVariable Integer orderId,
                                         @RequestBody OrderDetailCreate payload) {
        validateDetailCreate(payload);
        GameItemOrder o = orderService.getById(orderId);
        if (o == null) throw ApiException.notFound("订单不存在");
        if (!"pending".equals(o.getStatus())) {
            throw ApiException.badRequest("只能向待分配的订单添加明细");
        }
        GameItem item = itemService.getById(payload.itemId);
        if (item == null) throw ApiException.badRequest("物品ID " + payload.itemId + " 不存在");
        int qty = payload.quantity != null ? payload.quantity : 1;
        BigDecimal unitPrice = payload.unitPrice != null ? payload.unitPrice
                : (item.getPrice() != null ? item.getPrice() : BigDecimal.ZERO);
        GameRegionInventory inventory = findInventory(o.getRegionId(), payload.itemId);
        GameItemOrderDetail detail = new GameItemOrderDetail();
        detail.setOrderId(orderId);
        detail.setItemId(payload.itemId);
        detail.setItemName(item.getName());
        detail.setItemImage(item.getImage());
        detail.setItemSelectedImage(item.getSelectedImage());
        detail.setQuantity(qty);
        detail.setUnitPrice(unitPrice);
        detail.setSubtotal(unitPrice.multiply(BigDecimal.valueOf(qty)));
        if (inventory != null) {
            detail.setPurchasePrice(inventory.getPurchasePrice());
        }
        detail.setRemark(payload.remark);
        detailService.save(detail);
        recalculateOrderTotal(o);
        orderService.updateById(o);
        return detail;
    }

    @PutMapping("/details/{detailId}")
    @Transactional
    public GameItemOrderDetail updateDetail(@PathVariable Integer detailId,
                                            @RequestBody OrderDetailUpdate payload) {
        if (payload == null) {
            throw ApiException.badRequest("请求参数不能为空");
        }
        if (payload.quantity != null && payload.quantity <= 0) {
            throw ApiException.badRequest("物品数量必须大于 0");
        }
        if (payload.unitPrice != null && payload.unitPrice.signum() < 0) {
            throw ApiException.badRequest("物品单价不能小于 0");
        }
        if (payload.status != null && !DETAIL_STATUSES.contains(payload.status)) {
            throw ApiException.badRequest("明细状态无效: " + payload.status);
        }
        GameItemOrderDetail d = detailService.getById(detailId);
        if (d == null) throw ApiException.notFound("明细不存在");
        GameItemOrder order = orderService.getById(d.getOrderId());
        if (order == null) throw ApiException.notFound("订单不存在");
        if (!"pending".equals(order.getStatus())) {
            throw ApiException.badRequest("只能修改待分配订单的明细");
        }
        boolean recalcSubtotal = payload.quantity != null || payload.unitPrice != null;
        if (payload.quantity != null) d.setQuantity(payload.quantity);
        if (payload.unitPrice != null) d.setUnitPrice(payload.unitPrice);
        if (payload.status != null) d.setStatus(payload.status);
        if (payload.remark != null) d.setRemark(payload.remark);
        if (recalcSubtotal) {
            BigDecimal price = d.getUnitPrice() != null ? d.getUnitPrice() : BigDecimal.ZERO;
            d.setSubtotal(price.multiply(BigDecimal.valueOf(d.getQuantity())));
        }
        detailService.updateById(d);
        recalculateOrderTotal(order);
        orderService.updateById(order);
        return d;
    }

    @DeleteMapping("/details/{detailId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Transactional
    public void deleteDetail(@PathVariable Integer detailId) {
        GameItemOrderDetail d = detailService.getById(detailId);
        if (d == null) throw ApiException.notFound("明细不存在");
        GameItemOrder order = orderService.getById(d.getOrderId());
        if (order != null && !"pending".equals(order.getStatus())) {
            throw ApiException.badRequest("只能删除待分配订单的明细");
        }
        detailService.removeById(detailId);
        if (order != null) {
            recalculateOrderTotal(order);
            orderService.updateById(order);
        }
    }

    private void validateCreate(OrderCreate payload) {
        if (payload == null || payload.gameId == null || payload.regionId == null) {
            throw ApiException.badRequest("游戏和大区不能为空");
        }
        if (payload.details == null || payload.details.isEmpty()) {
            throw ApiException.badRequest("订单明细不能为空");
        }
        payload.details.forEach(this::validateDetailCreate);
    }

    private void validateCopy(OrderCopy payload, GameItemOrder source) {
        if (payload == null || payload.gameId == null || payload.regionId == null) {
            throw ApiException.badRequest("游戏和大区不能为空");
        }
        if (payload.orderNo == null || payload.orderNo.isBlank()) {
            throw ApiException.badRequest("订单号不能为空");
        }
        if (payload.orderNo.length() > 50) {
            throw ApiException.badRequest("订单号不能超过 50 个字符");
        }
        if (payload.sourceOrderNo != null && payload.sourceOrderNo.length() > 100) {
            throw ApiException.badRequest("平台订单号不能超过 100 个字符");
        }
        if (payload.orderNo.equals(source.getOrderNo())) {
            throw ApiException.badRequest("复制订单必须使用新的订单号");
        }
        if (payload.sourceOrderNo != null && !payload.sourceOrderNo.isBlank()
                && payload.sourceOrderNo.equals(source.getSourceOrderNo())) {
            throw ApiException.badRequest("复制订单必须使用新的平台订单号");
        }
        if (orderService.getOne(new LambdaQueryWrapper<GameItemOrder>()
                .eq(GameItemOrder::getOrderNo, payload.orderNo.trim()), false) != null) {
            throw ApiException.conflict("订单号已存在: " + payload.orderNo.trim());
        }
        String sourceOrderNo = trimToNull(payload.sourceOrderNo);
        if (payload.websiteId != null && sourceOrderNo != null
                && orderService.findByWebsiteIdAndSourceOrderNo(payload.websiteId, sourceOrderNo) != null) {
            throw ApiException.conflict("该平台订单号已存在: " + sourceOrderNo);
        }
        if (payload.details == null || payload.details.isEmpty()) {
            throw ApiException.badRequest("订单明细不能为空");
        }
        payload.details.forEach(this::validateDetailCopy);
        try {
            DeliveryState initialState = DeliveryState.from(payload.deliveryStatus, payload.status);
            if (!COPY_INITIAL_STATES.contains(initialState)) {
                throw ApiException.badRequest("复制订单不能直接创建为交易中或已结束状态");
            }
        } catch (IllegalStateException e) {
            throw ApiException.badRequest("订单状态组合无效: " + payload.deliveryStatus + "/" + payload.status);
        }
    }

    private void applyCopyNumberDefaults(OrderCopy payload, GameItemOrder source) {
        if (payload == null) return;
        String uniqueSuffix = "-COPY-" + LocalDateTime.now().format(TS) + "-"
                + UUID.randomUUID().toString().replace("-", "").substring(0, 6).toUpperCase();
        if (payload.orderNo == null || payload.orderNo.isBlank()) {
            payload.orderNo = appendBoundedSuffix(source.getOrderNo(), uniqueSuffix, 50, "ORDER");
        }
        if (payload.sourceOrderNo == null || payload.sourceOrderNo.isBlank()) {
            payload.sourceOrderNo = appendBoundedSuffix(
                    source.getSourceOrderNo(), uniqueSuffix, 100, "PLATFORM-ORDER");
        }
    }

    private static String appendBoundedSuffix(String original, String suffix, int maxLength, String fallback) {
        String base = original == null || original.isBlank() ? fallback : original.trim();
        int baseLength = Math.max(1, maxLength - suffix.length());
        return base.substring(0, Math.min(base.length(), baseLength)) + suffix;
    }

    private void validateCopyAccount(OrderCopy payload) {
        if (payload.platformAccountId == null) return;
        PlatformAccount account = accountService.getById(payload.platformAccountId);
        if (account == null) {
            throw ApiException.badRequest("平台账号不存在: " + payload.platformAccountId);
        }
        if (!Integer.valueOf(1).equals(account.getIsActive())) {
            throw ApiException.badRequest("平台账号已停用: " + payload.platformAccountId);
        }
        if (payload.websiteId == null || !payload.websiteId.equals(account.getWebsiteId())) {
            throw ApiException.badRequest("平台账号不属于所选来源平台");
        }
    }

    private void validateDetailCopy(OrderDetailCopy payload) {
        if (payload == null || payload.itemId == null) {
            throw ApiException.badRequest("物品 ID 不能为空");
        }
        if (payload.quantity != null && payload.quantity <= 0) {
            throw ApiException.badRequest("物品数量必须大于 0");
        }
        if (payload.unitPrice != null && payload.unitPrice.signum() < 0) {
            throw ApiException.badRequest("物品单价不能小于 0");
        }
        if (payload.purchasePrice != null && payload.purchasePrice.signum() < 0) {
            throw ApiException.badRequest("进货价不能小于 0");
        }
        if (payload.sellingPrice != null && payload.sellingPrice.signum() < 0) {
            throw ApiException.badRequest("出货价不能小于 0");
        }
    }

    private static String trimToNull(String value) {
        if (value == null || value.isBlank()) return null;
        return value.trim();
    }

    private void validateDetailCreate(OrderDetailCreate payload) {
        if (payload == null || payload.itemId == null) {
            throw ApiException.badRequest("物品 ID 不能为空");
        }
        if (payload.quantity != null && payload.quantity <= 0) {
            throw ApiException.badRequest("物品数量必须大于 0");
        }
        if (payload.unitPrice != null && payload.unitPrice.signum() < 0) {
            throw ApiException.badRequest("物品单价不能小于 0");
        }
    }

    private GameRegionInventory findInventory(Integer regionId, Integer itemId) {
        return inventoryService.getOne(new LambdaQueryWrapper<GameRegionInventory>()
                .eq(GameRegionInventory::getRegionId, regionId)
                .eq(GameRegionInventory::getItemId, itemId)
                .eq(GameRegionInventory::getIsActive, 1), false);
    }

    /** 创建订单入参（主表 + 明细）。 */
    public static class OrderCreate {
        public Integer gameId;
        public Integer regionId;
        public String customerName;
        public String customerContact;
        public String remark;
        public List<OrderDetailCreate> details;
    }

    /** 复制订单入参：可修改全部业务字段，运行态字段会重置。 */
    public static class OrderCopy {
        public String orderNo;
        public Integer websiteId;
        public Integer platformAccountId;
        public String sourceOrderNo;
        public Integer gameId;
        public Integer regionId;
        public Integer gameAccountId;
        public String buyerCharacter;
        public String assetType;
        public BigDecimal assetAmount;
        public String deliveryStatus;
        public String status;
        public String customerName;
        public String customerContact;
        public String remark;
        public LocalDateTime platformOrderTime;
        public BigDecimal platformPrice;
        public String platformItemType;
        public String productTitle;
        public String tradeItemName;
        public Integer quantity;
        public Integer saleQuantity;
        public List<OrderDetailCopy> details;
    }

    /** 复制订单的子订单入参。 */
    public static class OrderDetailCopy extends OrderDetailCreate {
        public BigDecimal purchasePrice;
        public BigDecimal sellingPrice;
        public String bundleName;
    }

    /** 更新订单入参。 */
    public static class OrderUpdate {
        public String customerName;
        public String customerContact;
        public String status;
        public Integer assignedMachineId;
        public String remark;
    }

    /** 新增/创建订单明细入参。 */
    public static class OrderDetailCreate {
        public Integer itemId;
        public Integer quantity;
        public BigDecimal unitPrice;
        public String remark;
    }

    /** 更新订单明细入参。 */
    public static class OrderDetailUpdate {
        public Integer quantity;
        public BigDecimal unitPrice;
        public String status;
        public String remark;
    }
}
