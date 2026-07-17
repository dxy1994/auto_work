package com.auto.mapper;

import com.auto.entity.GameScript;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface GameScriptMapper extends BaseMapper<GameScript> {

    Integer maxSortOrder(@Param("gameId") Integer gameId, @Param("category") String category);
}
