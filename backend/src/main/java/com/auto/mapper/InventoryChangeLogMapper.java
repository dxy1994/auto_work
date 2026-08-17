package com.auto.mapper;

import com.auto.entity.InventoryChangeLog;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/** 库存变更审计日志 Mapper。 */
@Mapper
public interface InventoryChangeLogMapper extends BaseMapper<InventoryChangeLog> {

    /** 按库存记录ID查询变更日志，按时间倒序。 */
    List<InventoryChangeLog> findByInventoryId(@Param("inventoryId") Integer inventoryId);
}
