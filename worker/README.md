# Worker

Worker 通过 WebSocket 连接总控，执行网站自动化任务，并上报本机游戏客户端与交易执行器运行态。

## 天堂经典版自动交易

正式 `LineageClassicExecutor` 在 Trader 启动时注册，通过 ESP32 HTTP HID
接口执行切区、等待买家交易申请、放入 Adena 和确认操作。硬件不可达或指令失败时不会伪报成功。

协议消息：

- `trade_offer`：总控发出带 30 秒租约的候选指派，不代表授权执行。
- `trade_offer_decision`：Worker 根据本机游戏和执行状态接受或拒绝。
- `trade_start`：总控确认预占成功后，使用同一临时令牌授权开始。
- `trade_status`：Worker 上报进度、取消和分类后的终态。
- `trade_cancel`：总控取消尚未完成的本机交易任务。

执行令牌只在总控内存和 WebSocket 消息中短暂存在，数据库仅保存 SHA-256 摘要。Worker 同时只允许一个活动交易指派，重复消息按 assignment ID 和令牌幂等校验。

天堂导航按 800×600 客户区相对坐标完成以下检查：

- 识别 `Lineage Classic - <版本> [LIVE] - Login [<账号>]` 窗口；
- OCR 比对当前大区，无法可靠识别时执行一次安全切区；
- 通过重新登录、角色界面退出登录进入服务器列表；
- 按 `region_sort_order` 的固定两列点位选择服务器，并施加横向 ±30、纵向 ±3 像素偏移；
- 选择角色并登录，最后通过未选中/选中金币模板确认物品栏已打开。

总控会随订单下发 `region_name`、`region_code` 和 `region_sort_order`。OCR 使用可选的
Tesseract 运行时；未安装 Tesseract 时仍可切区并用本进程中的已确认大区缓存完成后续判断。
服务器列表的左右列 X、首行 Y 和行距可通过 `.env.trader.example` 中的
`LINEAGE_SERVER_*` 参数按实机截图校准。
韩语 OCR 默认要求所有有效词块的最低置信度不低于 90，文本相似度不低于 0.90；
可通过 `LINEAGE_OCR_MIN_CONFIDENCE` 和 `LINEAGE_REGION_TEXT_SIMILARITY` 向上调整，程序强制
保底为 90/0.90；低于门槛时一律按识别失败处理并进入安全切区流程。

招呼发送成功后总控立即派发交易任务，Worker 应先完成切区和物品栏检查，再等待买家
发起游戏内交易。等待时长使用订单下发的 `trade_timeout_seconds`（游戏管理配置，默认
300 秒，范围 30–7200 秒）。超时结果使用 `timed_out` 上报，后台释放机器和游戏账号，
订单转为 `suspended` 并记录 `TRADE_REQUEST_TIMEOUT`。

执行进度会持久化为 `preparing / switching_region / waiting_buyer / trading /
verifying`。Worker 和后台各有一层总执行 watchdog；进入 `trading` 后如果超时、
断线或无法确认结果，订单进入 `review_required`，不会自动重试造成重复交付。
交易弹窗、确认按钮、取消按钮和最终确认提示均使用不低于 0.90 的模板置信度。
只有最终确认后相关交易元素消失，并连续三帧检测到已回到游戏主界面时，
才上报 `completed`；否则转人工复核，不会伪报成功。

运行 Worker 单元测试：

```bash
PYTHONPYCACHEPREFIX=/tmp/auto-work-pycache python3 -m unittest discover -s tests -v
```
