package com.auto.service.impl;

import com.auto.entity.Platform;
import com.auto.mapper.PlatformMapper;
import com.auto.service.PlatformService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class PlatformServiceImpl extends ServiceImpl<PlatformMapper, Platform> implements PlatformService {

    @Override
    public IPage<Platform> search(String category, String keyword, Page<Platform> page) {
        LambdaQueryWrapper<Platform> w = new LambdaQueryWrapper<>();
        w.eq(Platform::getIsActive, 1)
                .eq(category != null, Platform::getCategory, category)
                .like(keyword != null, Platform::getName, keyword)
                .orderByAsc(Platform::getSortOrder)
                .orderByDesc(Platform::getId);
        return page(page, w);
    }

    @Override
    public List<Platform> findAllActiveOrdered() {
        return list(new LambdaQueryWrapper<Platform>()
                .eq(Platform::getIsActive, 1)
                .orderByAsc(Platform::getSortOrder));
    }

    @Override
    public List<String> findDistinctCategories() {
        return baseMapper.findDistinctCategories();
    }
}
