package com.auto.config;


import org.springframework.boot.jackson.autoconfigure.JsonMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import tools.jackson.databind.cfg.CoercionAction;
import tools.jackson.databind.cfg.CoercionInputShape;
import tools.jackson.databind.type.LogicalType;

/**
 * Jackson 定制：允许布尔值反序列化为整型字段。
 * 前端对 is_default / is_active 等字段发送 true/false，而 entity 中为 Integer(1/0)，
 * 移除 DTO 后直接绑定 entity，需要此强制转换（true→1，false→0）。
 */
@Configuration
public class JacksonConfig {

    @Bean
    public JsonMapperBuilderCustomizer booleanToIntegerCoercion() {
        return builder -> builder.withCoercionConfig(LogicalType.Integer,
                config -> config.setCoercion(CoercionInputShape.Boolean, CoercionAction.TryConvert));
    }
}
