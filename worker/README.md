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

大区所在页码和点击坐标在总控“大区管理”中录入，坐标按 800×600 游戏客户区填写，
并随每次交易指令下发给游戏执行机。执行机每次交易都会重新进入服务器列表，先切换到
配置页，再优先使用总控坐标；未配置坐标时，才扫描当前页并通过 OCR 文本框定位大区
中心。OCR 未找到目标或最终坐标越界时会停止流程。

订单明细会携带物品管理中配置的未选中、选中两张 `recognition_image_*_url`。游戏执行机
按需从总控下载并缓存图片，在物品栏内依次进行模板匹配；金币和普通物品使用同一套
动态识别流程，不再引用脚本目录中的固定金币图片，也不再以固定坐标作为交易来源。

游戏操作后的等待按业务分级：大区、选角、登录和交易窗口切换使用长等待（固定时间加
3～10 秒随机等待）；菜单和图像识别使用中等待；物品拖拽、数量输入使用短等待。每个
动作等待后最多检测下一步状态 3 次，三次均未就绪才报错。日志统一使用
`[Lineage][步骤等待]`、`[Lineage][步骤检测]` 和 `[Lineage][步骤失败]` 前缀。

## OCR

游戏执行端使用 CPU 模式 PaddleOCR：

- 检测：`PP-OCRv5_mobile_det`
- 韩文识别：`korean_PP-OCRv5_mobile_rec`
- Windows CPU 下关闭 oneDNN/MKLDNN，避免 Paddle 3.3.1 推理异常

首次运行会下载官方模型到 PaddleX 缓存。韩文 OCR 默认要求最低词块置信度不低于
90，文本相似度不低于 0.90；可通过 `LINEAGE_OCR_MIN_CONFIDENCE` 和
`LINEAGE_REGION_TEXT_SIMILARITY` 向上调整。

## 人工键鼠真实测试

接入总控真实订单，保留全部正式等待、识别、截图及终态上报，仅阻断 HID 指令：

```env
GAME_EXECUTOR_MANUAL_ACTIONS=true
GAME_EXECUTOR_MANUAL_ACTION_WAIT_SECONDS=5
```

随后按正常方式启动 `game_executor.main`。Worker 会正常接收平台订单、上报中间状态，
每个实际键鼠动作输出 `[MANUAL-ACTION]`，包含需要人工执行的点击坐标、拖拽起止坐标、
按键或输入内容，但不会连接 ESP32。日志输出后会按配置预留人工操作时间，随后继续执行
正式的画面检测。流程成功或失败时直接上报真实结果，不再改写为 `DRY_RUN_NO_HID`；
因此成功测试会真实推进订单状态、库存和网站确认流程。启用前应使用明确的测试订单。

也可以使用本地测试订单运行同一套人工操作编排：

```bat
cd worker
python -m game_executor.dry_run_trade --amount 1000000 --buyer DryRunBuyer
```

日志末尾必须显示 `sent_hid_actions=0`。该入口不消费中控订单；需要验证真实总控订单时，
应按上面的环境变量启动 `game_executor.main`。

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
