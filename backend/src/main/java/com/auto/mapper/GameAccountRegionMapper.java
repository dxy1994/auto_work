package com.auto.mapper;

import com.auto.entity.GameAccountRegion;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface GameAccountRegionMapper extends BaseMapper<GameAccountRegion> {

    /** 联表 game_accounts 查询指定游戏+大区的账号-大区关联。 */
    List<GameAccountRegion> findByGameIdAndRegionIdActive(@Param("gameId") Integer gameId,
                                                          @Param("regionId") Integer regionId);
}
