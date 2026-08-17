package com.auto.mapper;

import com.auto.entity.Platform;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

import java.util.List;

@Mapper
public interface PlatformMapper extends BaseMapper<Platform> {

    List<String> findDistinctCategories();
}
