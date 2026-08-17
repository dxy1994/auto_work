package com.auto.service;

import com.auto.entity.RegionScript;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface RegionScriptService extends IService<RegionScript> {

    IPage<RegionScript> search(Integer regionId, String category, String keyword, Page<RegionScript> page);

    /** 按大区ID和分类获取第一条激活话术（按 sort_order 排序）。 */
    RegionScript findFirstByRegionIdAndCategory(int regionId, String category);

    /** 按大区ID和分类获取全部激活话术（按 sort_order 排序）。 */
    List<RegionScript> findAllByRegionIdAndCategory(int regionId, String category);

    /** 获取指定大区+分类下的最大 sort_order。 */
    Integer maxSortOrder(Integer regionId, String category);
}
