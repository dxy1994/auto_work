package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.*;
import com.auto.service.*;
import com.auto.trade.GreetingDispatchRequested;
import com.auto.trade.TradeDispatchCoordinator;
import com.auto.trade.statemachine.DeliveryEvent;
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

    private static final Set<String> DELETABLE_STATUSES = Set.of("pending", "cancelled");
    private static final Set<String> ORDER_STATUSES =
            Set.of("pending", "assigned", "processing", "completed", "cancelled");
    private static final Set<String> DETAIL_STATUSES =
            Set.of("pending", "processing", "completed", "failed");
    private static final java.time.format.DateTimeFormatter TS =
            java.time.format.DateTimeFormatter.ofPattern("yyyyMMddHHmmss");

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
                           TradeDispatchCoordinator tradeCoordinator) {
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
        return map;
    }

    // ── 订单主表 CRUD ────────────────────────────────────────────

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "game_id", required = false) Integer gameId,
            @RequestParam(name = "status", required = false) String status,
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize) {
        IPage<GameItemOrder> result = orderService.search(gameId, status, keyword, PageRequests.of(page, pageSize));
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
        return map;
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
        if ("abnormal".equals(orderStatus)) {
            deliveryStateMachine.fire(
                    order,
                    DeliveryEvent.RESET_TO_GREETING,
                    Map.of("message", "人工修复后重新招呼"));
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

    @DeleteMapping("/{orderId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Transactional
    public void delete(@PathVariable Integer orderId) {
        GameItemOrder o = orderService.getById(orderId);
        if (o == null) throw ApiException.notFound("订单不存在");
        if (!DELETABLE_STATUSES.contains(o.getStatus())) {
            throw ApiException.badRequest("只能删除待分配或已取消的订单");
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
