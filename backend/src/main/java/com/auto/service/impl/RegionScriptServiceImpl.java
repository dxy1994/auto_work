package com.auto.service.impl;

import com.auto.entity.RegionScript;
import com.auto.mapper.RegionScriptMapper;
import com.auto.service.RegionScriptService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

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

    @Override
    public RegionScript findFirstByRegionIdAndCategory(int regionId, String category) {
        return getOne(new LambdaQueryWrapper<RegionScript>()
                .eq(RegionScript::getRegionId, regionId)
                .eq(RegionScript::getCategory, category)
                .eq(RegionScript::getIsActive, 1)
                .orderByAsc(RegionScript::getSortOrder)
                .last("LIMIT 1"), false);
    }

    @Override
    public List<RegionScript> findAllByRegionIdAndCategory(int regionId, String category) {
        return list(new LambdaQueryWrapper<RegionScript>()
                .eq(RegionScript::getRegionId, regionId)
                .eq(RegionScript::getCategory, category)
                .eq(RegionScript::getIsActive, 1)
                .orderByAsc(RegionScript::getSortOrder));
    }
}
