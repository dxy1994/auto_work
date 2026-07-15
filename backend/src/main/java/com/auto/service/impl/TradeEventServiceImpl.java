package com.auto.service.impl;

import com.auto.entity.TradeEvent;
import com.auto.mapper.TradeEventMapper;
import com.auto.service.TradeEventService;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

@Service
public class TradeEventServiceImpl extends ServiceImpl<TradeEventMapper, TradeEvent>
        implements TradeEventService {
}
