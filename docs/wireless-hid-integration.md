# Wireless HID 上位机与 SDK

本项目已经按照《Wireless HID 设备接口文档》V1.0 接入现有中控平台。

## 组成

- Java SDK：`backend/src/main/java/com/auto/whid/sdk`
  - UDP 多网卡广播和已知 IP 单播发现
  - V1 TCP 帧编码、CRC32、拆包读取和 ACK/ERROR 校验
  - CLAIM、独立 1 秒心跳、状态、键盘、相对/绝对鼠标和全释放
  - HTTP 挑战应答、管理会话、状态、改名、AP 模式、恢复出厂和 OTA
- Spring 集成：`WirelessHidDeviceManager` 与 `WirelessHidController`
  - 控制连接和管理 token 仅保存在进程内存
  - 发现结果写入现有 `mouse_keyboard_devices`，无需数据库迁移
  - 设备连接信息以 JSON 保存到 `device_info`
- Vue 上位机：原“键鼠设备”页面已升级为 Wireless HID 工作台
- 独立 Python SDK 与测试工具：`tools/whid_sdk.py`、`tools/whid_test.py`

## 启动

先按项目原有方式启动 MySQL 和后端：

```powershell
cd backend
.\mvnw.cmd spring-boot:run
```

再启动前端：

```powershell
cd frontend
npm.cmd run dev
```

打开“设备管理 → Wireless HID”，点击“发现设备”。如 Windows 有多个网卡，Java SDK 会分别绑定每个有效本地 IPv4 地址发起广播。

## 独立测试工具

测试工具仅依赖 Python 标准库。PIN 不允许作为命令行参数，只能交互输入。

```powershell
python tools\whid_test.py discover
python tools\whid_test.py discover --ip 192.168.6.167
python tools\whid_test.py status --ip 192.168.6.167
python tools\whid_test.py keyboard --ip 192.168.6.167 --modifier 0x01 --keys 0x06
python tools\whid_test.py type --ip 192.168.6.167 --text "Hello"
python tools\whid_test.py mouse-rel --ip 192.168.6.167 --x 20 --y -10
python tools\whid_test.py mouse-abs --ip 192.168.6.167 --x 2048 --y 2048
python tools\whid_test.py management-status --ip 192.168.6.167
python tools\whid_test.py rename --ip 192.168.6.167 --name Desk-PC-01
python tools\whid_test.py ota --ip 192.168.6.167 --file firmware.bin
```

所有 TCP 命令都会先 CLAIM，后台维持心跳，并在退出时依次执行 `RELEASE_ALL` 和 `RELEASE`。

## 后端 API

基础路径为 `/api/wireless-hid`：

- `POST /discover`
- `GET /devices`
- `POST /{id}/connect`、`POST /{id}/disconnect`
- `GET /{id}/status`
- `POST /{id}/keyboard`
- `POST /{id}/mouse/relative`、`POST /{id}/mouse/absolute`
- `POST /{id}/release-all`
- `POST /{id}/management/session`
- `GET /{id}/management/status`
- `POST /{id}/management/name`
- `POST /{id}/management/provision`
- `POST /{id}/management/factory-reset`
- `POST /{id}/management/ota`
- `POST /ap/provision`

## 安全边界

- 管理 PIN、proof 和 token 不入库、不写日志。
- 设备管理接口是明文 HTTP，只应在可信局域网使用。
- AP 配网只接受局域网 IPv4 网关，不接受任意 URL。
- 恢复出厂要求再次输入设备 ID；OTA 与进入 AP 模式在界面中均有二次确认。
- OTA 上传前检查文件大小、ESP Magic `0xE9` 和 SHA-256。
- OTA 超时或连接中断后，应先重新发现并核对固件版本，不应立即重复刷写。
