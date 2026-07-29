# Worker 分布式部署

Worker 已拆成三个互相有明确边界的模块：

```text
worker/
├─ common/          # 公共 WebSocket、协议、上报、时钟和主机信息
├─ monitor/         # 网站订单监控、浏览器登录、招呼发送
└─ game_executor/   # 游戏窗口、OCR、Wireless HID、交易状态机
```

`monitor` 和 `game_executor` 是两个独立进程、两个独立依赖集和两个独立 EXE，
应部署在不同主机。公共模块只提供通信与基础设施，不启动任何业务角色。
统一的 `worker/main.py` 已停用，避免误把两个角色运行在同一安装环境。

## 监控主机

监控主机只负责网站订单检测和招呼，不包含 PaddleOCR、游戏窗口或 Wireless HID 代码。

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

真实键鼠通过 WHID/1 TCP SDK 直连设备，不再依赖旧的 ESP32 HTTP 占位接口。
设备地址不在 Worker 上手工配置：Worker 使用本机 MAC 注册，总控根据机器记录的
`mk_device_id` 下发 Wireless HID 的稳定设备 ID、IP 和控制端口。机器尚未绑定键鼠时，
Worker 会保持在线并持续轮询；绑定设备通过 UDP 身份校验并成功取得控制权后，才会探测
游戏和接受交易任务。每次交易下发还会重新携带当前绑定，避免机器改绑后继续使用旧设备。

物品识别图由总控以下发 `/uploads/...` 相对地址。游戏执行端配置 `STORAGE_ENDPOINT`、
`STORAGE_BUCKET`、`STORAGE_ACCESS_KEY`、`STORAGE_SECRET_KEY` 后，会去掉
`/uploads/` 前缀并直接从 RustFS 读取对应对象；未配置完整的 RustFS 参数时，才根据
`GAME_IMAGE_BASE_URL` 或 `BACKEND_WS_URL` 回退到总控 HTTP 代理。

鼠标绝对坐标会转换为 HID 的 0～4095 坐标，并拆分成带加减速和弯曲的多点轨迹；
点击、拖拽和按键包含随机停顿。文本逐字输入，默认按压 75～145ms、字间间隔
80～220ms，底层会再次限制最短时长。每段硬件指令结束后更新 `last_feedback`，
`health_check()` 同时返回 CH9329 在线状态和最近一段指令的结果。

动作标注图和逐动作日志当前固定关闭，不提供运行时手动配置开关。步骤状态检测固定
轮询 30 次，不读取环境变量覆盖该次数。

### Wireless HID 浏览器调试

下面的入口会发送真实键鼠指令：打开 Windows 运行窗口，输入 `google.com` 并打开
默认浏览器，在 Google 输入随机搜索词，进入结果页后将鼠标移动到随机位置并向下滚动。
每个完整步骤结束后输出一条 `[HID-DEBUG]` 完成反馈：

```bat
cd worker
python -m game_executor.hid_browser_debug
```

启动后有 3 秒倒计时，运行前应保存当前工作并停止触碰键鼠。

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
`LINEAGE_REGION_TEXT_SIMILARITY` 向上调整。游戏画面截图默认最多等待 5 秒，
可通过 `LINEAGE_CAPTURE_TIMEOUT_SECONDS` 调大（最低为 1 秒）。

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
