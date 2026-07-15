package com.auto.service.impl;

import com.auto.entity.GameItemOrder;
import com.auto.mapper.GameItemOrderMapper;
import com.auto.service.GameItemOrderService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class GameItemOrderServiceImpl extends ServiceImpl<GameItemOrderMapper, GameItemOrder>
        implements GameItemOrderService {

    @Override
    public IPage<GameItemOrder> search(Integer gameId, String status, String keyword, Page<GameItemOrder> page) {
        LambdaQueryWrapper<GameItemOrder> w = new LambdaQueryWrapper<>();
        w.eq(gameId != null, GameItemOrder::getGameId, gameId)
                .eq(status != null, GameItemOrder::getStatus, status)
                .and(keyword != null, q -> q.like(GameItemOrder::getOrderNo, keyword)
                        .or().like(GameItemOrder::getCustomerName, keyword))
                .orderByDesc(GameItemOrder::getId);
        return page(page, w);
    }

    @Override
    public GameItemOrder findByWebsiteIdAndSourceOrderNo(Integer websiteId, String sourceOrderNo) {
        return getOne(new LambdaQueryWrapper<GameItemOrder>()
                .eq(GameItemOrder::getWebsiteId, websiteId)
                .eq(GameItemOrder::getSourceOrderNo, sourceOrderNo), false);
    }

    @Override
    public Set<String> findExistingSourceOrderNos(Integer websiteId, List<String> sourceOrderNos) {
        if (sourceOrderNos == null || sourceOrderNos.isEmpty()) {
            return Collections.emptySet();
        }
        List<GameItemOrder> list = list(new LambdaQueryWrapper<GameItemOrder>()
                .select(GameItemOrder::getSourceOrderNo)
                .eq(GameItemOrder::getWebsiteId, websiteId)
                .in(GameItemOrder::getSourceOrderNo, sourceOrderNos));
        return list.stream()
                .map(GameItemOrder::getSourceOrderNo)
                .collect(Collectors.toSet());
    }

    @Override
    public void updateDeliveryStatus(Integer orderId, String expectedStatus, String targetStatus,
                                     String assignmentId) {
        GameItemOrder current = getById(orderId);
        if (current == null || !expectedStatus.equals(current.getDeliveryStatus())) {
            throw new IllegalStateException("订单状态已变化，请刷新后重试");
        }
        Integer rowVersion = current.getRowVersion() == null ? 0 : current.getRowVersion();
        boolean updated = update(new LambdaUpdateWrapper<GameItemOrder>()
                .eq(GameItemOrder::getId, orderId)
                .eq(GameItemOrder::getDeliveryStatus, expectedStatus)
                .eq(GameItemOrder::getRowVersion, rowVersion)
                .set(GameItemOrder::getDeliveryStatus, targetStatus)
                .set(GameItemOrder::getAssignmentId, assignmentId)
                .setSql("row_version = row_version + 1"));
        if (!updated) {
            throw new IllegalStateException("订单状态已变化，请刷新后重试");
        }
    }
}
