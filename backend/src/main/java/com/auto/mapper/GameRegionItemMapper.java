package com.auto.mapper;

import com.auto.entity.GameRegionItem;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

/**
 * 大区库存 Mapper。联表查询返回 snake_case 键的 Map，直接作为接口响应。
 */
@Mapper
public interface GameRegionItemMapper extends BaseMapper<GameRegionItem> {

    String JOIN_SELECT = "select inv.id as id, inv.game_id as game_id, inv.region_id as region_id, "
            + "inv.item_id as item_id, item.name as item_name, item.code as item_code, "
            + "item.image as item_image, inv.stock as stock, inv.is_active as is_active, "
            + "inv.created_at as created_at, inv.updated_at as updated_at "
            + "from game_region_items inv join game_items item on inv.item_id = item.id "
            + "where inv.is_active = 1 and item.is_active = 1 "
            + "and (#{gameId} is null or inv.game_id = #{gameId}) "
            + "and (#{regionId} is null or inv.region_id = #{regionId}) ";

    /** 分页联表查询库存（含物品信息），返回 snake_case 键的 Map。 */
    @Select("<script>" + JOIN_SELECT
            + "<if test='keyword != null'> and item.name like concat('%', #{keyword}, '%') </if>"
            + "order by item.sort_order asc, item.id desc"
            + "</script>")
    IPage<Map<String, Object>> searchWithItem(IPage<Map<String, Object>> page,
                                              @Param("gameId") Integer gameId,
                                              @Param("regionId") Integer regionId,
                                              @Param("keyword") String keyword);

    @Select(JOIN_SELECT + "order by item.sort_order asc, item.id desc")
    List<Map<String, Object>> findAllWithItem(@Param("gameId") Integer gameId,
                                              @Param("regionId") Integer regionId);
}
