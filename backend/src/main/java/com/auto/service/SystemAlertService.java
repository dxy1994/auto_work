package com.auto.service;

import com.auto.entity.SystemAlert;
import com.auto.entity.SystemAlertEvent;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface SystemAlertService extends IService<SystemAlert> {

    List<SystemAlert> listOpen();

    List<SystemAlert> listHistory(int limit);

    IPage<SystemAlert> searchHistory(String status, String alertType, String severity,
                                     Integer machineId, Integer accountId, String keyword,
                                     Page<SystemAlert> page);

    List<SystemAlertEvent> listEvents(long alertId);

    SystemAlert openOrRefresh(String alertType, String sourceKey, Integer machineId,
                              Integer accountId, String severity, String title, String message);

    SystemAlert dismiss(long alertId);

    SystemAlert dismissBySourceKey(String sourceKey);

    void recordClientEvent(long alertId, String eventType, String details);
}
