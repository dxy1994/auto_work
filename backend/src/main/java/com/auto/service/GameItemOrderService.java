package com.auto.service;

import com.auto.entity.GameItemOrder;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Set;

public interface GameItemOrderService extends IService<GameItemOrder> {

    IPage<GameItemOrder> search(Integer websiteId, Integer gameId, String status,
                                String deliveryStatus, LocalDateTime createdFrom,
                                LocalDateTime createdTo, String keyword,
                                Page<GameItemOrder> page);

    GameItemOrder findByWebsiteIdAndSourceOrderNo(Integer websiteId, String sourceOrderNo);

    /** 批量查重：返回已存在的 source_order_no 集合，用于 Worker 端预过滤。 */
    Set<String> findExistingSourceOrderNos(Integer websiteId, List<String> sourceOrderNos);

    void updateDeliveryStatus(Integer orderId, String expectedStatus, String targetStatus,
                              String assignmentId);

    /** 仅更新订单错误信息，避免状态转换异常时整行更新再次失败。 */
    void updateLastError(Integer orderId, String errorCode, String errorMessage);
}
