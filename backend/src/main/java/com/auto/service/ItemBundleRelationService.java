package com.auto.service;

import com.auto.entity.ItemBundleRelation;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;
import java.util.Map;

public interface ItemBundleRelationService extends IService<ItemBundleRelation> {

    /** 获取套装下的所有子物品ID */
    List<Integer> findItemIdsByBundleId(Integer bundleId);

    /** 获取套装下的所有关联记录（含数量） */
    List<ItemBundleRelation> findRelationsByBundleId(Integer bundleId);

    /** 批量添加物品到套装（默认数量1） */
    void addItems(Integer bundleId, List<Integer> itemIds);

    /** 批量添加物品到套装（指定数量，key=itemId, value=quantity） */
    void addItemsWithQuantity(Integer bundleId, Map<Integer, Integer> itemQuantities);

    /** 从套装中移除物品 */
    void removeItem(Integer bundleId, Integer itemId);

    /** 获取物品所属的套装ID列表 */
    List<Integer> findBundleIdsByItemId(Integer itemId);
}
