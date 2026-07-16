---
项目: auto-work
作者: houliangyu
日期: 2026-07-16
编号: SPI-DES-ConFix-Plan
阶段: 02-03设计
状态: 已基线
---

# 任务并发阻塞修复实施计划

> 内联执行，按测试驱动步骤实施；不执行 Git 提交。

**目标：** 修复招呼跨事件循环复用 Playwright 会话和同步语音阻塞问题。

**架构：** 每个 `BrowserSession` 记录 Playwright 所属事件循环。所有聊天页面操作投递到该循环；WebSocket 主循环仅分发消息。同步语音通过线程池桥接为异步调用。

**技术栈：** Python 3、asyncio、threading、Patchright、unittest。

## 任务一：建立事件循环归属回归测试

- 新建 `tests/test_worker_concurrency.py`。
- 构造独立 owner loop 和假会话，断言聊天协程在 owner loop 执行。
- 运行测试，预期现有实现因依赖全局 main loop 而失败。
- 修改 `browser_session.py`、`chat_sender.py`、`main.py`，使测试通过。

## 任务二：建立非阻塞语音回归测试

- 测试慢速同步播放器通过异步入口执行时，事件循环计时协程仍可推进。
- 运行测试，预期现有代码因缺少 async 入口而失败。
- 修改 `audio_alert.py` 及 async 调用点，使测试通过。

## 任务三：保护聊天临时页

- 测试临时页面登记快照能被清理逻辑读取。
- 修改 `BrowserSession` 和 `BaseOrderMonitor`。
- 验证关闭页面后登记被清除。

## 任务四：全量验证

- 执行 `python3 -m unittest discover -s tests -v`；
- 执行 `python3 -m compileall worker tests`；
- 检查 `git diff --check`；
- 更新实现过程、评审报告、测试报告及文档索引。

