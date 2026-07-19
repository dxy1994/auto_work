package com.auto.service;

import com.auto.entity.GameRegionInventoryShopPrice;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface GameRegionInventoryShopPriceService extends IService<GameRegionInventoryShopPrice> {

    /** 按 inventoryId + accountId 查询商铺定价。 */
    GameRegionInventoryShopPrice findByInventoryIdAndAccountId(Integer inventoryId, Integer accountId);

    /** 按 inventoryId 查询所有商铺定价。 */
    List<GameRegionInventoryShopPrice> findByInventoryId(Integer inventoryId);

    /** 按 accountId 查询所有定价。 */
    List<GameRegionInventoryShopPrice> findByAccountId(Integer accountId);

    /** 为指定 inventory 在所有活跃商铺下创建默认定价记录。 */
    void initForInventory(Integer inventoryId);

    /** 为指定商铺在所有活跃库存下创建默认定价记录。 */
    void initForAccount(Integer accountId);
}
