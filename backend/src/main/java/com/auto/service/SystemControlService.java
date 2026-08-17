package com.auto.service;

import com.auto.entity.SystemControl;
import com.baomidou.mybatisplus.spring.service.IService;

public interface SystemControlService extends IService<SystemControl> {

    SystemControl getControl();

    SystemControl updateControls(Boolean autoGameTradeEnabled, Boolean pageGuidesVisible);

    default SystemControl updateAutoGameTradeEnabled(boolean enabled) {
        return updateControls(enabled, null);
    }

    boolean isAutoGameTradeEnabled();
}
