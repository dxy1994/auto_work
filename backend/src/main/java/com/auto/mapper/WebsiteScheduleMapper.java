package com.auto.mapper;

import com.auto.entity.WebsiteSchedule;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

/**
 * 账号调度 Mapper。联表查询返回 snake_case 键的 Map，直接作为接口响应。
 */
@Mapper
public interface WebsiteScheduleMapper extends BaseMapper<WebsiteSchedule> {

    /** 联表查询调度配置列表（含账号与网站信息），返回 snake_case 键的 Map。 */
    @Select("<script>"
            + "select s.id as id, s.account_id as account_id, s.name as name, s.code as code, "
            + "s.refresh_interval as refresh_interval, s.schedule_type as schedule_type, "
            + "s.schedule_time as schedule_time, s.schedule_cron as schedule_cron, "
            + "s.alert_audio_path as alert_audio_path, s.is_enabled as is_enabled, "
            + "s.created_at as created_at, s.updated_at as updated_at, "
            + "a.label as account_label, a.username as account_username, "
            + "w.name as website_name, w.url as website_url, "
            + "coalesce(w.login_type, '') as login_type, w.category as category "
            + "from website_schedules s "
            + "join accounts a on a.id = s.account_id "
            + "join websites w on w.id = a.website_id "
            + "<where>"
            + "<if test='keyword != null'> and (a.label like concat('%', #{keyword}, '%') "
            + "or a.username like concat('%', #{keyword}, '%')) </if>"
            + "<if test='scheduleType != null'> and s.schedule_type = #{scheduleType} </if>"
            + "</where>"
            + "order by s.updated_at desc"
            + "</script>")
    List<Map<String, Object>> searchWithRelations(@Param("keyword") String keyword,
                                                  @Param("scheduleType") String scheduleType);
}
