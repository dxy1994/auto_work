package com.auto.service;

import com.auto.entity.TradeAssignment;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.Collection;
import java.util.List;

public interface TradeAssignmentService extends IService<TradeAssignment> {

    List<TradeAssignment> findByStatuses(Collection<String> statuses);
}
