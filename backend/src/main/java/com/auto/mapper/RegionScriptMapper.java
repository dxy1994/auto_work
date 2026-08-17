package com.auto.mapper;

import com.auto.entity.RegionScript;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface RegionScriptMapper extends BaseMapper<RegionScript> {

    Integer maxSortOrder(@Param("regionId") Integer regionId, @Param("category") String category);
}
