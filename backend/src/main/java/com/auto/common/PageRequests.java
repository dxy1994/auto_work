package com.auto.common;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;

/** 统一校验前端使用的 1-based 分页参数，并构造 MyBatis-Plus 分页对象。 */
public final class PageRequests {

    private static final int MAX_PAGE_SIZE = 1000;

    private PageRequests() {
    }

    /** 构造 MyBatis-Plus 分页对象（current 为 1-based）。 */
    public static <T> Page<T> of(int page, int pageSize) {
        if (page < 1) {
            throw ApiException.badRequest("page 必须大于等于 1");
        }
        validateSize(pageSize, "page_size");
        return Page.of(page, pageSize);
    }

    public static int limit(int limit) {
        validateSize(limit, "limit");
        return limit;
    }

    private static void validateSize(int size, String name) {
        if (size < 1 || size > MAX_PAGE_SIZE) {
            throw ApiException.badRequest(name + " 必须在 1 到 " + MAX_PAGE_SIZE + " 之间");
        }
    }
}
