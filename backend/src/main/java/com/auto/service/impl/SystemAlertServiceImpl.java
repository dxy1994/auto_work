package com.auto.service.impl;

import com.auto.common.ApiException;
import com.auto.entity.SystemAlert;
import com.auto.mapper.SystemAlertMapper;
import com.auto.service.SystemAlertService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Service
public class SystemAlertServiceImpl extends ServiceImpl<SystemAlertMapper, SystemAlert>
        implements SystemAlertService {

    @Override
    public List<SystemAlert> listOpen() {
        return list(new LambdaQueryWrapper<SystemAlert>()
                .eq(SystemAlert::getStatus, "open")
                .orderByAsc(SystemAlert::getOccurredAt)
                .last("LIMIT 200"));
    }

    @Override
    @Transactional
    public SystemAlert openOrRefresh(String alertType, String sourceKey, Integer machineId,
                                     Integer accountId, String severity, String title, String message) {
        LocalDateTime now = LocalDateTime.now();
        SystemAlert alert = getOne(new LambdaQueryWrapper<SystemAlert>()
                .eq(SystemAlert::getSourceKey, sourceKey), false);
        if (alert == null) {
            alert = new SystemAlert();
            alert.setAlertType(alertType);
            alert.setSourceKey(sourceKey);
            alert.setCreatedAt(now);
        }
        alert.setMachineId(machineId);
        alert.setAccountId(accountId);
        alert.setSeverity(severity);
        alert.setTitle(title);
        alert.setMessage(message);
        alert.setStatus("open");
        alert.setOccurredAt(now);
        alert.setDismissedAt(null);
        alert.setUpdatedAt(now);
        saveOrUpdate(alert);
        return alert;
    }

    @Override
    @Transactional
    public SystemAlert dismiss(long alertId) {
        SystemAlert alert = getById(alertId);
        if (alert == null) {
            throw ApiException.notFound("提醒不存在");
        }
        return dismissAlert(alert);
    }

    @Override
    @Transactional
    public SystemAlert dismissBySourceKey(String sourceKey) {
        SystemAlert alert = getOne(new LambdaQueryWrapper<SystemAlert>()
                .eq(SystemAlert::getSourceKey, sourceKey), false);
        if (alert == null) {
            return null;
        }
        return dismissAlert(alert);
    }

    private SystemAlert dismissAlert(SystemAlert alert) {
        if (!"dismissed".equals(alert.getStatus())) {
            LocalDateTime now = LocalDateTime.now();
            alert.setStatus("dismissed");
            alert.setDismissedAt(now);
            alert.setUpdatedAt(now);
            updateById(alert);
        }
        return alert;
    }
}
