package com.auto.service;

import com.auto.entity.Website;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface WebsiteService extends IService<Website> {

    IPage<Website> search(String category, String keyword, Page<Website> page);

    List<Website> findAllActiveOrdered();

    List<String> findDistinctCategories();
}
