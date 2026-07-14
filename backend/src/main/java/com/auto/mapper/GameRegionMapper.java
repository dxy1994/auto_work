package com.auto.mapper;

import com.auto.entity.GameRegion;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface GameRegionMapper extends BaseMapper<GameRegion> {

    @Select("select max(sort_order) from game_regions where game_id = #{gameId}")
    Integer maxSortOrder(@Param("gameId") Integer gameId);
}
