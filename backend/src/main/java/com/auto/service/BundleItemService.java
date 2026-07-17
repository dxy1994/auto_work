package com.auto.service;

import com.auto.entity.BundleItem;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface BundleItemService extends IService<BundleItem> {

    /** 获取套装下的所有子物品ID */
    List<Integer> findItemIdsByBundleId(Integer bundleId);

    /** 批量添加物品到套装 */
    void addItems(Integer bundleId, List<Integer> itemIds);

    /** 从套装中移除物品 */
    void removeItem(Integer bundleId, Integer itemId);

    /** 获取物品所属的套装ID列表 */
    List<Integer> findBundleIdsByItemId(Integer itemId);
}
