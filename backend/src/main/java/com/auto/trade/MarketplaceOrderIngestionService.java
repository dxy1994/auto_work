package com.auto.trade;

import com.auto.entity.Account;
import com.auto.entity.GameItemOrder;
import com.auto.entity.GameRegion;
import com.auto.entity.TradeEvent;
import com.auto.service.AccountService;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameRegionService;
import com.auto.service.TradeEventService;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Map;
import java.util.UUID;

/** 将 Worker 订单观察幂等写入总控订单域。 */
@Service
public class MarketplaceOrderIngestionService {

    private final AccountService accountService;
    private final GameRegionService regionService;
    private final GameItemOrderService orderService;
    private final TradeEventService eventService;

    public MarketplaceOrderIngestionService(
            AccountService accountService,
            GameRegionService regionService,
            GameItemOrderService orderService,
            TradeEventService eventService) {
        this.accountService = accountService;
        this.regionService = regionService;
        this.orderService = orderService;
        this.eventService = eventService;
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
        int gameId = intValue(config == null ? null : config.get("trade_game_id"), "未配置交易游戏");
        int regionId = resolveRegionId(config, message.regionExternalKey());
        GameRegion region = regionService.getById(regionId);
        if (region == null || !Integer.valueOf(1).equals(region.getIsActive())
                || !Integer.valueOf(gameId).equals(region.getGameId())) {
            throw new IllegalStateException("区服映射无效或不属于配置游戏");
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
        order.setDeliveryStatus(supported ? "waiting_assignment" : "suspended");
        order.setRemark(message.rawTitle());
        if (!supported) {
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

    private int resolveRegionId(Map<String, Object> config, String externalKey) {
        Object rawMap = config == null ? null : config.get("trade_region_map");
        if (!(rawMap instanceof Map<?, ?> regionMap)) {
            throw new IllegalStateException("未配置平台区服映射");
        }
        return intValue(regionMap.get(externalKey), "未找到平台区服映射: " + externalKey);
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
