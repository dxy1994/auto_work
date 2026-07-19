package com.auto.service;

import com.auto.entity.Platform;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface PlatformService extends IService<Platform> {

    IPage<Platform> search(String category, String keyword, Page<Platform> page);

    List<Platform> findAllActiveOrdered();

    List<String> findDistinctCategories();
}
