---
项目: auto-work
作者: houliangyu
日期: 2026-07-16
编号: SPI-DES-ConFix-GD
阶段: 02-03设计
状态: 已基线
---

# 概要设计说明书（SPI-DES-ConFix-GD）V1.0

## 设计决策

采用“账户浏览器事件循环归属”方案。`BrowserSession.init()` 记录创建 Playwright 的事件循环；招呼线程先只读获取现有会话，再通过 `run_coroutine_threadsafe()` 把聊天协程投递给该会话的所有者事件循环。

不再把聊天协程统一投递到 WebSocket 主事件循环。WebSocket 主循环只负责收发协议，不操作 Playwright 对象。

## 数据流

```text
WebSocket 主循环收到 greeting
  → 创建轻量招呼线程
  → 按 account_id 查找现有 BrowserSession（不增加引用计数）
  → 获取 session.owner_loop
  → 将聊天协程投递到 owner_loop
  → 在同一 BrowserContext 新建独立聊天页
  → 标记聊天页为临时活动页
  → 发送话术
  → 关闭并解除临时页标记
  → 招呼线程上报 greeting_result
```

## 组件修改

### BrowserSession

- 保存 `_owner_loop`；
- 提供 `get_existing(account_id)`，只读获取会话且不增加引用计数；
- 提供 `owner_loop`；
- 提供临时页面登记、解除和快照方法。

### ChatSender

- 删除全局 `_main_loop`；
- 按账户查找会话并投递到 `owner_loop`；
- `_do_send_web_chat` 接收明确的 session；
- 聊天页创建后登记，关闭后解除。

### BaseOrderMonitor

- 清理多余页面时，把会话登记的临时页面加入保护集合。

### AudioAlert

- 增加 `play_alert_audio_async()`，通过专用单线程执行器执行现有同步播放器，既不阻塞事件循环，也保持 Windows COM 线程亲和性；
- async 监控和登录路径统一改为 `await play_alert_audio_async(...)`。

## 异常处理

| 异常 | 处理 |
|---|---|
| 无现有浏览器会话 | 返回“浏览器会话未初始化” |
| 所有者循环缺失或关闭 | 返回“浏览器事件循环不可用” |
| 招呼超过 120 秒 | 取消 future 并返回超时 |
| 页面操作异常 | 关闭聊天页、解除登记并返回异常信息 |

## 兼容性

后端 API、WebSocket 消息、数据库和前端均不变化。商品刷新与订单检测仍保留现有协程和页面结构。
