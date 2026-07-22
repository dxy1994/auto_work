package com.auto.service;

import com.auto.entity.SystemAlert;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface SystemAlertService extends IService<SystemAlert> {

    List<SystemAlert> listOpen();

    SystemAlert openOrRefresh(String alertType, String sourceKey, Integer machineId,
                              Integer accountId, String severity, String title, String message);

    SystemAlert dismiss(long alertId);
}
