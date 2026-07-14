# Worker

Worker 通过 WebSocket 连接总控，执行网站自动化任务，并上报本机游戏客户端与交易执行器运行态。

## 天堂经典版交易基础阶段

当前实现的是“不控制游戏”的调度闭环，用于先验证总控能否根据机器在线状态、绑定游戏账号、韩服区服、客户端登录状态、执行器空闲状态和 UI 健康状态，唯一指派一笔 Adena 订单。

协议消息：

- `trade_offer`：总控发出带 30 秒租约的候选指派，不代表授权执行。
- `trade_offer_decision`：Worker 根据本机游戏和执行状态接受或拒绝。
- `trade_start`：总控确认预占成功后，使用同一临时令牌授权开始。
- `trade_status`：Worker 上报开始、拒绝、取消或模拟完成状态。
- `trade_cancel`：总控取消尚未完成的本机交易任务。

执行令牌只在总控内存和 WebSocket 消息中短暂存在，数据库仅保存 SHA-256 摘要。Worker 同时只允许一个活动交易指派，重复消息按 assignment ID 和令牌幂等校验。

当前 `trade_start` 只上报 `started` 和 `simulation_completed`，随后释放执行槽。此阶段没有引入屏幕捕获、OpenCV、Windows 输入、采集卡或 USB HID 依赖，也不会操作游戏窗口。

运行 Worker 单元测试：

```bash
PYTHONPYCACHEPREFIX=/tmp/auto-work-pycache python3 -m unittest discover -s tests -v
```
