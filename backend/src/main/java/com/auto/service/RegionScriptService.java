package com.auto.service;

import com.auto.entity.RegionScript;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

public interface RegionScriptService extends IService<RegionScript> {

    IPage<RegionScript> search(Integer regionId, String category, String keyword, Page<RegionScript> page);
}
