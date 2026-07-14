package com.auto.service.impl;

import com.auto.entity.WebsiteSchedule;
import com.auto.mapper.WebsiteScheduleMapper;
import com.auto.service.WebsiteScheduleService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class WebsiteScheduleServiceImpl extends ServiceImpl<WebsiteScheduleMapper, WebsiteSchedule>
        implements WebsiteScheduleService {

    @Override
    public WebsiteSchedule findByAccountId(Integer accountId) {
        return getOne(new LambdaQueryWrapper<WebsiteSchedule>()
                .eq(WebsiteSchedule::getAccountId, accountId), false);
    }

    @Override
    public List<Map<String, Object>> searchWithRelations(String keyword, String scheduleType) {
        return baseMapper.searchWithRelations(keyword, scheduleType);
    }
}
