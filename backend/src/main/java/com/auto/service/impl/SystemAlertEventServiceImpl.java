package com.auto.service.impl;

import com.auto.entity.SystemAlertEvent;
import com.auto.mapper.SystemAlertEventMapper;
import com.auto.service.SystemAlertEventService;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

@Service
public class SystemAlertEventServiceImpl
        extends ServiceImpl<SystemAlertEventMapper, SystemAlertEvent>
        implements SystemAlertEventService {
}
