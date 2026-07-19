package com.auto.service.impl;

import com.auto.entity.PlatformSchedule;
import com.auto.mapper.PlatformScheduleMapper;
import com.auto.service.PlatformScheduleService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class PlatformScheduleServiceImpl extends ServiceImpl<PlatformScheduleMapper, PlatformSchedule>
        implements PlatformScheduleService {

    @Override
    public PlatformSchedule findByAccountId(Integer accountId) {
        return getOne(new LambdaQueryWrapper<PlatformSchedule>()
                .eq(PlatformSchedule::getAccountId, accountId), false);
    }

    @Override
    public List<Map<String, Object>> searchWithRelations(String keyword, String scheduleType) {
        return baseMapper.searchWithRelations(keyword, scheduleType);
    }
}
