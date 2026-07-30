package com.auto.service;

import com.auto.entity.InventoryChangeLog;
import com.auto.entity.GameRegionInventory;
import com.baomidou.mybatisplus.spring.service.IService;

import java.math.BigDecimal;
import java.util.List;

public interface InventoryChangeLogService extends IService<InventoryChangeLog> {

    /** 查询某库存记录的所有变更日志。 */
    List<InventoryChangeLog> findByInventoryId(Integer inventoryId);

    /** 记录入库日志。 */
    InventoryChangeLog logStockIn(GameRegionInventory inv, long quantity, BigDecimal unitPrice,
                                  BigDecimal avgBefore, BigDecimal avgAfter, String operator);

    /** 记录出库日志（reason 必填）。 */
    InventoryChangeLog logStockOut(GameRegionInventory inv, long quantity, String reason, String operator);

    /** 记录风控参数变更日志。 */
    InventoryChangeLog logFluctuationUpdate(GameRegionInventory inv, String field, String oldVal,
                                            String newVal, String operator);
}
