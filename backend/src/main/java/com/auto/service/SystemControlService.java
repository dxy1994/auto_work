package com.auto.service;

import com.auto.entity.SystemControl;
import com.baomidou.mybatisplus.spring.service.IService;

public interface SystemControlService extends IService<SystemControl> {

    SystemControl getControl();

    SystemControl updateAutoGameTradeEnabled(boolean enabled);

    boolean isAutoGameTradeEnabled();
}
