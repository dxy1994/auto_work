# Worker 分布式部署

Worker 已拆成三个互相有明确边界的模块：

```text
worker/
├─ common/          # 公共 WebSocket、协议、上报、时钟和主机信息
├─ monitor/         # 网站订单监控、浏览器登录、招呼发送
└─ game_executor/   # 游戏窗口、OCR、ESP32 HID、交易状态机
```

`monitor` 和 `game_executor` 是两个独立进程、两个独立依赖集和两个独立 EXE，
应部署在不同主机。公共模块只提供通信与基础设施，不启动任何业务角色。
统一的 `worker/main.py` 已停用，避免误把两个角色运行在同一安装环境。

## 监控主机

监控主机只负责网站订单检测和招呼，不包含 PaddleOCR、游戏窗口或 ESP32 代码。

```bat
copy worker\.env.monitor.example worker\.env
scripts\start-monitor.bat
```

直接运行：

```bat
cd worker
python -m monitor.main
```

独立依赖：`worker/requirements-monitor.txt`。

## 游戏执行主机

游戏执行主机只负责接收交易指派、识别游戏画面和执行游戏交易，
不安装浏览器自动化、网站适配器或招呼模块。

```bat
copy worker\.env.game-executor.example worker\.env
scripts\start-game-executor.bat
```

直接运行：

```bat
cd worker
python -m game_executor.main
```

独立依赖：`worker/requirements-game-executor.txt`。
游戏执行端向总控注册的角色是 `game_executor`；总控仍兼容升级前的 `trader`。

大区点击坐标在总控“大区管理”中按 800×600 游戏客户区坐标录入，并随每次交易指令
下发给游戏执行机。执行机优先直接使用总控坐标；未配置坐标时，才扫描服务器列表并
通过 OCR 文本框定位大区中心。OCR 未找到目标或最终坐标越界时会停止流程。

订单明细会携带物品管理中配置的 `recognition_image_url`。游戏执行机按需从总控下载并
缓存图片，在物品栏内进行模板匹配；金币和普通物品使用同一套动态识别流程，不再引用
脚本目录中的固定金币图片，也不再以物品栏固定坐标作为交易来源。

## OCR

游戏执行端使用 CPU 模式 PaddleOCR：

- 检测：`PP-OCRv5_mobile_det`
- 韩文识别：`korean_PP-OCRv5_mobile_rec`
- Windows CPU 下关闭 oneDNN/MKLDNN，避免 Paddle 3.3.1 推理异常

首次运行会下载官方模型到 PaddleX 缓存。韩文 OCR 默认要求最低词块置信度不低于
90，文本相似度不低于 0.90；可通过 `LINEAGE_OCR_MIN_CONFIDENCE` 和
`LINEAGE_REGION_TEXT_SIMILARITY` 向上调整。

## 无键鼠干跑

在游戏执行主机上可以运行正式交易编排，但强制阻断 ESP32 键鼠指令：

```bat
cd worker
python -m game_executor.dry_run_trade --amount 1000000 --buyer DryRunBuyer
```

日志末尾必须显示 `sent_hid_actions=0`。该入口使用本地测试订单，不消费中控订单。

## 独立打包

分别构建：

```bat
scripts\build-monitor-exe.bat
scripts\build-game-executor-exe.bat
```

输出：

- `worker/dist/monitor/auto-monitor.exe`
- `worker/dist/game-executor/auto-game-executor.exe`

`scripts/build-worker-exe.bat` 仅是同时构建上述两个独立产物的开发机快捷入口，
不会生成包含两个角色的统一 EXE。部署时只能把对应角色的 EXE 和 `.env` 放到目标主机。

## 测试

```bat
cd worker
python -m unittest discover -s tests -v
```
