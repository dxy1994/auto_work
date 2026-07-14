package com.auto.service.impl;

import com.auto.entity.RegionScript;
import com.auto.mapper.RegionScriptMapper;
import com.auto.service.RegionScriptService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

@Service
public class RegionScriptServiceImpl extends ServiceImpl<RegionScriptMapper, RegionScript>
        implements RegionScriptService {

    @Override
    public IPage<RegionScript> search(Integer regionId, String category, String keyword,
                                      Page<RegionScript> page) {
        LambdaQueryWrapper<RegionScript> w = new LambdaQueryWrapper<>();
        w.eq(RegionScript::getIsActive, 1)
                .eq(regionId != null, RegionScript::getRegionId, regionId)
                .eq(category != null, RegionScript::getCategory, category)
                .like(keyword != null, RegionScript::getTitle, keyword)
                .orderByAsc(RegionScript::getSortOrder)
                .orderByDesc(RegionScript::getId);
        return page(page, w);
    }
}
