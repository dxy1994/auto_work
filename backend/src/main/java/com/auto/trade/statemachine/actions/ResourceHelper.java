package com.auto.trade.statemachine.actions;

import com.auto.entity.GameAccount;
import com.auto.entity.Machine;
import com.auto.service.GameAccountService;
import com.auto.service.MachineService;
import com.auto.ws.AgentRegistry;

/** 资源释放工具：将机器和账号恢复为可用状态。 */
public final class ResourceHelper {

    private ResourceHelper() {}

    public static void release(MachineService machineService,
                               GameAccountService gameAccountService,
                               AgentRegistry agentRegistry,
                               int machineId, int gameAccountId) {
        Machine machine = machineService.getById(machineId);
        if (machine != null) {
            machine.setStatus(agentRegistry.isAgentOnline(machineId) ? "online" : "offline");
            machineService.updateById(machine);
        }
        GameAccount account = gameAccountService.getById(gameAccountId);
        if (account != null) {
            account.setStatus("idle");
            gameAccountService.updateById(account);
        }
    }
}
