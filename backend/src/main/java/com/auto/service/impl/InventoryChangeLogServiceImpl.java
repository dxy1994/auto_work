package com.auto.service.impl;

import com.auto.entity.GameRegionInventory;
import com.auto.entity.InventoryChangeLog;
import com.auto.mapper.InventoryChangeLogMapper;
import com.auto.service.InventoryChangeLogService;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

@Service
public class InventoryChangeLogServiceImpl extends ServiceImpl<InventoryChangeLogMapper, InventoryChangeLog>
        implements InventoryChangeLogService {

    @Override
    public List<InventoryChangeLog> findByInventoryId(Integer inventoryId) {
        return baseMapper.findByInventoryId(inventoryId);
    }

    @Override
    public InventoryChangeLog logStockIn(GameRegionInventory inv, int quantity, BigDecimal unitPrice,
                                         BigDecimal avgBefore, BigDecimal avgAfter, String operator) {
        InventoryChangeLog log = new InventoryChangeLog();
        log.setInventoryId(inv.getId());
        log.setGameId(inv.getGameId());
        log.setRegionId(inv.getRegionId());
        log.setItemId(inv.getItemId());
        log.setChangeType("stock_in");
        log.setStockBefore(inv.getStock() - quantity);
        log.setStockAfter(inv.getStock());
        log.setStockDelta(quantity);
        log.setUnitPrice(unitPrice);
        log.setAvgPriceBefore(avgBefore);
        log.setAvgPriceAfter(avgAfter);
        log.setOperator(operator);
        log.setCreatedAt(LocalDateTime.now());
        save(log);
        return log;
    }

    @Override
    public InventoryChangeLog logStockOut(GameRegionInventory inv, int quantity, String reason, String operator) {
        InventoryChangeLog log = new InventoryChangeLog();
        log.setInventoryId(inv.getId());
        log.setGameId(inv.getGameId());
        log.setRegionId(inv.getRegionId());
        log.setItemId(inv.getItemId());
        log.setChangeType("stock_out");
        log.setStockBefore(inv.getStock() + quantity);
        log.setStockAfter(inv.getStock());
        log.setStockDelta(-quantity);
        log.setAvgPriceBefore(inv.getPurchasePrice());
        log.setAvgPriceAfter(inv.getPurchasePrice());
        log.setChangeReason(reason);
        log.setOperator(operator);
        log.setCreatedAt(LocalDateTime.now());
        save(log);
        return log;
    }

    @Override
    public InventoryChangeLog logFluctuationUpdate(GameRegionInventory inv, String field, String oldVal,
                                                   String newVal, String operator) {
        InventoryChangeLog log = new InventoryChangeLog();
        log.setInventoryId(inv.getId());
        log.setGameId(inv.getGameId());
        log.setRegionId(inv.getRegionId());
        log.setItemId(inv.getItemId());
        log.setChangeType("fluctuation_update");
        log.setChangeReason("风控参数变更: " + field + " " + oldVal + " -> " + newVal);
        log.setOperator(operator);
        log.setCreatedAt(LocalDateTime.now());
        save(log);
        return log;
    }
}
