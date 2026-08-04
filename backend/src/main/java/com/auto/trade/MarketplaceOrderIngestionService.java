package com.auto.trade;

import com.auto.entity.PlatformAccount;
import com.auto.entity.Game;
import com.auto.entity.GameItemOrder;
import com.auto.entity.GameRegion;
import com.auto.entity.TradeEvent;
import com.auto.service.PlatformAccountService;
import com.auto.service.GameItemOrderService;
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

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeFormatterBuilder;
import java.time.temporal.ChronoField;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/** 将 Worker 订单观察幂等写入总控订单域。 */
@Service
public class MarketplaceOrderIngestionService {

    private static final Logger log = LoggerFactory.getLogger(MarketplaceOrderIngestionService.class);
    private static final DateTimeFormatter PLATFORM_TIME_WITH_YEAR =
            new DateTimeFormatterBuilder()
                    .appendPattern("yyyy-MM-dd HH:mm")
                    .optionalStart()
                    .appendPattern(":ss")
                    .optionalEnd()
                    .toFormatter();

    private final PlatformAccountService accountService;
    private final GameRegionService regionService;
    private final GameItemOrderService orderService;
    private final TradeEventService eventService;
    private final GameService gameService;
    private final ApplicationEventPublisher eventPublisher;
    private final OrderDetailGenerationService detailGenerationService;

    public MarketplaceOrderIngestionService(
            PlatformAccountService accountService,
            GameRegionService regionService,
            GameItemOrderService orderService,
            TradeEventService eventService,
            GameService gameService,
            ApplicationEventPublisher eventPublisher,
            OrderDetailGenerationService detailGenerationService) {
        this.accountService = accountService;
        this.regionService = regionService;
        this.orderService = orderService;
        this.eventService = eventService;
        this.gameService = gameService;
        this.eventPublisher = eventPublisher;
        this.detailGenerationService = detailGenerationService;
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
            return recoverExistingOrderMapping(
                    machineId, accountId, account, existing, message);
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
            errorMessage = "原因：商品标题未包含有效的 %物品名% 标记。解决方案：在平台商品标题中加入 %游戏中的物品名或物品编码%，"
                    + "并确保该值与游戏物品管理中的名称或编码完全一致。";
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
            LocalDateTime platformOrderTime =
                    parsePlatformOrderTime(message.platformOrderTime());
            if (platformOrderTime != null) {
                order.setPlatformOrderTime(platformOrderTime);
            } else {
                log.warn("[Order] 无法解析平台订单时间 sourceOrderNo={} value={}",
                        message.sourceOrderNo(), message.platformOrderTime());
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
                detailGenerationService.ensureDetails(order);
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

    private GameItemOrder recoverExistingOrderMapping(
            int machineId,
            int accountId,
            PlatformAccount account,
            GameItemOrder existing,
            OrderDetectedMessage message) {
        boolean needsRecovery = !positiveId(existing.getGameId())
                || !positiveId(existing.getRegionId())
                || "CONFIG_MISSING".equals(existing.getLastErrorCode());
        if (!needsRecovery) {
            return existing;
        }

        Map<String, Object> config = account.getExtraFields();
        Integer gameId = resolveGameId(config, message);
        Integer regionId = positiveId(gameId)
                ? resolveRegionId(config, message.regionExternalKey(), gameId)
                : -1;
        if (!positiveId(gameId) || !positiveId(regionId)) {
            return existing;
        }

        String tradeItem = parseItemFromTitle(message.productTitle());
        String previousStatus = existing.getDeliveryStatus();
        boolean resumeGreeting = "suspended".equals(previousStatus)
                && "CONFIG_MISSING".equals(existing.getLastErrorCode())
                && !tradeItem.isEmpty();

        existing.setGameId(gameId);
        existing.setRegionId(regionId);
        existing.setBuyerCharacter(message.buyerCharacter());
        existing.setCustomerName(message.buyerCharacter());
        existing.setAssetType(message.assetType());
        existing.setAssetAmount(message.assetAmount());
        existing.setRemark(message.rawTitle());
        existing.setProductTitle(message.productTitle());
        existing.setQuantity(message.quantity());
        existing.setSaleQuantity(message.saleQuantity());
        existing.setPlatformPrice(message.platformPrice());
        existing.setPlatformItemType(message.platformItemType());
        if (!tradeItem.isEmpty()) {
            existing.setTradeItemName(tradeItem);
        }

        if (resumeGreeting) {
            existing.setDeliveryStatus("greeting");
            existing.setLastErrorCode(null);
            existing.setLastErrorMessage(null);
        } else if (tradeItem.isEmpty()
                && "CONFIG_MISSING".equals(existing.getLastErrorCode())) {
            existing.setLastErrorCode("ITEM_NAME_PARSE_FAILED");
            existing.setLastErrorMessage(
                    "原因：商品标题未包含有效的 %物品名% 标记。解决方案："
                            + "在平台商品标题中加入 %游戏中的物品名或物品编码%。");
        }
        orderService.updateById(existing);

        if (!tradeItem.isEmpty()) {
            try {
                detailGenerationService.ensureDetails(existing);
            } catch (Exception e) {
                log.warn("[Order] 修复映射后创建子订单明细失败 order_id={}: {}",
                        existing.getId(), e.getMessage(), e);
            }
        }

        TradeEvent event = new TradeEvent();
        event.setOrderId(existing.getId());
        event.setEventType("order_configuration_recovered");
        event.setFromStatus(previousStatus);
        event.setToStatus(existing.getDeliveryStatus());
        event.setMessage("平台游戏名和区服已重新匹配");
        try {
            eventService.save(event);
        } catch (Exception e) {
            log.error("[Order] 映射恢复事件记录失败 order_id={}: {}",
                    existing.getId(), e.getMessage());
        }

        if (resumeGreeting) {
            eventPublisher.publishEvent(new GreetingDispatchRequested(
                    machineId,
                    existing.getId(),
                    gameId,
                    regionId,
                    account.getWebsiteId(),
                    accountId,
                    message.sourceOrderNo(),
                    message.platform()));
        }
        return existing;
    }

    private static boolean positiveId(Integer value) {
        return value != null && value > 0;
    }

    static LocalDateTime parsePlatformOrderTime(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }

        String normalized = value.trim().replace('T', ' ');
        try {
            return LocalDateTime.parse(normalized, PLATFORM_TIME_WITH_YEAR);
        } catch (Exception ignore) {
            // 继续兼容旧 Worker 上报的 MM-dd HH:mm[:ss]。
        }

        LocalDateTime now = LocalDateTime.now();
        DateTimeFormatter withoutYear = new DateTimeFormatterBuilder()
                .appendPattern("MM-dd HH:mm")
                .optionalStart()
                .appendPattern(":ss")
                .optionalEnd()
                .parseDefaulting(ChronoField.YEAR, LocalDate.now().getYear())
                .toFormatter();
        try {
            LocalDateTime parsed = LocalDateTime.parse(normalized, withoutYear);
            // 跨年时，12 月的订单可能在次年 1 月才被采集。
            if (parsed.isAfter(now.plusDays(1))) {
                parsed = parsed.minusYears(1);
            }
            return parsed;
        } catch (Exception ignore) {
            return null;
        }
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
            if (game == null) {
                game = gameService.findAllActiveOrdered().stream()
                        .filter(candidate -> samePlatformGameName(
                                name, candidate.getCode())
                                || samePlatformGameName(
                                name, candidate.getName()))
                        .findFirst()
                        .orElse(null);
            }
            if (game != null) {
                return game.getId();
            }
        }
        return -1;
    }

    static boolean samePlatformGameName(String left, String right) {
        String leftKey = platformGameNameKey(left);
        return !leftKey.isEmpty()
                && leftKey.equals(platformGameNameKey(right));
    }

    private static String platformGameNameKey(String value) {
        return value == null
                ? ""
                : value.replaceAll("\\s+", "").toLowerCase(Locale.ROOT);
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

}
