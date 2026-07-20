package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.GameItemOrderDetail;
import com.auto.entity.GameRegionInventory;
import com.auto.service.GameItemOrderDetailService;
import com.auto.service.GameRegionInventoryService;
import com.auto.service.InventoryChangeLogService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/** 游戏内交易完成后的订单明细、交付时间和库存对账。 */
@Service
@Slf4j
public class TradeCompletionService {

    private final GameItemOrderDetailService detailService;
    private final GameRegionInventoryService inventoryService;
    private final InventoryChangeLogService changeLogService;

    public TradeCompletionService(GameItemOrderDetailService detailService,
                                  GameRegionInventoryService inventoryService,
                                  InventoryChangeLogService changeLogService) {
        this.detailService = detailService;
        this.inventoryService = inventoryService;
        this.changeLogService = changeLogService;
    }

    public void complete(GameItemOrder order) {
        LocalDateTime now = LocalDateTime.now();
        if (order.getGameDeliveredAt() == null) {
            order.setGameDeliveredAt(now);
            reconcileInventory(order, "completed");
        } else {
            for (GameItemOrderDetail detail : detailService.findByOrderId(order.getId())) {
                detail.setStatus("completed");
                detailService.updateById(detail);
            }
        }
        order.setCompletedAt(now);
    }

    /** 游戏交易完成时立即扣减库存，但订单仍需等待网站侧确认。 */
    public void gameDelivered(GameItemOrder order) {
        if (order.getGameDeliveredAt() != null) {
            return;
        }
        order.setGameDeliveredAt(LocalDateTime.now());
        reconcileInventory(order, "processing");
    }

    private void reconcileInventory(GameItemOrder order, String detailStatus) {
        List<String> reconciliationErrors = new ArrayList<>();
        for (GameItemOrderDetail detail : detailService.findByOrderId(order.getId())) {
            detail.setStatus(detailStatus);
            detailService.updateById(detail);

            Integer itemId = detail.getItemId();
            int quantity = detail.getQuantity() != null ? detail.getQuantity() : 0;
            if (itemId == null || quantity <= 0) {
                reconciliationErrors.add("明细" + detail.getId() + "缺少有效物品或数量");
                continue;
            }

            GameRegionInventory inventory = inventoryService.findByRegionIdAndItemId(
                    order.getRegionId(), itemId);
            if (inventory == null) {
                reconciliationErrors.add("物品" + itemId + "没有区服库存记录");
                continue;
            }
            if (inventory.getStock() == null || inventory.getStock() < quantity) {
                reconciliationErrors.add("物品" + itemId + "库存不足，需要人工对账");
                continue;
            }

            inventory.setStock(inventory.getStock() - quantity);
            inventoryService.updateById(inventory);
            changeLogService.logStockOut(
                    inventory, quantity, "auto_trade:order=" + order.getId(), "system");
        }

        if (!reconciliationErrors.isEmpty()) {
            order.setLastErrorCode("INVENTORY_RECONCILIATION_REQUIRED");
            order.setLastErrorMessage(String.join("; ", reconciliationErrors));
            log.warn("[TradeCompletion] 游戏交易完成但库存需要对账 order_id={} errors={}",
                    order.getId(), reconciliationErrors);
        } else {
            order.setLastErrorCode(null);
            order.setLastErrorMessage(null);
        }
    }
}
