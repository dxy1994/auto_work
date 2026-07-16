---
项目: auto-work
作者: houliangyu
日期: 2026-07-16
编号: SPI-VER-ConFix-TestReport
阶段: 02-05测试
状态: 已基线
---

# 测试报告（SPI-VER-ConFix-TestReport）V1.0

## 自动化结果

| 检查 | 命令 | 结果 |
|---|---|---|
| Worker 并发回归 | `PYTHONPYCACHEPREFIX=/tmp/auto-work-pycache python3 -m unittest discover -s tests -v` | 5 项通过，0 失败 |
| Python 编译 | `PYTHONPYCACHEPREFIX=/tmp/auto-work-pycache python3 -m compileall -q worker tests` | 通过 |
| 补丁格式 | `git diff --check` | 通过 |

## 用例

| 用例 | 预期 | 结果 |
|---|---|---|
| 从其他线程发起招呼 | 聊天协程在 BrowserSession owner loop 执行 | 通过 |
| 招呼结束清理 | 页面关闭，临时页登记为空 | 通过 |
| 慢速同步 TTS | asyncio 调度不被 200ms 播放阻塞 | 通过 |
| 多账户并发 TTS | 同步播放统一运行于一个专用线程 | 通过 |
| 启动页面清理 | 保留聊天临时页，仅关闭游离页 | 通过 |
| 会话关闭 | 拒绝新招呼并解除活动任务登记 | 通过 |

## 环境限制

当前本地环境未安装 Patchright，自动化测试使用最小浏览器会话替身验证调度边界；未连接真实 Windows Worker 和 Itemmania 页面。上线前应执行现场联调：商品刷新过程中下发招呼，确认 1 秒内出现聊天页创建日志，并确认刷新页和订单页继续运行。
