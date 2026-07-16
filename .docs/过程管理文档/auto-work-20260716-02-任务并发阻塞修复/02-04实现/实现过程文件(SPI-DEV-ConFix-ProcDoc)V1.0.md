---
项目: auto-work
作者: houliangyu
日期: 2026-07-16
编号: SPI-DEV-ConFix-ProcDoc
阶段: 02-04实现
状态: 已基线
---

# 实现过程文件（SPI-DEV-ConFix-ProcDoc）V1.0

## 根因

订单监控在线程内通过 `asyncio.run()` 创建 Playwright；自动招呼却把聊天协程投递到 WebSocket 主循环，并复用监控循环创建的 `BrowserContext`，形成跨事件循环访问。监控协程还直接执行同步 `voice.Speak()`，会暂停该账户下所有页面任务。

## 测试驱动记录

### 循环归属

1. 新增测试，构造独立 owner loop 和浏览器假会话。
2. 现有实现失败，结果为 `event loop 未初始化`。
3. `BrowserSession` 增加所有者循环和只读获取接口。
4. `ChatSender` 改为向 owner loop 投递。
5. 测试通过，并确认聊天页关闭及临时页登记清空。

### 非阻塞语音

1. 新增慢速同步语音测试。
2. 现有实现失败于缺少异步语音入口。
3. 增加 `play_alert_audio_async()`，使用专用单线程执行器，避免阻塞并保持 COM 线程亲和性。
4. 替换监控器、订单基类和验证码登录中的同步调用。
5. 测试通过，慢速语音期间事件循环计时任务仍可推进。

## 修改文件

| 文件 | 修改内容 |
|---|---|
| `worker/automation/browser_session.py` | 记录 owner loop；只读获取会话；登记临时页面 |
| `worker/automation/chat_sender.py` | 按账户 owner loop 执行聊天；移除全局主循环；保护聊天页 |
| `worker/main.py` | 移除聊天主循环初始化 |
| `worker/automation/order_monitor.py` | 页面清理纳入会话临时页；使用异步语音 |
| `worker/automation/audio_alert.py` | 增加线程池异步入口 |
| `worker/automation/login_handler.py` | 验证码提醒改为异步入口 |
| 三个平台监控器 | 提醒播放改为异步入口 |
| `tests/test_worker_concurrency.py` | 增加五个并发与生命周期回归测试 |

## 评审修订

独立复核发现并修复三项重要问题：启动阶段页面清理遗漏聊天临时页、默认线程池不保证 COM 线程亲和、浏览器关闭与在途招呼存在竞态。修订后再次复核，未发现剩余 Critical 或 Important；同时按 Minor 建议将任务注销放入最外层 `finally`，确保二次取消时仍清理登记。

## 未修改项

- WebSocket 协议；
- 后端订单与招呼逻辑；
- 数据库结构；
- 商品刷新周期；
- 页面选择器与平台业务步骤。
