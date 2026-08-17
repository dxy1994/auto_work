package com.auto.service;

import com.auto.entity.PlatformSchedule;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;
import java.util.Map;

public interface PlatformScheduleService extends IService<PlatformSchedule> {

    PlatformSchedule findByAccountId(Integer accountId);

    List<Map<String, Object>> searchWithRelations(String keyword, String scheduleType);
}
