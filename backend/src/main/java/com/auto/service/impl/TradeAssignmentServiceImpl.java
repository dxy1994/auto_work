package com.auto.service.impl;

import com.auto.entity.TradeAssignment;
import com.auto.mapper.TradeAssignmentMapper;
import com.auto.service.TradeAssignmentService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

@Service
public class TradeAssignmentServiceImpl extends ServiceImpl<TradeAssignmentMapper, TradeAssignment>
        implements TradeAssignmentService {
}
