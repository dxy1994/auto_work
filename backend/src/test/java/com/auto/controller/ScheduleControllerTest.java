package com.auto.controller;

import com.auto.entity.WebsiteSchedule;
import com.auto.service.AccountService;
import com.auto.service.StorageService;
import com.auto.service.WebsiteScheduleService;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ScheduleControllerTest {

    @Test
    void uploadKeepsOldAudioAndRemovesNewObjectWhenDatabaseUpdateFails() throws Exception {
        WebsiteSchedule schedule = new WebsiteSchedule();
        schedule.setAccountId(10);
        schedule.setAlertAudioPath("uploads/audio/old.mp3");
        WebsiteScheduleService scheduleService = mock(WebsiteScheduleService.class);
        StorageService storageService = mock(StorageService.class);
        when(scheduleService.findByAccountId(10)).thenReturn(schedule);
        when(storageService.upload(eq("audio"), eq(".mp3"), any())).thenReturn("audio/new.mp3");
        when(scheduleService.updateById(any())).thenThrow(new RuntimeException("database unavailable"));
        ScheduleController controller = new ScheduleController(scheduleService,
                mock(AccountService.class), storageService);

        assertThrows(RuntimeException.class, () -> controller.uploadAlertAudio(10,
                new MockMultipartFile("file", "new.mp3", "audio/mpeg", "new".getBytes())));

        // 写库失败时删除新上传的对象，保留旧对象不动。
        verify(storageService).delete("audio/new.mp3");
        verify(storageService, never()).delete("audio/old.mp3");
    }
}
