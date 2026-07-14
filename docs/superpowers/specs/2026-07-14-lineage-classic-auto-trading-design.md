# 韩服《Lineage Classic》自动交易设计

## 1. 目标与范围

在现有 `Backend + Frontend + Windows Worker` 系统中增加韩服《Lineage Classic》自动交易能力。系统监控 itemmania、barotem、itembay 三个平台，由总控依据机器安装的游戏、绑定的游戏账号、大区和实时执行状态，主动向合适的 Worker 指派订单。

第一阶段采用方案 A：在游戏机本地通过画面识别和 Windows 正常键鼠输入完成固定交易点的 Adena 交付。架构同时抽象画面源和输入驱动，以便未来接入方案 C 的视频采集与 USB HID 控制。

第一阶段约束：

- 韩服《Lineage Classic》，通过 PURPLE PC 运行。
- 单机单游戏账号，同一时刻最多执行一笔交易。
- 买家前往约定的固定安全区交易点。
- 商品只支持 Adena；道具和组合包只预留扩展接口。
- Windows 显示缩放、分辨率、游戏窗口尺寸和位置固定。
- 自动交易期间不允许人工抢占鼠标键盘。
- 不读取游戏内存、不注入进程、不调用非公开游戏协议，也不实现反作弊绕过。
- 自动交易行为可能违反游戏服务规则，系统不对账号安全作保证。

不在第一阶段范围内：

- 自动寻路到买家位置。
- 多开游戏或单机多账号并行交易。
- 道具、组合包或分批交付。
- 自动处理无法明确判断结果的交易。
- 通过硬件隔离方式规避游戏检测。

## 2. 总体架构

Backend 是订单和交易状态的唯一权威来源。Worker 负责网站数据采集、游戏环境观测和指令执行，不自主领取订单，也不独立决定重试交付。

```text
三个交易平台
    │
    ▼
网站适配器 ──标准订单事件──► Backend 订单协调器
                                      │
                                      ▼
                                  机器调度器
                                      │
                      总控预占、指派、启动、取消
                                      │
                                      ▼
                                Windows Worker
                                      │
                                游戏交易状态机
                                      │
                         FrameSource + InputDriver
                                      │
                                      ▼
                         PURPLE / Lineage Classic
```

### 2.1 网站适配器

itemmania、barotem、itembay 各自负责登录、读取订单详情和更新平台订单状态。适配器输出统一订单，至少包含：来源平台、平台订单号、游戏、大区、买家角色名、商品类型、Adena 数量和平台状态。

`website_id + source_order_no` 是幂等键。重复轮询只能更新已有订单，不能创建第二笔内部订单。

### 2.2 Backend 订单协调器

订单协调器负责持久化订单、执行状态、有效指派、状态版本、交易事件和证据。只有 Backend 可以决定指派、开始、暂停、取消和人工恢复。

已进入 `GAME_DELIVERED` 的订单禁止再次进行游戏交付，只能读取并重试网站确认状态。

### 2.3 游戏交易执行器

Worker 中的网站监控与游戏执行相互隔离。游戏执行器一次只接受一笔有效指派，并按状态机执行。每个动作遵循“确认当前状态、执行一个动作、重新截图验证”的规则，不进行无条件连续点击。

### 2.4 A/C 兼容边界

公共业务层依赖以下接口：

- `FrameSource`：提供当前游戏画面及分辨率信息。
- `InputDriver`：提供点击、按键和文本输入能力。
- `ScreenRecognizer`：把画面转换为结构化游戏状态。
- `AssetHandler`：准备并核验交付资产。

第一阶段实现：

- `WindowsWindowFrameSource`
- `WindowsInputDriver`
- `AdenaAssetHandler`

未来方案 C 实现：

- `CaptureCardFrameSource`
- `UsbHidInputDriver`

替换底层适配器不得改变订单协调、调度、风控或交易状态机。

## 3. 总控主动指派

### 3.1 候选机器条件

总控只从同时满足以下条件的机器中选择目标：

1. 机器已启用，WebSocket 在线且心跳未超时。
2. `machine_games` 已启用目标 `game_id`。
3. 机器绑定目标游戏和大区的有效游戏账号。
4. 游戏账号不是锁定或停用状态。
5. Worker 报告客户端已登录正确角色和大区。
6. 执行器为 `idle`，没有交易、人工接管或异常恢复任务。
7. UI 自检为 `ready`。
8. 当前执行数小于 `machine_games.max_concurrent`；首阶段该值固定为 1。

存在多台候选机器时，先按 `machine_games.priority` 降序，再选择最久未执行交易的机器。

### 3.2 Worker 实时状态

Worker 心跳扩展以下信息：

- `game_id`
- `game_account_id`
- `region_id`
- `client_status`
- `character_name`
- `executor_status`
- `current_assignment_id`
- `ui_health`

实时状态用于调度判断，数据库中的订单与指派记录用于最终一致性判断。

### 3.3 两阶段指派握手

1. Backend 原子预占订单、机器和游戏账号，生成唯一 `assignment_id`、执行令牌和租约。
2. Backend 发送 `trade_offer`。
3. Worker 重新检查本机游戏、账号、窗口、UI 和本地执行锁。
4. Worker 返回 `accepted` 或带原因的 `rejected`。
5. Backend 仅在收到有效 `accepted` 后发送 `trade_start`。
6. Worker 只有收到匹配有效指派和令牌的 `trade_start` 才能操作游戏。
7. 拒绝或握手超时释放预占并重新调度；没有其他候选机器时保持等待。
8. 任务终止并完成状态核对后，Backend 释放机器和游戏账号。

Worker 接受指派期间，机器状态为 `busy`，游戏账号状态为 `in_use`，其他指派必须被拒绝。三个网站监控仍可继续产生待调度订单。

## 4. 交易状态机

主状态如下：

```text
DETECTED
  → VALIDATED
  → WAITING_ASSIGNMENT
  → OFFERED
  → ASSIGNED
  → PRECHECKING
  → WAITING_BUYER
  → VERIFYING_BUYER
  → STAGING_ASSET
  → REVIEWING
  → CONFIRMING
  → GAME_DELIVERED
  → WEBSITE_CONFIRMING
  → COMPLETED
```

异常进入 `SUSPENDED`。指派拒绝或握手超时可从 `OFFERED` 返回 `WAITING_ASSIGNMENT`。买家角色不匹配时拒绝本次申请并返回 `WAITING_BUYER`。

### 4.1 订单校验

订单必须具备来源平台、平台订单号、游戏、大区、买家角色名和 Adena 数量。非 Adena 订单进入人工处理。订单金额必须为正数并符合配置的单笔及每日限额。

### 4.2 游戏预检

执行器确认目标游戏、服务器、角色、固定交易点、窗口尺寸、UI 模板和前台焦点。识别 Adena 余额，确保余额覆盖订单金额并保留最低配置余额。

### 4.3 等待与校验买家

按配置发送一次通知话术并等待交易申请。默认等待 10 分钟后提醒一次，总计 20 分钟后转 `SUSPENDED`。交易申请人角色名必须与订单角色名逐字符完全匹配；不使用模糊匹配。连续异常申请达到阈值后暂停任务。

### 4.4 放入与核验 Adena

`AdenaAssetHandler` 输入金额后重新读取交易窗口。至少两次独立识别结果一致，且结果必须等于订单金额。最终确认前再次核对买家角色名、自方交易栏内容、窗口焦点、遮挡和异常弹窗。

### 4.5 不可逆边界

最终确认后必须识别明确的游戏成功提示才能进入 `GAME_DELIVERED`。若无法确认成功或失败，进入 `SUSPENDED`，不得自动重做。

放入 Adena 之前发生的可恢复异常允许释放机器后重新调度。放入 Adena 之后的任何不确定异常均需人工核查。

### 4.6 网站确认

`GAME_DELIVERED` 后由来源平台适配器确认交付。失败时保持 `GAME_DELIVERED`，重试前先读取平台当前状态。此阶段只允许重试网站确认，禁止重新进行游戏交易。

## 5. 数据模型

复用 `game_item_orders` 和 `game_item_order_details`。

`game_item_orders` 增加：

- `website_id`
- `source_order_no`
- `game_account_id`
- `buyer_character`
- `asset_type`
- `asset_amount`
- `delivery_status`
- `assignment_id`
- `version`
- `game_delivered_at`
- `website_confirmed_at`
- `last_error_code`
- `last_error_message`

数据库为 `website_id + source_order_no` 建立唯一约束。

新增：

- `trade_assignments`：记录机器、账号、租约、令牌摘要、接受/拒绝结果及原因。同一订单同一时刻只有一个有效指派。
- `trade_events`：只追加的状态迁移和执行事件日志。
- `trade_evidence`：关键截图的存储地址、哈希、类型和时间。

未来道具交易使用 `game_item_order_details` 表达每个商品、数量和独立交付状态。

## 6. 自动化配置

每个游戏客户端版本维护一个自动化配置档案，包括：

- 游戏进程名、窗口标题、固定窗口大小和坐标映射。
- 截图区域、UI 模板版本、匹配阈值。
- OCR 语言、字符约束和识别区域。
- 状态超时、最大重试、异常申请阈值。
- 单笔和每日额度、最低保留余额。
- 固定交易地点与通知话术。
- `frame_source` 和 `input_driver` 类型。

客户端更新或配置版本变化后必须先通过 UI 自检。未经验证的配置不得执行真实交易。

## 7. 风控、证据和恢复

- 买家角色名完全匹配。
- Adena 金额连续两次识别一致。
- 每次输入前确认游戏窗口为前台目标窗口。
- 陌生弹窗、画面遮挡、分辨率变化或模板失效立即暂停。
- 提供本机全局急停、后台远程停止和人工接管状态。
- Worker 重启后不能自行恢复交易，必须等待总控指令。
- 所有状态迁移携带 `assignment_id` 和状态版本；过期 Worker 消息不得覆盖当前状态。
- Worker 执行中断线时订单进入 `SUSPENDED`。
- `GAME_DELIVERED` 是禁止重复游戏交付的永久保护边界。

每笔交易至少保留预检、买家角色名、Adena 金额、最终确认前、游戏结果和网站结果截图，以及完整状态事件时间线。截图通过现有存储服务保存，数据库仅记录地址和哈希。

日志不得包含密码、Cookie 或完整执行令牌。截图应设置访问权限和保留周期。

## 8. 管理端

订单页面增加来源平台、平台订单号、游戏、大区、买家角色、Adena 数量、交付状态、指派机器和游戏账号，并展示事件时间线和关键截图。提供暂停、取消、重新调度和人工确认网站完成操作。

`GAME_DELIVERED` 状态不提供重新游戏交付操作。

机器页面展示当前游戏、角色、客户端状态、执行器状态、UI 自检、当前指派订单、急停和人工接管状态。

## 9. 测试与验收

### 9.1 测试层次

1. 单元测试：三个平台解析、订单幂等、状态迁移、机器筛选、额度判断。
2. 调度集成测试：空闲、忙碌、离线、游戏不匹配、拒绝、握手超时和过期消息。
3. 画面回放测试：使用脱敏截图验证角色名、金额、窗口和成功提示识别。
4. Dry-run：真实运行到最终确认前，禁止执行最终确认。
5. 小额真实交易：验证完整交付、网站确认、断线和重复消息保护。

### 9.2 完成标准

- 三个平台均可生成幂等的标准订单。
- 总控根据机器游戏、账号、大区和执行状态主动指派。
- Worker 接受/拒绝握手与指派租约正常工作。
- 同一机器不会并发执行两笔交易。
- 买家或金额不一致时绝不执行最终确认。
- Worker 或网络异常不会触发自动重复交付。
- 游戏交付后网站确认失败时只重试网站确认。
- 方案 A 完成全闭环，A/C 底层接口已经隔离。
- 自动化测试、画面回放、Dry-run 和一轮小额验收全部通过。

## 10. 实施顺序

实施计划应按以下依赖顺序展开：

1. 数据库和 Backend 订单状态基础。
2. 三个平台订单详情标准化。
3. 总控机器调度与两阶段指派协议。
4. Worker 实时游戏状态和执行任务框架。
5. A/C 兼容接口及方案 A 底层实现。
6. Lineage Classic 识别器、状态机和 Adena 处理器。
7. 网站确认、异常恢复、证据和管理端。
8. 分层测试、Dry-run 和小额验收。
