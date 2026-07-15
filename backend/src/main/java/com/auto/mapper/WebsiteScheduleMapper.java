package com.auto.mapper;

import com.auto.entity.WebsiteSchedule;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.Map;

/**
 * 账号调度 Mapper。联表查询返回 snake_case 键的 Map，直接作为接口响应。
 * SQL 定义在 resources/mapper/WebsiteScheduleMapper.xml
 */
@Mapper
public interface WebsiteScheduleMapper extends BaseMapper<WebsiteSchedule> {

    /** 联表查询调度配置列表（含账号与网站信息），返回 snake_case 键的 Map。 */
    List<Map<String, Object>> searchWithRelations(@Param("keyword") String keyword,
                                                  @Param("scheduleType") String scheduleType);
}
