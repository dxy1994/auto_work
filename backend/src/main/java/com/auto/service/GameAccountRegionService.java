package com.auto.service;

import com.auto.entity.GameAccountRegion;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface GameAccountRegionService extends IService<GameAccountRegion> {

    /** 查询某个账号的所有活跃大区关联。 */
    List<GameAccountRegion> findByAccountIdActive(Integer gameAccountId);

    /** 查询某个大区下所有活跃账号关联。 */
    List<GameAccountRegion> findByRegionIdActive(Integer regionId);

    /** 查询指定游戏+大区下的所有活跃账号关联。 */
    List<GameAccountRegion> findByGameIdAndRegionIdActive(Integer gameId, Integer regionId);

    /** 批量获取账号的大区ID列表。 */
    List<Integer> findRegionIdsByAccountId(Integer gameAccountId);
}
