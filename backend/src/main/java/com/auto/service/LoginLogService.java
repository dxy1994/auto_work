package com.auto.service;

import com.auto.entity.LoginLog;
import com.baomidou.mybatisplus.extension.service.IService;

import java.util.List;

public interface LoginLogService extends IService<LoginLog> {

    List<LoginLog> search(Integer websiteId, Integer accountId, int limit);
}
