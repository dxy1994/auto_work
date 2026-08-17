package com.auto.mapper;

import com.auto.entity.GameRegion;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface GameRegionMapper extends BaseMapper<GameRegion> {

    Integer maxSortOrder(@Param("gameId") Integer gameId);
}
