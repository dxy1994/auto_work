package com.auto.config;

import com.fasterxml.jackson.databind.cfg.CoercionAction;
import com.fasterxml.jackson.databind.cfg.CoercionInputShape;
import com.fasterxml.jackson.databind.type.LogicalType;
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Jackson 定制：允许布尔值反序列化为整型字段。
 * 前端对 is_default / is_active 等字段发送 true/false，而 entity 中为 Integer(1/0)，
 * 移除 DTO 后直接绑定 entity，需要此强制转换（true→1，false→0）。
 */
@Configuration
public class JacksonConfig {

    @Bean
    public Jackson2ObjectMapperBuilderCustomizer booleanToIntegerCoercion() {
        return builder -> builder.postConfigurer(mapper ->
                mapper.coercionConfigFor(LogicalType.Integer)
                        .setCoercion(CoercionInputShape.Boolean, CoercionAction.TryConvert));
    }
}
