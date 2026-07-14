package com.auto;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 网址统一管理系统 - Spring Boot 主入口。
 *
 * <p>支持网站管理、多账号管理、分布式 worker 自动化登录（经 WebSocket 下发任务）。
 */
@SpringBootApplication
@EnableScheduling
@MapperScan("com.auto.mapper")
public class AutoApplication {

    public static void main(String[] args) {
        SpringApplication.run(AutoApplication.class, args);
    }
}
