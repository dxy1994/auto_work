package com.auto.trade;

import com.auto.entity.GameItem;
import com.auto.entity.GameItemOrder;
import com.auto.entity.GameItemOrderDetail;
import com.auto.entity.GameRegionInventory;
import com.auto.entity.ItemBundleRelation;
import com.auto.service.GameItemOrderDetailService;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameItemService;
import com.auto.service.GameRegionInventoryService;
import com.auto.service.ItemBundleRelationService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 根据订单物品编码/名称生成子订单明细；可安全用于首次生成和失败重试。 */
@Service
public class OrderDetailGenerationService {

    private final GameItemService gameItemService;
    private final ItemBundleRelationService bundleItemService;
    private final GameItemOrderDetailService detailService;
    private final GameItemOrderService orderService;
    private final GameRegionInventoryService regionInventoryService;

    public OrderDetailGenerationService(
            GameItemService gameItemService,
            ItemBundleRelationService bundleItemService,
            GameItemOrderDetailService detailService,
            GameItemOrderService orderService,
            GameRegionInventoryService regionInventoryService) {
        this.gameItemService = gameItemService;
        this.bundleItemService = bundleItemService;
        this.detailService = detailService;
        this.orderService = orderService;
        this.regionInventoryService = regionInventoryService;
    }

    public List<GameItemOrderDetail> ensureDetails(GameItemOrder requestedOrder) {
        if (requestedOrder == null || requestedOrder.getId() == null) {
            throw new IllegalStateException("订单不存在，无法生成子订单");
        }

        // 锁定主订单，避免多个页面同时重试时重复插入子订单。
        GameItemOrder order = orderService.getOne(
                new LambdaQueryWrapper<GameItemOrder>()
                        .eq(GameItemOrder::getId, requestedOrder.getId())
                        .last("FOR UPDATE"),
                false);
        if (order == null) {
            throw new IllegalStateException("订单不存在，无法生成子订单");
        }

        List<GameItemOrderDetail> existing = detailService.findByOrderId(order.getId());
        if (!existing.isEmpty()) {
            return existing;
        }
        if (order.getGameId() == null || order.getGameId() <= 0) {
            throw new IllegalStateException("订单缺少有效游戏，无法生成子订单");
        }
        String itemCodeOrName = order.getTradeItemName();
        if (itemCodeOrName == null || itemCodeOrName.isBlank()) {
            throw new IllegalStateException("订单缺少交易物品编码，无法生成子订单");
        }

        GameItem matchedItem = gameItemService.findActiveByGameIdAndCodeOrName(
                order.getGameId(), itemCodeOrName.trim());
        if (matchedItem == null) {
            throw new IllegalStateException(
                    "未找到编码或名称匹配的启用物品: " + itemCodeOrName);
        }

        int platformQuantity = resolvePlatformQuantity(order);
        List<GameItemOrderDetail> generated = Integer.valueOf(1).equals(matchedItem.getIsBundle())
                ? buildBundleDetails(order, matchedItem, platformQuantity)
                : List.of(buildDetail(order, matchedItem, null, platformQuantity));
        for (GameItemOrderDetail detail : generated) {
            detailService.save(detail);
        }
        order.setTotalAmount(generated.stream()
                .map(GameItemOrderDetail::getSubtotal)
                .reduce(BigDecimal.ZERO, BigDecimal::add));
        orderService.updateById(order);
        return generated;
    }

    private List<GameItemOrderDetail> buildBundleDetails(
            GameItemOrder order,
            GameItem bundle,
            int platformQuantity) {
        List<ItemBundleRelation> relations = bundleItemService.findRelationsByBundleId(bundle.getId());
        if (relations.isEmpty()) {
            throw new IllegalStateException("套装尚未配置子物品: " + bundle.getName());
        }
        Map<Integer, GameItem> children = new LinkedHashMap<>();
        gameItemService.listByIds(relations.stream()
                        .map(ItemBundleRelation::getItemId)
                        .distinct()
                        .toList())
                .forEach(item -> children.put(item.getId(), item));

        List<GameItemOrderDetail> details = new ArrayList<>();
        for (ItemBundleRelation relation : relations) {
            GameItem child = children.get(relation.getItemId());
            if (child == null || !Integer.valueOf(1).equals(child.getIsActive())) {
                throw new IllegalStateException(
                        "套装包含不存在或已停用的子物品，item_id=" + relation.getItemId());
            }
            int bundleItemQuantity = relation.getQuantity() != null && relation.getQuantity() > 0
                    ? relation.getQuantity()
                    : 1;
            int quantity;
            try {
                quantity = Math.multiplyExact(bundleItemQuantity, platformQuantity);
            } catch (ArithmeticException e) {
                throw new IllegalStateException(
                        "套装子物品数量超出系统支持范围，item_id=" + relation.getItemId(), e);
            }
            details.add(buildDetail(order, child, bundle.getName(), quantity));
        }
        return details;
    }

    private int resolvePlatformQuantity(GameItemOrder order) {
        if (order.getSaleQuantity() == null || order.getSaleQuantity() <= 0) {
            throw new IllegalStateException("订单缺少有效的平台已售数量，无法生成子订单");
        }
        return order.getSaleQuantity();
    }

    private GameItemOrderDetail buildDetail(
            GameItemOrder order,
            GameItem item,
            String bundleName,
            int quantity) {
        GameItemOrderDetail detail = new GameItemOrderDetail();
        detail.setOrderId(order.getId());
        detail.setItemId(item.getId());
        detail.setItemName(item.getName());
        detail.setItemImage(item.getImage());
        detail.setItemSelectedImage(item.getSelectedImage());
        detail.setQuantity(quantity);
        BigDecimal price = item.getPrice() != null ? item.getPrice() : BigDecimal.ZERO;
        detail.setUnitPrice(price);
        detail.setSubtotal(price.multiply(BigDecimal.valueOf(quantity)));
        detail.setBundleName(bundleName);

        if (order.getRegionId() != null && order.getRegionId() > 0) {
            GameRegionInventory inventory = regionInventoryService.getOne(
                    new LambdaQueryWrapper<GameRegionInventory>()
                            .eq(GameRegionInventory::getRegionId, order.getRegionId())
                            .eq(GameRegionInventory::getItemId, item.getId())
                            .eq(GameRegionInventory::getIsActive, 1),
                    false);
            if (inventory != null) {
                detail.setPurchasePrice(inventory.getPurchasePrice());
            }
        }
        return detail;
    }
}
