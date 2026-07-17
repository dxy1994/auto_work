package com.auto.service.impl;

import com.auto.entity.BundleItem;
import com.auto.mapper.BundleItemMapper;
import com.auto.service.BundleItemService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

@Service
public class BundleItemServiceImpl extends ServiceImpl<BundleItemMapper, BundleItem> implements BundleItemService {

    @Override
    public List<Integer> findItemIdsByBundleId(Integer bundleId) {
        return list(new LambdaQueryWrapper<BundleItem>()
                .eq(BundleItem::getBundleId, bundleId))
                .stream()
                .map(BundleItem::getItemId)
                .collect(Collectors.toList());
    }

    @Override
    public void addItems(Integer bundleId, List<Integer> itemIds) {
        for (Integer itemId : itemIds) {
            BundleItem bi = new BundleItem();
            bi.setBundleId(bundleId);
            bi.setItemId(itemId);
            save(bi);
        }
    }

    @Override
    public void removeItem(Integer bundleId, Integer itemId) {
        remove(new LambdaQueryWrapper<BundleItem>()
                .eq(BundleItem::getBundleId, bundleId)
                .eq(BundleItem::getItemId, itemId));
    }

    @Override
    public List<Integer> findBundleIdsByItemId(Integer itemId) {
        return list(new LambdaQueryWrapper<BundleItem>()
                .eq(BundleItem::getItemId, itemId))
                .stream()
                .map(BundleItem::getBundleId)
                .collect(Collectors.toList());
    }
}
