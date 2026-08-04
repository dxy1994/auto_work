package com.auto.service.impl;

import com.auto.entity.SystemControl;
import com.auto.mapper.SystemControlMapper;
import com.auto.service.SystemControlService;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
public class SystemControlServiceImpl extends ServiceImpl<SystemControlMapper, SystemControl>
        implements SystemControlService {

    @Override
    @Transactional
    public synchronized SystemControl getControl() {
        SystemControl control = getById(SystemControl.SINGLETON_ID);
        if (control != null) {
            return control;
        }
        control = new SystemControl();
        control.setId(SystemControl.SINGLETON_ID);
        control.setAutoGameTradeEnabled(1);
        control.setPageGuidesVisible(1);
        save(control);
        return control;
    }

    @Override
    @Transactional
    public SystemControl updateControls(
            Boolean autoGameTradeEnabled,
            Boolean pageGuidesVisible) {
        SystemControl control = getControl();
        if (autoGameTradeEnabled != null) {
            control.setAutoGameTradeEnabled(autoGameTradeEnabled ? 1 : 0);
        }
        if (pageGuidesVisible != null) {
            control.setPageGuidesVisible(pageGuidesVisible ? 1 : 0);
        }
        control.setUpdatedAt(LocalDateTime.now());
        updateById(control);
        return control;
    }

    @Override
    public boolean isAutoGameTradeEnabled() {
        return Integer.valueOf(1).equals(getControl().getAutoGameTradeEnabled());
    }
}
