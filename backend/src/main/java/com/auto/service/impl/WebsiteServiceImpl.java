package com.auto.service.impl;

import com.auto.entity.Website;
import com.auto.mapper.WebsiteMapper;
import com.auto.service.WebsiteService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class WebsiteServiceImpl extends ServiceImpl<WebsiteMapper, Website> implements WebsiteService {

    @Override
    public IPage<Website> search(String category, String keyword, Page<Website> page) {
        LambdaQueryWrapper<Website> w = new LambdaQueryWrapper<>();
        w.eq(Website::getIsActive, 1)
                .eq(category != null, Website::getCategory, category)
                .like(keyword != null, Website::getName, keyword)
                .orderByAsc(Website::getSortOrder)
                .orderByDesc(Website::getId);
        return page(page, w);
    }

    @Override
    public List<Website> findAllActiveOrdered() {
        return list(new LambdaQueryWrapper<Website>()
                .eq(Website::getIsActive, 1)
                .orderByAsc(Website::getSortOrder));
    }

    @Override
    public List<String> findDistinctCategories() {
        return baseMapper.findDistinctCategories();
    }
}
