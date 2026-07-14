package com.auto.service;

import com.auto.entity.GameItemOrder;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;

public interface GameItemOrderService extends IService<GameItemOrder> {

    IPage<GameItemOrder> search(Integer gameId, String status, String keyword, Page<GameItemOrder> page);

    void updateDeliveryStatus(Integer orderId, String expectedStatus, String targetStatus,
                              String assignmentId);
}
