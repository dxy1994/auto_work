package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.GameItem;
import com.auto.entity.GameItemOrder;
import com.auto.entity.GameItemOrderDetail;
import com.auto.entity.GameRegion;
import com.auto.entity.GameRegionItem;
import com.auto.service.GameItemOrderDetailService;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameItemService;
import com.auto.service.GameRegionItemService;
import com.auto.service.GameRegionService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import tools.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

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
    private final GameRegionItemService inventoryService;
    private final ObjectMapper objectMapper;

    public OrderController(GameItemOrderService orderService, GameItemOrderDetailService detailService,
                           GameItemService itemService, GameRegionService regionService,
                           GameRegionItemService inventoryService,
                           ObjectMapper objectMapper) {
        this.orderService = orderService;
        this.detailService = detailService;
        this.itemService = itemService;
        this.regionService = regionService;
        this.inventoryService = inventoryService;
        this.objectMapper = objectMapper;
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
        return Map.of("total", result.getTotal(), "items", result.getRecords());
    }

    @GetMapping("/{orderId}")
    public Map<String, Object> get(@PathVariable Integer orderId) {
        GameItemOrder o = orderService.getById(orderId);
        if (o == null) throw ApiException.notFound("订单不存在");
        return toFullMap(o, detailService.findByOrderIdOrderById(orderId));
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
            GameRegionItem inventory = findInventory(payload.regionId, d.itemId);
            GameItemOrderDetail detail = new GameItemOrderDetail();
            detail.setOrderId(order.getId());
            detail.setItemId(d.itemId);
            detail.setItemName(item.getName());
            detail.setItemImage(item.getImage());
            detail.setQuantity(qty);
            detail.setUnitPrice(unitPrice);
            detail.setSubtotal(unitPrice.multiply(BigDecimal.valueOf(qty)));
            if (inventory != null) {
                detail.setPurchasePrice(inventory.getPurchasePrice());
                detail.setSellingPrice(inventory.getSellingPrice());
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
        GameRegionItem inventory = findInventory(o.getRegionId(), payload.itemId);
        GameItemOrderDetail detail = new GameItemOrderDetail();
        detail.setOrderId(orderId);
        detail.setItemId(payload.itemId);
        detail.setItemName(item.getName());
        detail.setItemImage(item.getImage());
        detail.setQuantity(qty);
        detail.setUnitPrice(unitPrice);
        detail.setSubtotal(unitPrice.multiply(BigDecimal.valueOf(qty)));
        if (inventory != null) {
            detail.setPurchasePrice(inventory.getPurchasePrice());
            detail.setSellingPrice(inventory.getSellingPrice());
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

    private GameRegionItem findInventory(Integer regionId, Integer itemId) {
        return inventoryService.getOne(new LambdaQueryWrapper<GameRegionItem>()
                .eq(GameRegionItem::getRegionId, regionId)
                .eq(GameRegionItem::getItemId, itemId)
                .eq(GameRegionItem::getIsActive, 1), false);
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
