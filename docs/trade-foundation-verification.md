# 天堂经典版自动交易：调度基础验证

日期：2026-07-14  
范围：韩服、单机单游戏账号、固定交易点、第一阶段仅 Adena。

## 本阶段结果

本阶段完成了“总控指派一笔订单”的基础闭环：

1. 订单进入 `waiting_assignment`。
2. 总控综合数据库配置和 Worker 心跳，筛选在线、游戏/区服/账号匹配、客户端已登录、执行器空闲且 UI 健康的机器。
3. 总控预占机器和游戏账号，生成 30 秒 `trade_offer`。
4. Worker 再次依据本机状态决定接受或拒绝。
5. 只有接受后，总控才发送 `trade_start`；第一阶段 Worker 运行模拟器并回报完成。
6. 拒绝、过期、启动失败或取消时释放机器和账号，订单进入可恢复状态。

订单状态更新使用 `delivery_status + row_version` 条件保护，防止两个调度请求同时覆盖同一订单。旧 WebSocket 会话、错误机器和过期 assignment 不能启动交易。执行令牌为 256 位随机值，数据库只保存 SHA-256 摘要，HTTP 验证接口不返回明文令牌。

## 验证接口

- `POST /api/trades/{orderId}/dispatch`：手工触发一笔待指派订单的调度。
- `GET /api/trades/{orderId}/status`：读取订单当前交付状态和非敏感错误信息。

## 明确边界

本阶段是可运行的调度与协议基础，不是已经能在游戏内完成交易的成品。当前不包含：

- 天堂经典版窗口捕获、界面识别和坐标标定；
- 买家角色识别、Adena 拆分、交易窗复核与确认；
- itemmania、barotem、itembay 三个平台的订单接入和网站确认；
- Windows 键鼠输入实现；
- 采集卡画面与 USB HID 外置输入实现。

架构继续保持 A/C 兼容：后续业务状态机只依赖 `FrameSource` 和 `InputDriver`，A 使用本机窗口捕获与 Windows 输入，C 使用采集卡与 USB HID。第一阶段后续优先实现 A。

## 后续实施顺序

1. 三平台标准化接单、去重和网站确认适配层。
2. `FrameSource` / `InputDriver` 接口及 A 方案 Windows 实现，同时预留 C 方案实现位。
3. 固定分辨率标定、韩服 UI 探针和交易场景识别。
4. 买家核验、Adena 交付、二次复核和异常恢复状态机。
5. 端到端影子模式、人工确认模式和小额灰度验证。

## 验证命令

```bash
cd backend
mvn -Dmaven.repo.local=/tmp/auto-work-m2 test

cd ../worker
PYTHONPYCACHEPREFIX=/tmp/auto-work-pycache python3 -m unittest discover -s tests -v

cd ../frontend
PATH=/Users/houliangyu/.nvm/versions/node/v20.20.0/bin:$PATH npm run build

cd ..
git diff --check
```

2026-07-14 实际结果：Backend 19 项测试通过，Worker 9 项测试通过，Frontend 使用 Node 20.20.0 构建成功。Vite 仍报告既有的大包体积提示，不影响构建产物。
