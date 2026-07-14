package com.auto.service;

import com.auto.entity.WebsiteSchedule;
import com.baomidou.mybatisplus.extension.service.IService;

import java.util.List;
import java.util.Map;

public interface WebsiteScheduleService extends IService<WebsiteSchedule> {

    WebsiteSchedule findByAccountId(Integer accountId);

    List<Map<String, Object>> searchWithRelations(String keyword, String scheduleType);
}
