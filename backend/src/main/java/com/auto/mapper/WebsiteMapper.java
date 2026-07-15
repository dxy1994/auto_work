package com.auto.mapper;

import com.auto.entity.Website;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

import java.util.List;

@Mapper
public interface WebsiteMapper extends BaseMapper<Website> {

    List<String> findDistinctCategories();
}
