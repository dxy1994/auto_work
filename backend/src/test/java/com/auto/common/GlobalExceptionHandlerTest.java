package com.auto.common;

import org.junit.jupiter.api.Test;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

import static org.junit.jupiter.api.Assertions.assertEquals;

class GlobalExceptionHandlerTest {

    private final GlobalExceptionHandler handler = new GlobalExceptionHandler();

    @Test
    void unknownExceptionDoesNotExposeInternalMessage() {
        var response = handler.handleOther(new RuntimeException("jdbc:mysql://secret-host/internal"));

        assertEquals(500, response.getStatusCode().value());
        assertEquals("服务器内部错误", response.getBody().get("detail"));
    }

    @Test
    void dataIntegrityViolationReturnsConflict() {
        var response = handler.handleConflict(new DataIntegrityViolationException("duplicate key detail"));

        assertEquals(409, response.getStatusCode().value());
        assertEquals("数据冲突，请检查是否重复提交", response.getBody().get("detail"));
    }

    @Test
    void missingRequiredParameterReturnsBadRequest() {
        var response = handler.handleBadRequest(
                new MissingServletRequestParameterException("account_id", "Integer"));

        assertEquals(400, response.getStatusCode().value());
        assertEquals("请求参数格式错误", response.getBody().get("detail"));
    }

    @Test
    void oversizedUploadReturnsPayloadTooLarge() {
        var response = handler.handleUploadTooLarge(new MaxUploadSizeExceededException(1024));

        assertEquals(413, response.getStatusCode().value());
        assertEquals("上传文件超过允许大小", response.getBody().get("detail"));
    }
}
