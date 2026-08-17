package com.auto.mapper;

import com.auto.entity.GameRegionInventory;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.Map;

/**
 * 大区库存 Mapper。联表查询返回 snake_case 键的 Map，直接作为接口响应。
 * SQL 定义在 resources/mapper/GameRegionInventoryMapper.xml
 */
@Mapper
public interface GameRegionInventoryMapper extends BaseMapper<GameRegionInventory> {

    /** 分页联表查询库存（含物品信息及指定商铺定价），返回 snake_case 键的 Map。 */
    IPage<Map<String, Object>> searchWithItem(IPage<Map<String, Object>> page,
                                              @Param("gameId") Integer gameId,
                                              @Param("regionId") Integer regionId,
                                              @Param("itemId") Integer itemId,
                                              @Param("hasStock") Integer hasStock,
                                              @Param("keyword") String keyword,
                                              @Param("accountId") Integer accountId);

    List<Map<String, Object>> findAllWithItem(@Param("gameId") Integer gameId,
                                              @Param("regionId") Integer regionId,
                                              @Param("accountId") Integer accountId);
}
