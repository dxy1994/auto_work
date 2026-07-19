package com.auto.service.impl;

import com.auto.entity.ItemBundleRelation;
import com.auto.mapper.ItemBundleRelationMapper;
import com.auto.service.ItemBundleRelationService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
public class ItemBundleRelationServiceImpl extends ServiceImpl<ItemBundleRelationMapper, ItemBundleRelation> implements ItemBundleRelationService {

    @Override
    public List<Integer> findItemIdsByBundleId(Integer bundleId) {
        return list(new LambdaQueryWrapper<ItemBundleRelation>()
                .eq(ItemBundleRelation::getBundleId, bundleId))
                .stream()
                .map(ItemBundleRelation::getItemId)
                .collect(Collectors.toList());
    }

    @Override
    public List<ItemBundleRelation> findRelationsByBundleId(Integer bundleId) {
        return list(new LambdaQueryWrapper<ItemBundleRelation>()
                .eq(ItemBundleRelation::getBundleId, bundleId));
    }

    @Override
    public void addItems(Integer bundleId, List<Integer> itemIds) {
        for (Integer itemId : itemIds) {
            ItemBundleRelation bi = new ItemBundleRelation();
            bi.setBundleId(bundleId);
            bi.setItemId(itemId);
            bi.setQuantity(1);
            save(bi);
        }
    }

    @Override
    public void addItemsWithQuantity(Integer bundleId, Map<Integer, Integer> itemQuantities) {
        for (Map.Entry<Integer, Integer> entry : itemQuantities.entrySet()) {
            ItemBundleRelation bi = new ItemBundleRelation();
            bi.setBundleId(bundleId);
            bi.setItemId(entry.getKey());
            bi.setQuantity(entry.getValue() != null && entry.getValue() > 0 ? entry.getValue() : 1);
            save(bi);
        }
    }

    @Override
    public void removeItem(Integer bundleId, Integer itemId) {
        remove(new LambdaQueryWrapper<ItemBundleRelation>()
                .eq(ItemBundleRelation::getBundleId, bundleId)
                .eq(ItemBundleRelation::getItemId, itemId));
    }

    @Override
    public List<Integer> findBundleIdsByItemId(Integer itemId) {
        return list(new LambdaQueryWrapper<ItemBundleRelation>()
                .eq(ItemBundleRelation::getItemId, itemId))
                .stream()
                .map(ItemBundleRelation::getBundleId)
                .collect(Collectors.toList());
    }
}
