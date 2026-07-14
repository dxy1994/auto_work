package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.entity.Account;
import com.auto.entity.Website;
import com.auto.service.AccountService;
import com.auto.service.CryptoService;
import com.auto.service.LoginLogService;
import com.auto.service.WebsiteService;
import com.auto.ws.AgentRegistry;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AutomationControllerTest {

    @Test
    void orderCheckRejectsInactiveAccountBeforeDispatch() {
        WebsiteService websiteService = mock(WebsiteService.class);
        AccountService accountService = mock(AccountService.class);
        AgentRegistry registry = mock(AgentRegistry.class);
        AutomationController controller = new AutomationController(websiteService, accountService,
                mock(LoginLogService.class), mock(CryptoService.class), registry);

        Account account = new Account();
        account.setId(10);
        account.setWebsiteId(1);
        account.setIsActive(0);
        Website website = new Website();
        website.setId(1);
        website.setIsActive(1);
        when(accountService.getById(10)).thenReturn(account);
        when(websiteService.getById(1)).thenReturn(website);

        ApiException error = assertThrows(ApiException.class, () -> controller.orderCheck(10, null));

        assertEquals(409, error.getStatus().value());
        verify(registry, never()).pickAgent(null);
    }
}
