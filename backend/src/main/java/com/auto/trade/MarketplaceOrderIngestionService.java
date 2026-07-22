package com.auto.trade;

import com.auto.entity.PlatformAccount;
import com.auto.entity.ItemBundleRelation;
import com.auto.entity.Game;
import com.auto.entity.GameItem;
import com.auto.entity.GameItemOrder;
import com.auto.entity.GameItemOrderDetail;
import com.auto.entity.GameRegion;
import com.auto.entity.GameRegionInventory;
import com.auto.entity.TradeEvent;
import com.auto.service.PlatformAccountService;
import com.auto.service.ItemBundleRelationService;
import com.auto.service.GameItemOrderDetailService;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameItemService;
import com.auto.service.GameRegionInventoryService;
import com.auto.service.GameRegionService;
import com.auto.service.GameService;
import com.auto.service.TradeEventService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/** 将 Worker 订单观察幂等写入总控订单域。 */
@Service
public class MarketplaceOrderIngestionService {

    private static final Logger log = LoggerFactory.getLogger(MarketplaceOrderIngestionService.class);

    private final PlatformAccountService accountService;
    private final GameRegionService regionService;
    private final GameItemOrderService orderService;
    private final TradeEventService eventService;
    private final GameService gameService;
    private final ApplicationEventPublisher eventPublisher;
    private final GameItemService gameItemService;
    private final ItemBundleRelationService bundleItemService;
    private final GameItemOrderDetailService orderDetailService;
    private final GameRegionInventoryService regionItemService;

    public MarketplaceOrderIngestionService(
            PlatformAccountService accountService,
            GameRegionService regionService,
            GameItemOrderService orderService,
            TradeEventService eventService,
            GameService gameService,
            ApplicationEventPublisher eventPublisher,
            GameItemService gameItemService,
            ItemBundleRelationService bundleItemService,
            GameItemOrderDetailService orderDetailService,
            GameRegionInventoryService regionItemService) {
        this.accountService = accountService;
        this.regionService = regionService;
        this.orderService = orderService;
        this.eventService = eventService;
        this.gameService = gameService;
        this.eventPublisher = eventPublisher;
        this.gameItemService = gameItemService;
        this.bundleItemService = bundleItemService;
        this.orderDetailService = orderDetailService;
        this.regionItemService = regionItemService;
    }

    @Transactional
    public GameItemOrder ingest(int machineId, int accountId, OrderDetectedMessage message) {
        PlatformAccount account = accountService.getById(accountId);
        if (account == null || !Integer.valueOf(1).equals(account.getIsActive())) {
            throw new IllegalStateException("网站账号不存在或已停用");
        }
        GameItemOrder existing = orderService.findByWebsiteIdAndSourceOrderNo(
                account.getWebsiteId(), message.sourceOrderNo());
        if (existing != null) {
            return existing;
        }

        Map<String, Object> config = account.getExtraFields();

        // 配置校验 → 容错模式：优先从账号配置取，缺失时按 gameName/regionExternalKey 自动匹配
        Integer gameId = resolveGameId(config, message);
        Integer regionId = null;
        if (gameId != null && gameId != -1) {
            regionId = resolveRegionId(config, message.regionExternalKey(), gameId);
        } else {
            regionId = -1;
        }

        StringBuilder configError = new StringBuilder();
        if (gameId == null || gameId == -1) {
            configError.append("未配置交易游戏");
            gameId = -1;
        }
        if (regionId == null || regionId == -1) {
            if (!configError.isEmpty()) configError.append("; ");
            configError.append("未匹配到区服");
            regionId = -1;
        }
        if (gameId == -1 && regionId == -1) {
            // 两者都失败，尝试进一步的 gameName 匹配
            String gn = message.gameName();
            if (gn != null && !gn.isEmpty()) {
                configError.append(" (gameName=").append(gn).append(")");
            }
        }

        String tradeItem = parseItemFromTitle(message.productTitle());
        String errorCode = null;
        String errorMessage = null;
        if (!configError.isEmpty()) {
            errorCode = "CONFIG_MISSING";
            errorMessage = "原因：" + configError + "。解决方案：检查网站账号的交易游戏配置，并确认平台区服名称已关联到系统大区。";
        } else if (tradeItem.isEmpty()) {
            errorCode = "ITEM_NAME_PARSE_FAILED";
            errorMessage = "原因：商品标题未包含有效的 %物品名% 标记。解决方案：在平台商品标题中加入 %游戏中的物品名%，"
                    + "并确保该名称与游戏物品管理中的名称完全一致。";
        }
        if (errorCode != null) {
            log.warn("[Order] 订单校验失败 code={} account={} sourceOrderNo={} title={}; {}",
                    errorCode, accountId, message.sourceOrderNo(), message.productTitle(), errorMessage);
        }

        GameItemOrder order = new GameItemOrder();
        order.setOrderNo("MP-" + UUID.randomUUID().toString().replace("-", ""));
        order.setWebsiteId(account.getWebsiteId());
        order.setPlatformAccountId(accountId);
        order.setSourceOrderNo(message.sourceOrderNo());
        order.setGameId(gameId);
        order.setRegionId(regionId);
        order.setBuyerCharacter(message.buyerCharacter());
        order.setCustomerName(message.buyerCharacter());
        order.setAssetType(message.assetType());
        order.setAssetAmount(message.assetAmount());
        boolean isNormal = errorCode == null;
        if (isNormal) {
            order.setDeliveryStatus("greeting");
        } else {
            order.setDeliveryStatus("suspended");
            order.setLastErrorCode(errorCode);
            order.setLastErrorMessage(errorMessage);
        }
        order.setRemark(message.rawTitle());
        order.setProductTitle(message.productTitle());
        if (!tradeItem.isEmpty()) {
            order.setTradeItemName(tradeItem);
        }
        order.setQuantity(message.quantity());
        order.setSaleQuantity(message.saleQuantity());
        if (message.platformOrderTime() != null
                && !message.platformOrderTime().isEmpty()) {
            try {
                order.setPlatformOrderTime(
                        java.time.LocalDateTime.parse(
                                message.platformOrderTime(),
                                java.time.format.DateTimeFormatter.ofPattern(
                                        "MM-dd HH:mm")));
            } catch (Exception ignore) {
                // 解析失败忽略，保留为空
            }
        }
        if (message.platformPrice() != null) {
            order.setPlatformPrice(message.platformPrice());
        }
        if (message.platformItemType() != null
                && !message.platformItemType().isEmpty()) {
            order.setPlatformItemType(message.platformItemType());
        }

        try {
            orderService.save(order);
        } catch (DuplicateKeyException race) {
            GameItemOrder raced = orderService.findByWebsiteIdAndSourceOrderNo(
                    account.getWebsiteId(), message.sourceOrderNo());
            if (raced != null) {
                return raced;
            }
            throw race;
        } catch (DataIntegrityViolationException e) {
            log.warn("[Order] 订单入库失败 account={} sourceOrderNo={}; 原因：数据完整性约束冲突，{}；"
                            + "解决方案：检查数据库迁移是否完整，以及订单状态、游戏和大区字段是否允许当前值",
                    accountId, message.sourceOrderNo(), e.getMessage());
            return null;
        }

        // 根据解析的交易物品名自动创建子订单明细（失败不影响主流程）
        if (order.getTradeItemName() != null && !order.getTradeItemName().isEmpty()
                && gameId != null && gameId != -1) {
            try {
                autoCreateOrderDetails(order, gameId, regionId);
            } catch (Exception e) {
                log.warn("[Order] 自动创建子订单明细失败 order_id={} tradeItemName={}; 原因：{}；"
                                + "解决方案：检查同名游戏物品、套装子物品及大区库存配置，修正后重试",
                        order.getId(), order.getTradeItemName(), e.getMessage(), e);
            }
        }

        TradeEvent event = new TradeEvent();
        event.setOrderId(order.getId());
        event.setEventType("order_detected");
        event.setFromStatus("detected");
        event.setToStatus(order.getDeliveryStatus());
        event.setMessage("machine=" + machineId + ", platform=" + message.platform());
        try {
            eventService.save(event);
        } catch (Exception e) {
            log.error("[Order] 事件记录失败 order_id={} type={}; 原因：{}；"
                            + "解决方案：检查 trade_events 表结构和数据库连接，订单主记录已保留",
                    order.getId(), "order_detected", e.getMessage());
        }

        // 正常订单：异步派发招呼指令
        if (isNormal) {
            final int finalGameId = gameId;
            final int finalRegionId = regionId;
            final int finalOrderId = order.getId();
            final int finalWebsiteId = account.getWebsiteId();
            final int finalAccountId = accountId;
            final String finalSourceOrderNo = message.sourceOrderNo();
            final String finalPlatform = message.platform();
            eventPublisher.publishEvent(new GreetingDispatchRequested(
                    machineId, finalOrderId, finalGameId, finalRegionId,
                    finalWebsiteId, finalAccountId, finalSourceOrderNo, finalPlatform));
        }

        return order;
    }

    /** 批量查重：返回已存在于 DB 的 source_order_no 集合，供 Worker 端预过滤。 */
    public Set<String> findExistingSourceOrderNos(int websiteId, List<String> sourceOrderNos) {
        return orderService.findExistingSourceOrderNos(websiteId, sourceOrderNos);
    }

    /**
     * 解析 gameId：优先从账号配置 trade_game_id 取，
     * 缺失时按 gameName 匹配 games 表（name/code LIKE）。
     * 返回 -1 表示未匹配到。
     */
    private Integer resolveGameId(Map<String, Object> config, OrderDetectedMessage message) {
        // 1. 账号配置优先
        if (config != null && config.get("trade_game_id") instanceof Number num) {
            try {
                return intValue(num, "");
            } catch (IllegalStateException ignored) { }
        }
        // 2. 按 gameName 自动匹配
        String name = message.gameName();
        if (name != null && !name.isEmpty()) {
            Game game = gameService.findByCode(name);
            if (game != null) {
                return game.getId();
            }
        }
        return -1;
    }

    /**
     * 解析 regionId：优先从账号配置 trade_region_map 取，
     * 缺失时按 externalKey 匹配 game_regions（code/name LIKE，限定 gameId）。
     * 返回 -1 表示未匹配到。
     */
    private Integer resolveRegionId(Map<String, Object> config, String externalKey, int gameId) {
        // 1. 账号配置优先
        if (config != null && config.get("trade_region_map") instanceof Map<?, ?> regionMap) {
            Object val = regionMap.get(externalKey);
            if (val != null) {
                try {
                    return intValue(val, "");
                } catch (IllegalStateException ignored) { }
            }
        }
        // 2. 按 externalKey 自动匹配 game_regions 表
        if (gameId != -1) {
            GameRegion region = regionService.findByGameIdAndCode(gameId, externalKey);
            if (region != null) {
                return region.getId();
            }
        }
        return -1;
    }

    private int intValue(Object value, String message) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (NumberFormatException e) {
            throw new IllegalStateException(message);
        }
    }

    /** 从标题中提取一对 % 之间的内容作为实际物品名，未匹配返回空串。 */
    static String parseItemFromTitle(String title) {
        if (title == null || title.isEmpty()) {
            return "";
        }
        int start = title.indexOf('%');
        int end = title.indexOf('%', start + 1);
        if (start >= 0 && end > start) {
            return title.substring(start + 1, end).trim();
        }
        return "";
    }

    /**
     * 根据 tradeItemName 在物品表中查找匹配物品，自动创建子订单明细。
     * 单物品 → 创建 1 条明细；套装 → 拆分为多条明细，每条记录 bundleName。
     */
    private void autoCreateOrderDetails(GameItemOrder order, int gameId, int regionId) {
        String tradeItemName = order.getTradeItemName();
        GameItem matchedItem = gameItemService.findByGameIdAndName(gameId, tradeItemName);
        if (matchedItem == null) {
            log.warn("[Order] 子订单未创建 order_id={} tradeItemName={}; 原因：系统中未找到同名游戏物品；"
                            + "解决方案：在游戏物品管理中新增该物品，或将平台标题中的 %物品名% 改为系统中的准确名称",
                    order.getId(), tradeItemName);
            return;
        }

        if (Integer.valueOf(1).equals(matchedItem.getIsBundle())) {
            // 套装：拆分所有子物品，按关联表中配置的数量创建明细
            List<ItemBundleRelation> relations = bundleItemService.findRelationsByBundleId(matchedItem.getId());
            if (relations.isEmpty()) {
                log.warn("[Order] 子订单未创建 order_id={} bundle={}; 原因：套装尚未配置子物品；"
                                + "解决方案：在游戏物品管理中展开该套装并添加至少一个子物品",
                        order.getId(), tradeItemName);
                return;
            }
            List<Integer> childItemIds = relations.stream().map(ItemBundleRelation::getItemId).collect(Collectors.toList());
            Map<Integer, GameItem> childItemMap = gameItemService.listByIds(childItemIds).stream()
                    .collect(Collectors.toMap(GameItem::getId, i -> i));
            BigDecimal totalAmount = BigDecimal.ZERO;
            for (ItemBundleRelation rel : relations) {
                GameItem child = childItemMap.get(rel.getItemId());
                if (child == null) continue;
                int qty = rel.getQuantity() != null && rel.getQuantity() > 0 ? rel.getQuantity() : 1;
                GameItemOrderDetail detail = buildDetail(order.getId(), child, regionId, matchedItem.getName(), qty);
                orderDetailService.save(detail);
                totalAmount = totalAmount.add(detail.getSubtotal());
            }
            order.setTotalAmount(totalAmount);
        } else {
            // 单物品
            GameItemOrderDetail detail = buildDetail(order.getId(), matchedItem, regionId, null, 1);
            orderDetailService.save(detail);
            order.setTotalAmount(detail.getSubtotal());
        }
        orderService.updateById(order);
        log.info("[Order] 自动创建子订单明细 order_id={} item={} bundle={}",
                order.getId(), tradeItemName,
                Integer.valueOf(1).equals(matchedItem.getIsBundle()) ? matchedItem.getName() : "-");
    }

    private GameItemOrderDetail buildDetail(int orderId, GameItem item, int regionId, String bundleName, int quantity) {
        GameItemOrderDetail detail = new GameItemOrderDetail();
        detail.setOrderId(orderId);
        detail.setItemId(item.getId());
        detail.setItemName(item.getName());
        detail.setItemImage(item.getImage());
        detail.setItemSelectedImage(item.getSelectedImage());
        detail.setQuantity(quantity);
        BigDecimal price = item.getPrice() != null ? item.getPrice() : BigDecimal.ZERO;
        detail.setUnitPrice(price);
        detail.setSubtotal(price.multiply(BigDecimal.valueOf(quantity)));
        detail.setBundleName(bundleName);
        // 从大区物品库存获取进货价/出货价快照
        if (regionId > 0) {
            GameRegionInventory inventory = regionItemService.getOne(
                    new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<GameRegionInventory>()
                            .eq(GameRegionInventory::getRegionId, regionId)
                            .eq(GameRegionInventory::getItemId, item.getId())
                            .eq(GameRegionInventory::getIsActive, 1), false);
            if (inventory != null) {
                detail.setPurchasePrice(inventory.getPurchasePrice());
            }
        }
        return detail;
    }
}
