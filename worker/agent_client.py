"""
Agent WebSocket 客户端封装。

- 运行在 asyncio 事件循环中；
- 浏览器自动化任务在工作线程内执行，通过 send_threadsafe 把回报消息
  投递回事件循环发送，避免跨线程直接操作 WebSocket。
"""
import asyncio
import json


class AgentClient:
    def __init__(self, ws, loop: asyncio.AbstractEventLoop):
        self._ws = ws
        self._loop = loop

    async def send(self, msg: dict):
        await self._ws.send(json.dumps(msg, ensure_ascii=False))

    def send_threadsafe(self, msg: dict):
        """供工作线程调用：把消息投递到 asyncio 循环发送（非阻塞）。"""
        try:
            future = asyncio.run_coroutine_threadsafe(self.send(msg), self._loop)
            future.add_done_callback(self._log_send_failure)
        except Exception as e:
            print(f"[AgentClient] send_threadsafe 失败: {e}")

    @staticmethod
    def _log_send_failure(future):
        try:
            future.result()
        except Exception as e:
            print(f"[AgentClient] 异步发送失败: {e}")
