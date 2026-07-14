package com.auto.mapper;

import com.auto.entity.Website;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface WebsiteMapper extends BaseMapper<Website> {

    @Select("select distinct category from websites where is_active = 1 and category is not null")
    List<String> findDistinctCategories();
}
