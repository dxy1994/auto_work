package com.auto.trade;

import com.auto.entity.Account;
import com.auto.entity.Game;
import com.auto.entity.GameItemOrder;
import com.auto.entity.GameRegion;
import com.auto.entity.TradeEvent;
import com.auto.service.AccountService;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameRegionService;
import com.auto.service.GameService;
import com.auto.service.TradeEventService;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/** 将 Worker 订单观察幂等写入总控订单域。 */
@Service
public class MarketplaceOrderIngestionService {

    private final AccountService accountService;
    private final GameRegionService regionService;
    private final GameItemOrderService orderService;
    private final TradeEventService eventService;
    private final GameService gameService;

    public MarketplaceOrderIngestionService(
            AccountService accountService,
            GameRegionService regionService,
            GameItemOrderService orderService,
            TradeEventService eventService,
            GameService gameService) {
        this.accountService = accountService;
        this.regionService = regionService;
        this.orderService = orderService;
        this.eventService = eventService;
        this.gameService = gameService;
    }

    @Transactional
    public GameItemOrder ingest(int machineId, int accountId, OrderDetectedMessage message) {
        Account account = accountService.getById(accountId);
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

        boolean supported = "adena".equals(message.assetType());
        GameItemOrder order = new GameItemOrder();
        order.setOrderNo("MP-" + UUID.randomUUID().toString().replace("-", ""));
        order.setWebsiteId(account.getWebsiteId());
        order.setSourceOrderNo(message.sourceOrderNo());
        order.setGameId(gameId);
        order.setRegionId(regionId);
        order.setBuyerCharacter(message.buyerCharacter());
        order.setCustomerName(message.buyerCharacter());
        order.setAssetType(message.assetType());
        order.setAssetAmount(message.assetAmount());
        if (configError.isEmpty()) {
            order.setDeliveryStatus(supported ? "waiting_assignment" : "suspended");
        } else {
            order.setDeliveryStatus("suspended");
            order.setLastErrorCode("CONFIG_MISSING");
            order.setLastErrorMessage(configError.toString());
        }
        order.setRemark(message.rawTitle());
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
        if (!supported && configError.isEmpty()) {
            order.setLastErrorCode("UNSUPPORTED_ASSET");
            order.setLastErrorMessage("第一阶段只支持 Adena");
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
        }
        TradeEvent event = new TradeEvent();
        event.setOrderId(order.getId());
        event.setEventType("order_detected");
        event.setFromStatus("detected");
        event.setToStatus(order.getDeliveryStatus());
        event.setMessage("machine=" + machineId + ", platform=" + message.platform());
        eventService.save(event);
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
            Game game = gameService.findByName(name);
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
}
