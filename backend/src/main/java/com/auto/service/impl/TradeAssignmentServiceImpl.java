package com.auto.service.impl;

import com.auto.entity.TradeAssignment;
import com.auto.mapper.TradeAssignmentMapper;
import com.auto.service.TradeAssignmentService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.Collection;
import java.util.List;

@Service
public class TradeAssignmentServiceImpl extends ServiceImpl<TradeAssignmentMapper, TradeAssignment>
        implements TradeAssignmentService {

    @Override
    public List<TradeAssignment> findByStatuses(Collection<String> statuses) {
        if (statuses == null || statuses.isEmpty()) return List.of();
        return list(new LambdaQueryWrapper<TradeAssignment>()
                .in(TradeAssignment::getStatus, statuses));
    }
}
