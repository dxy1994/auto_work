# Worker（分布式浏览器自动化 Agent）

本目录是独立运行的分布式 worker，负责在**本机**运行浏览器自动化（登录 / 订单监控 / 语音提醒）。
它通过 WebSocket 长连接接入总控 backend，注册本机、心跳保活、领取并执行任务，
并把登录结果、任务状态经 WS 交给 backend 处理。

worker **零数据库依赖**：不连 MySQL、不持有 `SECRET_KEY`。密码由总控解密后以明文下发。

## 目录结构

```
worker/
  main.py            入口：连 WS → 注册 → 心跳 → 派发任务到线程
  config.py          BACKEND_WS_URL / PLAYWRIGHT_HEADLESS / 本机信息检测
  agent_client.py    WS 连接封装（线程安全发送）
  reporter.py        自动化代码回报门面（report_* / 验证码交互）
  task_manager.py    任务注册表 + stop_event，按 account_id 起停线程
  automation/
    browser.py       登录（自动 / 手动 captcha）
    login_helper.py  登录共享逻辑
    order_monitor.py 订单监控（itemmania / barotem / itembay）+ 语音提醒
```

## 安装

```powershell
cd worker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
patchright install chromium
```

## 配置

复制 `.env.example` 为 `.env`，把 `BACKEND_WS_URL` 改成总控机器地址：

```
BACKEND_WS_URL=ws://<总控IP>:8000/api/agent/ws
PLAYWRIGHT_HEADLESS=false
```

## 运行

```powershell
python -m worker.main
```

或在 `worker/` 目录内直接 `python main.py`。也可用仓库根目录的 `scripts/start-worker.bat`。

启动后 worker 会自动连接总控并注册本机（按 MAC 唯一）。总控 `machines` 表会出现在线记录并随心跳刷新。

## 说明

- 手动登录（captcha 类型）会在 worker 机器上弹出**有头浏览器**，需操作员在该机器旁或远程桌面完成验证码；
  验证码请求经总控转发到前端，前端回填后 worker 收到并继续。
- 登录任务结束后浏览器会关闭，不保存 Cookie 或账号浏览器 profile。
- 语音提醒（TTS）在 worker 本机播放，无需文件传输。
- 单机开发：需同时启动 backend 与至少一个 worker，否则触发自动化会返回“无在线 agent”。
- WS 下发明文密码，请部署在可信内网或启用 TLS。
