<template>
  <div class="whid-console">
    <header class="console-hero">
      <div class="hero-copy">
        <div class="eyebrow">WIRELESS HID / OPERATOR CONSOLE</div>
        <h1>键鼠链路工作台</h1>
        <p>在同一条安全操作链上完成设备发现、HID 控制、管理认证与固件升级。</p>
      </div>

      <div class="signal-path" aria-label="Wireless HID 连接阶段">
        <div class="signal-node active">
          <span class="signal-index">01</span>
          <div><strong>UDP 发现</strong><small>39666 · 多网卡</small></div>
        </div>
        <div class="signal-wire" :class="{ live: selectedDevice }"><i /></div>
        <div class="signal-node" :class="{ active: selectedDevice }">
          <span class="signal-index">02</span>
          <div><strong>TCP 控制</strong><small>CLAIM · 39667</small></div>
        </div>
        <div class="signal-wire" :class="{ live: isConnected }"><i /></div>
        <div class="signal-node" :class="{ active: isConnected }">
          <span class="signal-index">03</span>
          <div><strong>心跳守护</strong><small>1 s / 3 s</small></div>
        </div>
      </div>

      <div class="discovery-bar">
        <el-input
          v-model="knownIp"
          clearable
          class="ip-input"
          placeholder="已知 IP（留空则广播发现）"
          @keyup.enter="discover"
        >
          <template #prefix><el-icon><Position /></el-icon></template>
        </el-input>
        <el-button class="ap-button" @click="apDialogVisible = true">
          <el-icon><Connection /></el-icon>AP 配网
        </el-button>
        <el-button type="primary" :loading="discovering" @click="discover">
          <el-icon><Aim /></el-icon>{{ discovering ? '正在扫描网络' : '发现设备' }}
        </el-button>
      </div>
    </header>

    <div class="console-layout">
      <aside class="device-rail">
        <div class="rail-heading">
          <div><span class="section-kicker">DEVICES</span><h2>设备列表</h2></div>
          <span class="device-count">{{ filteredDevices.length }}</span>
        </div>
        <el-input v-model="keyword" class="rail-search" clearable placeholder="名称、ID 或 IP">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>

        <div v-loading="loading" class="device-list">
          <button
            v-for="device in filteredDevices"
            :key="device.id"
            type="button"
            class="device-card"
            :class="{ selected: device.id === selectedId }"
            @click="selectDevice(device.id)"
          >
            <span class="device-state-dot" :class="device.connection_state" />
            <span class="device-card-copy">
              <strong>{{ device.name }}</strong>
              <span class="mono">{{ device.ip || '地址未知' }}</span>
              <small>{{ device.machine_name ? `关联 ${device.machine_name}` : device.device_id }}</small>
            </span>
            <span class="state-label" :class="device.connection_state">
              {{ stateLabel(device.connection_state) }}
            </span>
          </button>

          <div v-if="!loading && !filteredDevices.length" class="rail-empty">
            <el-icon :size="30"><Aim /></el-icon>
            <strong>还没有发现设备</strong>
            <span>确认上位机与设备位于同一局域网，然后开始扫描。</span>
          </div>
        </div>
      </aside>

      <main class="device-workspace">
        <div v-if="!selectedDevice" class="workspace-empty">
          <div class="empty-radar">
            <span /><span /><span />
            <el-icon :size="42"><Aim /></el-icon>
          </div>
          <h2>选择一台 Wireless HID</h2>
          <p>设备出现后，可在这里取得控制权、发送测试输入并执行管理操作。</p>
        </div>

        <template v-else>
          <section class="device-banner">
            <div class="device-identity">
              <span class="state-pill" :class="selectedDevice.connection_state">
                <i />{{ stateLabel(selectedDevice.connection_state) }}
              </span>
              <h2>{{ selectedDevice.name }}</h2>
              <div class="identity-line mono">
                {{ selectedDevice.device_id }} · {{ selectedDevice.ip }}:{{ selectedDevice.control_port }}
              </div>
            </div>
            <div class="banner-actions">
              <el-button
                v-if="!isConnected"
                type="primary"
                :loading="actionLoading === 'connect'"
                @click="connectDevice"
              >
                <el-icon><Link /></el-icon>取得控制权
              </el-button>
              <template v-else>
                <el-button
                  type="warning"
                  plain
                  :loading="actionLoading === 'release'"
                  @click="releaseAll"
                >
                  <el-icon><Unlock /></el-icon>释放全部按键
                </el-button>
                <el-button :loading="actionLoading === 'disconnect'" @click="disconnectDevice">
                  断开控制
                </el-button>
              </template>
              <el-dropdown trigger="click">
                <el-button circle aria-label="设备菜单"><el-icon><MoreFilled /></el-icon></el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="refreshDevices">刷新列表</el-dropdown-item>
                    <el-dropdown-item divided @click="removeDevice">移除设备记录</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </section>

          <section class="telemetry-strip">
            <div><span>固件</span><strong class="mono">{{ selectedDevice.firmware || '-' }}</strong></div>
            <div><span>Wi-Fi 信号</span><strong>{{ formatRssi(selectedDevice.rssi) }}</strong></div>
            <div>
              <span>CH9329</span>
              <strong :class="{ healthy: selectedDevice.ch9329 }">
                {{ selectedDevice.ch9329 ? '在线' : '离线' }}
              </strong>
            </div>
            <div>
              <span>控制心跳</span>
              <strong :class="{ healthy: isConnected }">
                {{ controlStatus?.last_heartbeat_at ? formatHeartbeat(controlStatus.last_heartbeat_at) : (isConnected ? '守护中' : '未启动') }}
              </strong>
            </div>
            <div><span>关联机器</span><strong>{{ selectedDevice.machine_name || '未关联' }}</strong></div>
          </section>

          <el-alert
            v-if="selectedDevice.last_error"
            class="device-error"
            type="error"
            :title="selectedDevice.last_error"
            :closable="false"
            show-icon
          />

          <el-tabs v-model="activeTab" class="workspace-tabs">
            <el-tab-pane name="control">
              <template #label>
                <span class="tab-label"><el-icon><Mouse /></el-icon>HID 控制</span>
              </template>
              <div class="control-grid" :class="{ disabled: !isConnected }">
                <section class="work-card keyboard-card">
                  <div class="card-heading">
                    <div><span class="section-kicker">BOOT KEYBOARD</span><h3>键盘测试</h3></div>
                    <el-tag :type="isConnected ? 'success' : 'info'" effect="plain">
                      {{ isConnected ? '可以发送' : '先取得控制权' }}
                    </el-tag>
                  </div>

                  <label class="field-label" for="whid-test-text">输入 ASCII 文本</label>
                  <el-input
                    id="whid-test-text"
                    v-model="keyboardText"
                    type="textarea"
                    :rows="4"
                    maxlength="500"
                    show-word-limit
                    :disabled="!isConnected"
                    placeholder="支持英文、数字和常用符号；发送后会逐键按下并释放"
                  />
                  <div class="inline-actions">
                    <el-input-number
                      v-model="keyDelay"
                      :min="0"
                      :max="1000"
                      :step="10"
                      :disabled="!isConnected"
                    />
                    <span class="unit-label">ms / 键</span>
                    <el-button
                      type="primary"
                      :disabled="!isConnected || !keyboardText"
                      :loading="actionLoading === 'keyboard'"
                      @click="sendText"
                    >发送文本</el-button>
                  </div>

                  <div class="keyboard-receiver">
                    <div class="receiver-heading">
                      <label class="field-label" for="whid-keyboard-receiver">输入接收区</label>
                      <span :class="{ active: keyboardReceiverFocused }">
                        <i />{{ keyboardReceiverFocused ? '正在接收键盘输入' : '发送时自动聚焦' }}
                      </span>
                    </div>
                    <el-input
                      id="whid-keyboard-receiver"
                      ref="keyboardReceiverRef"
                      v-model="keyboardReceiverText"
                      type="textarea"
                      :rows="2"
                      resize="none"
                      placeholder="USB HID 接在当前电脑时，发送结果会显示在这里"
                      @focus="keyboardReceiverFocused = true"
                      @blur="keyboardReceiverFocused = false"
                    />
                    <div class="receiver-footer">
                      <span>若 USB 接在另一台电脑，请在目标电脑的当前输入位置观察。</span>
                      <el-button
                        link
                        type="primary"
                        @mousedown.prevent
                        @click="keyboardReceiverText = ''"
                      >清空</el-button>
                    </div>
                  </div>

                  <div class="quick-key-row">
                    <span>快捷键</span>
                    <el-button
                      v-for="key in quickKeys"
                      :key="key.label"
                      size="small"
                      :disabled="!isConnected"
                      @click="sendQuickKey(key)"
                    >{{ key.label }}</el-button>
                  </div>

                  <el-collapse class="advanced-keys">
                    <el-collapse-item title="高级：原始 HID 报告" name="raw">
                      <div class="modifier-row">
                        <el-checkbox v-model="modifiers.ctrl">Ctrl</el-checkbox>
                        <el-checkbox v-model="modifiers.shift">Shift</el-checkbox>
                        <el-checkbox v-model="modifiers.alt">Alt</el-checkbox>
                        <el-checkbox v-model="modifiers.gui">GUI</el-checkbox>
                      </div>
                      <div class="raw-report-row">
                        <el-input
                          v-model="usageIds"
                          :disabled="!isConnected"
                          placeholder="Usage ID，最多 6 个，如 0x04, 0x05"
                        />
                        <el-button :disabled="!isConnected" @click="sendRawKeyboard">
                          按下并释放
                        </el-button>
                      </div>
                    </el-collapse-item>
                  </el-collapse>
                </section>

                <section class="work-card mouse-card">
                  <div class="card-heading">
                    <div><span class="section-kicker">POINTER LAB</span><h3>鼠标测试</h3></div>
                    <span class="mono subtle">REL / ABS</span>
                  </div>

                  <div class="mouse-section">
                    <div class="mouse-section-title">
                      <strong>相对移动</strong><span>单轴范围 -128..127</span>
                    </div>
                    <div class="mouse-pad">
                      <el-button :disabled="!isConnected" circle @click="moveMouse(0, -mouseStep)">
                        <el-icon><ArrowUp /></el-icon>
                      </el-button>
                      <div class="mouse-pad-middle">
                        <el-button :disabled="!isConnected" circle @click="moveMouse(-mouseStep, 0)">
                          <el-icon><ArrowLeft /></el-icon>
                        </el-button>
                        <span class="mouse-origin">0,0</span>
                        <el-button :disabled="!isConnected" circle @click="moveMouse(mouseStep, 0)">
                          <el-icon><ArrowRight /></el-icon>
                        </el-button>
                      </div>
                      <el-button :disabled="!isConnected" circle @click="moveMouse(0, mouseStep)">
                        <el-icon><ArrowDown /></el-icon>
                      </el-button>
                    </div>
                    <div class="mouse-click-row">
                      <span>按键测试</span>
                      <el-button-group>
                        <el-button
                          :disabled="!isConnected || mouseClickInProgress"
                          :loading="actionLoading === 'mouse-click-left'"
                          @click="clickMouse(1, 'left')"
                        >
                          <el-icon><Mouse /></el-icon>左键单击
                        </el-button>
                        <el-button
                          :disabled="!isConnected || mouseClickInProgress"
                          :loading="actionLoading === 'mouse-click-right'"
                          @click="clickMouse(2, 'right')"
                        >
                          <el-icon><Mouse /></el-icon>右键单击
                        </el-button>
                      </el-button-group>
                    </div>
                    <div class="mouse-options">
                      <label>步长 <el-input-number v-model="mouseStep" :min="1" :max="127" size="small" /></label>
                      <el-button :disabled="!isConnected" @click="scrollMouse(1)">滚轮 +1</el-button>
                      <el-button :disabled="!isConnected" @click="scrollMouse(-1)">滚轮 -1</el-button>
                    </div>
                  </div>

                  <div class="mouse-section absolute-section">
                    <div class="mouse-section-title">
                      <strong>绝对坐标</strong><span>12-bit · 0..4095</span>
                    </div>
                    <div class="coordinate-row">
                      <label>X <el-input-number v-model="absoluteMouse.x" :min="0" :max="4095" /></label>
                      <label>Y <el-input-number v-model="absoluteMouse.y" :min="0" :max="4095" /></label>
                      <el-button type="primary" plain :disabled="!isConnected" @click="moveAbsolute">
                        移动
                      </el-button>
                    </div>
                  </div>
                </section>
              </div>
            </el-tab-pane>

            <el-tab-pane name="management">
              <template #label>
                <span class="tab-label"><el-icon><Key /></el-icon>设备管理</span>
              </template>
              <div class="management-grid">
                <section class="work-card auth-card">
                  <div class="card-heading">
                    <div><span class="section-kicker">HMAC-SHA256</span><h3>管理认证</h3></div>
                    <span
                      class="auth-indicator"
                      :class="{ authenticated: selectedDevice.management_authenticated }"
                    >
                      <i />{{ selectedDevice.management_authenticated ? '会话有效' : '尚未认证' }}
                    </span>
                  </div>
                  <p class="card-note">PIN 只用于本次挑战应答，不会写入数据库或日志。</p>
                  <el-input
                    v-model="managementPin"
                    type="password"
                    show-password
                    autocomplete="new-password"
                    placeholder="用户 PIN 或出厂管理员凭据"
                    @keyup.enter="authenticate"
                  />
                  <el-button
                    type="primary"
                    :loading="actionLoading === 'authenticate'"
                    :disabled="!managementPin"
                    @click="authenticate"
                  >建立管理会话</el-button>
                  <div v-if="managementSession" class="session-ticket">
                    <span>角色</span><strong>{{ managementSession.role }}</strong>
                    <span>有效期</span><strong>{{ formatTime(managementSession.expires_at) }}</strong>
                  </div>
                </section>

                <section class="work-card management-actions">
                  <div class="card-heading">
                    <div><span class="section-kicker">DEVICE ADMIN</span><h3>设备操作</h3></div>
                    <el-button
                      text
                      :disabled="!selectedDevice.management_authenticated"
                      :loading="actionLoading === 'management-status'"
                      @click="loadManagementStatus"
                    >读取状态</el-button>
                  </div>

                  <div v-if="managementStatus" class="management-stats">
                    <div><span>运行时间</span><strong>{{ formatUptime(managementStatus.uptime) }}</strong></div>
                    <div><span>空闲堆</span><strong>{{ formatBytes(managementStatus.free_heap) }}</strong></div>
                    <div><span>RSSI</span><strong>{{ formatRssi(managementStatus.rssi) }}</strong></div>
                    <div><span>CH9329</span><strong>{{ managementStatus.ch9329 ? '在线' : '离线' }}</strong></div>
                  </div>

                  <label class="field-label">设备名称</label>
                  <div class="rename-row">
                    <el-input
                      v-model="renameValue"
                      maxlength="32"
                      :disabled="!selectedDevice.management_authenticated"
                    />
                    <el-button
                      :disabled="!selectedDevice.management_authenticated || !renameValue"
                      :loading="actionLoading === 'rename'"
                      @click="renameDevice"
                    >保存名称</el-button>
                  </div>

                  <div class="danger-zone">
                    <div>
                      <strong>网络与设备重置</strong>
                      <span>操作会先释放 HID 状态，并使当前连接中断。</span>
                    </div>
                    <div class="danger-actions">
                      <el-button
                        type="warning"
                        plain
                        :disabled="!selectedDevice.management_authenticated"
                        @click="enterProvisioning"
                      >进入 AP 配网</el-button>
                      <el-button
                        type="danger"
                        plain
                        :disabled="!selectedDevice.management_authenticated"
                        @click="factoryReset"
                      >恢复出厂</el-button>
                    </div>
                  </div>
                </section>
              </div>
            </el-tab-pane>

            <el-tab-pane name="ota">
              <template #label>
                <span class="tab-label"><el-icon><UploadFilled /></el-icon>OTA 与诊断</span>
              </template>
              <div class="ota-grid">
                <section class="work-card ota-card">
                  <div class="card-heading">
                    <div><span class="section-kicker">FIRMWARE UPDATE</span><h3>固件升级</h3></div>
                    <span class="firmware-limit mono">MAX 0x180000</span>
                  </div>
                  <div class="ota-checks">
                    <span><el-icon><CircleCheck /></el-icon>检查 ESP Magic 0xE9</span>
                    <span><el-icon><CircleCheck /></el-icon>计算并校验 SHA-256</span>
                    <span><el-icon><CircleCheck /></el-icon>升级前释放 TCP 控制权</span>
                  </div>
                  <el-upload
                    class="firmware-upload"
                    drag
                    action="#"
                    :auto-upload="false"
                    :limit="1"
                    accept=".bin,application/octet-stream"
                    :on-change="handleFirmwareChange"
                    :on-remove="handleFirmwareRemove"
                  >
                    <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                    <div class="el-upload__text">拖入 firmware.bin，或<em>选择文件</em></div>
                    <template #tip>
                      <div class="el-upload__tip">仅接受不超过 1536 KiB 的 ESP 应用镜像。</div>
                    </template>
                  </el-upload>
                  <el-progress
                    v-if="otaUploading"
                    :percentage="otaProgress"
                    :status="otaProgress === 100 ? 'success' : undefined"
                  />
                  <el-button
                    type="primary"
                    size="large"
                    :disabled="!firmwareFile || !selectedDevice.management_authenticated"
                    :loading="otaUploading"
                    @click="startOta"
                  >校验并升级设备</el-button>
                  <el-alert
                    v-if="otaResult"
                    type="success"
                    :closable="false"
                    show-icon
                    :title="`固件已上传，SHA-256 ${otaResult.sha256}`"
                    description="设备将重启；请在 30–60 秒内重新发现并核对固件版本。"
                  />
                </section>

                <section class="work-card diagnostics-card">
                  <div class="card-heading">
                    <div><span class="section-kicker">PROTOCOL SNAPSHOT</span><h3>链路诊断</h3></div>
                  </div>
                  <dl class="diagnostic-list">
                    <div><dt>协议版本</dt><dd class="mono">WHID / 1</dd></div>
                    <div><dt>控制端口</dt><dd class="mono">{{ selectedDevice.control_port }}</dd></div>
                    <div><dt>管理端口</dt><dd class="mono">{{ selectedDevice.management_port }}</dd></div>
                    <div><dt>最大 TCP 负载</dt><dd class="mono">64 bytes</dd></div>
                    <div><dt>最后发现</dt><dd>{{ formatTime(selectedDevice.last_seen) }}</dd></div>
                    <div><dt>管理链路</dt><dd>明文 HTTP · 仅可信局域网</dd></div>
                  </dl>
                  <el-alert
                    type="warning"
                    :closable="false"
                    show-icon
                    title="OTA 超时不代表升级失败"
                    description="连接中断后先重新发现并读取版本，避免立即重复刷写。"
                  />
                </section>
              </div>
            </el-tab-pane>
          </el-tabs>
        </template>
      </main>
    </div>

    <el-dialog v-model="apDialogVisible" title="AP 配网" width="560px" destroy-on-close>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="先让运行后端的电脑连接 WirelessHID-xxxx 开放热点"
        description="网关地址应从当前 Wi-Fi 连接读取；常见值为 192.168.4.1，但不要永久依赖该地址。"
      />
      <el-form class="ap-form" label-position="top">
        <el-form-item label="AP 网关 IPv4">
          <el-input v-model="apForm.gateway_ip" placeholder="例如 192.168.4.1" />
        </el-form-item>
        <el-form-item label="Wi-Fi SSID"><el-input v-model="apForm.ssid" /></el-form-item>
        <el-form-item label="Wi-Fi 密码">
          <el-input v-model="apForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="设备名称">
          <el-input v-model="apForm.name" maxlength="32" />
        </el-form-item>
        <div class="ap-pin-grid">
          <el-form-item label="当前 PIN / 出厂凭据">
            <el-input v-model="apForm.current_pin" type="password" show-password />
          </el-form-item>
          <el-form-item label="新用户 PIN（6 位数字）">
            <el-input v-model="apForm.new_pin" type="password" maxlength="6" show-password />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="apDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="apSubmitting" @click="submitApProvision">
          保存配置并重启
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  authenticateWirelessHid,
  connectWirelessHidDevice,
  deleteWirelessHidDevice,
  disconnectWirelessHidDevice,
  discoverWirelessHidDevices,
  enterWirelessHidProvisioning,
  factoryResetWirelessHidDevice,
  getWirelessHidDevices,
  getWirelessHidManagementStatus,
  getWirelessHidStatus,
  provisionWirelessHidAccessPoint,
  releaseWirelessHidAll,
  renameWirelessHidDevice,
  sendWirelessHidAbsoluteMouse,
  sendWirelessHidKeyboard,
  sendWirelessHidRelativeMouse,
  uploadWirelessHidFirmware,
} from '../api'

const devices = ref([])
const selectedId = ref(null)
const loading = ref(false)
const discovering = ref(false)
const knownIp = ref('')
const keyword = ref('')
const activeTab = ref('control')
const actionLoading = ref('')
const controlStatus = ref(null)
let refreshTimer = null
let liveRefreshInFlight = false

const selectedDevice = computed(() => devices.value.find((item) => item.id === selectedId.value) || null)
const isConnected = computed(() => selectedDevice.value?.connection_state === 'connected')
const filteredDevices = computed(() => {
  const query = keyword.value.trim().toLowerCase()
  if (!query) return devices.value
  return devices.value.filter((item) =>
    [item.name, item.device_id, item.ip].some((value) =>
      String(value || '').toLowerCase().includes(query)),
  )
})

const stateLabel = (state) => ({
  connected: '控制中',
  ready: '可连接',
  occupied: '已占用',
  offline: '未响应',
  invalid: '配置异常',
}[state] || '未知')

async function refreshDevices(silent = false) {
  if (!silent) loading.value = true
  try {
    devices.value = await getWirelessHidDevices()
    if (selectedId.value && !devices.value.some((item) => item.id === selectedId.value)) {
      selectedId.value = null
    }
    if (!selectedId.value && devices.value.length) selectedId.value = devices.value[0].id
  } catch (error) {
    if (!silent) ElMessage.error(error.message)
  } finally {
    if (!silent) loading.value = false
  }
}

async function refreshLiveDevices() {
  if (liveRefreshInFlight || discovering.value) return
  liveRefreshInFlight = true
  try {
    devices.value = await discoverWirelessHidDevices({ timeout_millis: 800 })
    if (selectedId.value && !devices.value.some((item) => item.id === selectedId.value)) {
      selectedId.value = null
    }
    if (!selectedId.value && devices.value.length) selectedId.value = devices.value[0].id
    await loadControlStatus()
  } catch {
    await refreshDevices(true)
  } finally {
    liveRefreshInFlight = false
  }
}

async function discover() {
  discovering.value = true
  try {
    devices.value = await discoverWirelessHidDevices({
      ip: knownIp.value.trim() || null,
      timeout_millis: 1500,
    })
    if (devices.value.length) {
      if (!selectedId.value || !devices.value.some((item) => item.id === selectedId.value)) {
        selectedId.value = devices.value[0].id
      }
      ElMessage.success(`已更新 ${devices.value.length} 台 Wireless HID`)
    } else {
      ElMessage.warning('本轮扫描没有收到设备响应')
    }
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    discovering.value = false
  }
}

function selectDevice(id) {
  selectedId.value = id
  controlStatus.value = null
  activeTab.value = 'control'
}

async function connectDevice() {
  await runAction('connect', async () => {
    replaceDevice(await connectWirelessHidDevice(selectedId.value))
    await loadControlStatus()
    ElMessage.success('已取得设备控制权，独立心跳已启动')
  })
}

async function disconnectDevice() {
  await runAction('disconnect', async () => {
    replaceDevice(await disconnectWirelessHidDevice(selectedId.value))
    controlStatus.value = null
    ElMessage.success('已释放按键并断开控制')
  })
}

async function releaseAll() {
  await runAction('release', async () => {
    await releaseWirelessHidAll(selectedId.value)
    ElMessage.success('键盘与鼠标状态已全部释放')
  })
}

async function loadControlStatus() {
  if (!isConnected.value) return
  try {
    controlStatus.value = await getWirelessHidStatus(selectedId.value)
  } catch {
    await refreshDevices(true)
  }
}

const keyboardText = ref('')
const keyDelay = ref(20)
const keyboardReceiverRef = ref(null)
const keyboardReceiverText = ref('')
const keyboardReceiverFocused = ref(false)
const usageIds = ref('')
const modifiers = reactive({ ctrl: false, shift: false, alt: false, gui: false })
const quickKeys = [
  { label: 'Esc', modifier: 0, keys: [0x29] },
  { label: 'Enter', modifier: 0, keys: [0x28] },
  { label: 'Tab', modifier: 0, keys: [0x2B] },
  { label: 'F5', modifier: 0, keys: [0x3E] },
  { label: 'Ctrl + C', modifier: 0x01, keys: [0x06] },
  { label: 'Alt + Tab', modifier: 0x04, keys: [0x2B] },
]

async function sendText() {
  keyboardReceiverRef.value?.focus()
  await runAction('keyboard', async () => {
    await sendWirelessHidKeyboard(selectedId.value, {
      text: keyboardText.value,
      delay_millis: keyDelay.value,
    })
    ElMessage.success('设备已确认接收；请查看输入接收区或目标电脑')
  })
}

async function sendQuickKey(key) {
  await runAction('quick-key', () =>
    sendWirelessHidKeyboard(selectedId.value, {
      modifier: key.modifier,
      keys: key.keys,
      tap: true,
    }))
}

async function sendRawKeyboard() {
  const keys = usageIds.value
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean)
    .map((value) => Number.parseInt(value, value.toLowerCase().startsWith('0x') ? 16 : 10))
  if (!keys.length || keys.length > 6 || keys.some((value) => !Number.isInteger(value) || value < 0 || value > 255)) {
    ElMessage.warning('请输入 1–6 个有效 Usage ID')
    return
  }
  const modifier =
    (modifiers.ctrl ? 0x01 : 0) |
    (modifiers.shift ? 0x02 : 0) |
    (modifiers.alt ? 0x04 : 0) |
    (modifiers.gui ? 0x08 : 0)
  await sendQuickKey({ modifier, keys })
}

const mouseStep = ref(20)
const absoluteMouse = reactive({ x: 2048, y: 2048 })
const mouseClickInProgress = computed(() => actionLoading.value.startsWith('mouse-click-'))
async function moveMouse(x, y) {
  await runAction('mouse', () =>
    sendWirelessHidRelativeMouse(selectedId.value, { buttons: 0, x, y, wheel: 0 }))
}
async function clickMouse(buttons, side) {
  await runAction(`mouse-click-${side}`, async () => {
    let failure = null
    try {
      await sendWirelessHidRelativeMouse(
        selectedId.value,
        { buttons, x: 0, y: 0, wheel: 0 },
      )
      await new Promise((resolve) => window.setTimeout(resolve, 30))
    } catch (error) {
      failure = error
    }
    try {
      await sendWirelessHidRelativeMouse(
        selectedId.value,
        { buttons: 0, x: 0, y: 0, wheel: 0 },
      )
    } catch (error) {
      if (!failure) failure = error
    }
    if (failure) throw failure
  })
}
async function scrollMouse(wheel) {
  await runAction('mouse', () =>
    sendWirelessHidRelativeMouse(selectedId.value, { buttons: 0, x: 0, y: 0, wheel }))
}
async function moveAbsolute() {
  await runAction('mouse', () =>
    sendWirelessHidAbsoluteMouse(selectedId.value, {
      buttons: 0,
      x: absoluteMouse.x,
      y: absoluteMouse.y,
      wheel: 0,
    }))
}

const managementPin = ref('')
const managementSession = ref(null)
const managementStatus = ref(null)
const renameValue = ref('')

watch(selectedId, (id) => {
  const device = devices.value.find((item) => item.id === id)
  renameValue.value = device?.name || ''
  managementSession.value = null
  managementStatus.value = null
}, { immediate: true })

async function authenticate() {
  const pin = managementPin.value
  managementPin.value = ''
  await runAction('authenticate', async () => {
    managementSession.value = await authenticateWirelessHid(selectedId.value, pin)
    await refreshDevices(true)
    await loadManagementStatus()
    ElMessage.success(`管理认证成功：${managementSession.value.role}`)
  })
}

async function loadManagementStatus() {
  await runAction('management-status', async () => {
    managementStatus.value = await getWirelessHidManagementStatus(selectedId.value)
  })
}

async function renameDevice() {
  await runAction('rename', async () => {
    replaceDevice(await renameWirelessHidDevice(selectedId.value, renameValue.value.trim()))
    ElMessage.success('设备名称已更新')
  })
}

async function enterProvisioning() {
  try {
    await ElMessageBox.confirm(
      '设备将释放所有键鼠状态、断开当前 Wi-Fi 并进入 AP 配网模式。是否继续？',
      '进入 AP 配网',
      { type: 'warning', confirmButtonText: '进入 AP 模式', cancelButtonText: '取消' },
    )
  } catch { return }
  await runAction('provision', async () => {
    await enterWirelessHidProvisioning(selectedId.value)
    await refreshDevices(true)
    ElMessage.success('设备正在切换到 AP 配网模式')
  })
}

async function factoryReset() {
  let result
  try {
    result = await ElMessageBox.prompt(
      `此操作会清除 Wi-Fi、设备名称和用户 PIN。请输入设备 ID ${selectedDevice.value.device_id} 确认：`,
      '恢复出厂设置',
      {
        type: 'error',
        confirmButtonText: '恢复出厂',
        cancelButtonText: '取消',
        inputValidator: (value) => value === selectedDevice.value.device_id || '设备 ID 不匹配',
      },
    )
  } catch { return }
  await runAction('factory-reset', async () => {
    await factoryResetWirelessHidDevice(selectedId.value, result.value)
    await refreshDevices(true)
    ElMessage.success('设备将在约 1 秒后恢复出厂并重启')
  })
}

const firmwareFile = ref(null)
const otaUploading = ref(false)
const otaProgress = ref(0)
const otaResult = ref(null)
function handleFirmwareChange(uploadFile) {
  firmwareFile.value = uploadFile.raw
  otaResult.value = null
}
function handleFirmwareRemove() {
  firmwareFile.value = null
  otaResult.value = null
}
async function startOta() {
  if (!firmwareFile.value) return
  if (firmwareFile.value.size > 0x180000) {
    ElMessage.error('固件超过 1536 KiB 上限')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将升级 ${selectedDevice.value.name}。控制连接会先释放，升级期间请勿断电。`,
      '确认 OTA 升级',
      { type: 'warning', confirmButtonText: '开始升级', cancelButtonText: '取消' },
    )
  } catch { return }
  otaUploading.value = true
  otaProgress.value = 0
  try {
    otaResult.value = await uploadWirelessHidFirmware(
      selectedId.value,
      firmwareFile.value,
      (progress) => { otaProgress.value = progress },
    )
    ElMessage.success('设备已接收固件并准备重启')
    await refreshDevices(true)
  } catch (error) {
    ElMessage.error(`${error.message}；若连接中断，请先重新发现并核对版本`)
  } finally {
    otaUploading.value = false
  }
}

const apDialogVisible = ref(false)
const apSubmitting = ref(false)
const apForm = reactive({
  gateway_ip: '192.168.4.1',
  current_pin: '',
  ssid: '',
  password: '',
  name: '',
  new_pin: '',
})
async function submitApProvision() {
  if (!apForm.gateway_ip || !apForm.ssid) {
    ElMessage.warning('AP 网关和 Wi-Fi SSID 不能为空')
    return
  }
  if (apForm.new_pin && !/^\d{6}$/.test(apForm.new_pin)) {
    ElMessage.warning('新用户 PIN 必须是 6 位数字')
    return
  }
  apSubmitting.value = true
  try {
    await provisionWirelessHidAccessPoint({ ...apForm })
    apForm.current_pin = ''
    apForm.password = ''
    apForm.new_pin = ''
    apDialogVisible.value = false
    ElMessage.success('配网参数已保存，设备正在重启')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    apSubmitting.value = false
  }
}

async function removeDevice() {
  try {
    await ElMessageBox.confirm('仅移除中控平台中的设备记录，不会修改硬件配置。', '移除设备', {
      type: 'warning',
      confirmButtonText: '移除记录',
      cancelButtonText: '取消',
    })
  } catch { return }
  await runAction('delete', async () => {
    await deleteWirelessHidDevice(selectedId.value)
    selectedId.value = null
    await refreshDevices()
    ElMessage.success('设备记录已移除')
  })
}

async function runAction(name, operation) {
  actionLoading.value = name
  try {
    await operation()
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    actionLoading.value = ''
  }
}

function replaceDevice(updated) {
  const index = devices.value.findIndex((item) => item.id === updated.id)
  if (index >= 0) devices.value[index] = updated
}
function formatRssi(value) {
  return Number.isFinite(Number(value)) ? `${value} dBm` : '-'
}
function formatTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleString('zh-CN', { hour12: false })
}
function formatHeartbeat(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '刚刚'
    : `最近 ${date.toLocaleTimeString('zh-CN', { hour12: false })}`
}
function formatUptime(seconds) {
  const value = Number(seconds)
  if (!Number.isFinite(value)) return '-'
  return `${Math.floor(value / 3600)} 小时 ${Math.floor((value % 3600) / 60)} 分`
}
function formatBytes(value) {
  const bytes = Number(value)
  return Number.isFinite(bytes) ? `${Math.round(bytes / 1024)} KiB` : '-'
}

onMounted(async () => {
  await refreshDevices()
  await refreshLiveDevices()
  refreshTimer = window.setInterval(async () => {
    await refreshLiveDevices()
  }, 5000)
})
onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>

<style scoped>
.whid-console {
  --ink: #17324d;
  --muted: #6c8296;
  --line: #d7e2ea;
  --paper: #f7fafc;
  --signal: #16a7b7;
  --signal-dark: #0b7180;
  --live: #1f9d68;
  --warn: #d88a18;
  display: flex;
  height: calc(100vh - 40px);
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  color: var(--ink);
  font-family: "Microsoft YaHei", "PingFang SC", system-ui, sans-serif;
}

.console-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(240px, .8fr) minmax(460px, 1.35fr);
  flex: 0 0 auto;
  gap: 30px 44px;
  padding: 28px 32px 24px;
  overflow: hidden;
  border-radius: 18px 18px 0 0;
  color: #f5fbff;
  background:
    radial-gradient(circle at 85% 0%, rgba(22, 167, 183, .25), transparent 34%),
    linear-gradient(118deg, #102a43 0%, #173c58 58%, #113448 100%);
  box-shadow: 0 16px 40px rgba(20, 51, 75, .14);
}
.console-hero::after {
  position: absolute;
  right: -80px;
  bottom: -95px;
  width: 260px;
  height: 260px;
  border: 1px solid rgba(119, 222, 229, .15);
  border-radius: 50%;
  box-shadow: 0 0 0 38px rgba(119, 222, 229, .04), 0 0 0 80px rgba(119, 222, 229, .025);
  content: "";
}
.hero-copy, .signal-path, .discovery-bar { position: relative; z-index: 1; }
.eyebrow, .section-kicker {
  color: #77dee5;
  font: 700 11px/1.2 Consolas, "Microsoft YaHei", monospace;
  letter-spacing: .16em;
}
.hero-copy h1 { margin: 8px 0 7px; font-size: 30px; line-height: 1.15; letter-spacing: -.04em; }
.hero-copy p { max-width: 520px; margin: 0; color: #b9ccd9; font-size: 14px; line-height: 1.7; }

.signal-path { display: flex; align-items: center; justify-content: flex-end; }
.signal-node { display: flex; align-items: center; gap: 9px; opacity: .42; transition: opacity .25s ease; }
.signal-node.active { opacity: 1; }
.signal-node strong, .signal-node small { display: block; white-space: nowrap; }
.signal-node strong { font-size: 13px; }
.signal-node small { margin-top: 3px; color: #8fb0c3; font: 11px Consolas, monospace; }
.signal-index {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border: 1px solid rgba(119, 222, 229, .35);
  border-radius: 50%;
  color: #7ce2e8;
  font: 700 10px Consolas, monospace;
}
.signal-wire {
  position: relative;
  width: clamp(32px, 5vw, 72px);
  height: 1px;
  margin: 0 11px;
  overflow: hidden;
  background: rgba(255, 255, 255, .16);
}
.signal-wire.live { background: rgba(119, 222, 229, .42); }
.signal-wire i { position: absolute; inset: -1px auto -1px -25%; width: 25%; background: #8df4f4; opacity: 0; }
.signal-wire.live i { opacity: 1; animation: signal-pulse 1.8s linear infinite; }
@keyframes signal-pulse { to { left: 110%; } }

.discovery-bar { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: 10px; }
.ip-input { width: min(350px, 100%); }
.discovery-bar :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, .08);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, .18) inset;
}
.discovery-bar :deep(.el-input__inner) { color: white; }
.discovery-bar :deep(.el-input__inner::placeholder) { color: #9db5c5; }
.ap-button { color: #d8f6f7; border-color: rgba(125, 224, 231, .35); background: rgba(255, 255, 255, .06); }

.console-layout {
  display: grid;
  min-height: 0;
  flex: 1 1 auto;
  grid-template-columns: 300px minmax(0, 1fr);
  overflow: hidden;
  border: 1px solid #dce6ed;
  border-top: 0;
  border-radius: 0 0 18px 18px;
  background: white;
  box-shadow: 0 18px 42px rgba(28, 60, 82, .08);
}
.device-rail {
  min-height: 0;
  padding: 24px 18px;
  overflow-y: auto;
  border-right: 1px solid var(--line);
  background: #f2f7fa;
}
.rail-heading { display: flex; align-items: flex-end; justify-content: space-between; margin: 0 4px 16px; }
.rail-heading h2 { margin: 4px 0 0; font-size: 20px; letter-spacing: -.03em; }
.rail-heading .section-kicker { color: var(--signal-dark); }
.device-count {
  display: grid;
  min-width: 30px;
  height: 30px;
  padding: 0 8px;
  place-items: center;
  border-radius: 9px;
  color: var(--signal-dark);
  background: #daf2f4;
  font: 700 12px Consolas, monospace;
}
.rail-search { margin-bottom: 14px; }
.device-list { min-height: 220px; }
.device-card {
  position: relative;
  display: grid;
  width: 100%;
  grid-template-columns: 10px 1fr auto;
  gap: 10px;
  align-items: center;
  margin-bottom: 9px;
  padding: 14px 12px;
  border: 1px solid transparent;
  border-radius: 12px;
  color: var(--ink);
  text-align: left;
  background: transparent;
  cursor: pointer;
  transition: border-color .18s ease, background .18s ease, transform .18s ease;
}
.device-card:hover { transform: translateX(2px); background: white; }
.device-card.selected { border-color: #9ed7dc; background: white; box-shadow: 0 7px 22px rgba(31, 94, 116, .09); }
.device-state-dot { width: 8px; height: 8px; border-radius: 50%; background: #aab8c3; box-shadow: 0 0 0 4px rgba(170, 184, 195, .14); }
.device-state-dot.connected { background: var(--live); box-shadow: 0 0 0 4px rgba(31, 157, 104, .13); }
.device-state-dot.ready { background: var(--signal); box-shadow: 0 0 0 4px rgba(22, 167, 183, .13); }
.device-state-dot.occupied { background: var(--warn); box-shadow: 0 0 0 4px rgba(216, 138, 24, .13); }
.device-card-copy { min-width: 0; }
.device-card-copy strong, .device-card-copy span, .device-card-copy small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.device-card-copy strong { font-size: 14px; }
.device-card-copy span { margin-top: 5px; color: #3d647d; font-size: 12px; }
.device-card-copy small { margin-top: 4px; color: #8a9aa7; font-size: 11px; }
.state-label { align-self: flex-start; padding: 3px 6px; border-radius: 5px; color: #788b99; background: #e6edf1; font-size: 10px; white-space: nowrap; }
.state-label.connected { color: #087247; background: #d9f1e7; }
.state-label.ready { color: #0b7180; background: #d9f1f3; }
.state-label.occupied { color: #93600f; background: #fbecd2; }
.rail-empty { display: grid; gap: 8px; padding: 50px 18px; justify-items: center; color: #8498a7; text-align: center; }
.rail-empty strong { color: #49677c; font-size: 14px; }
.rail-empty span { font-size: 12px; line-height: 1.6; }

.device-workspace {
  min-width: 0;
  min-height: 0;
  padding: 26px 28px 32px;
  overflow-y: auto;
  background: white;
  border-radius: 0 0 18px;
}
.workspace-empty { display: grid; height: 100%; min-height: 520px; place-content: center; justify-items: center; text-align: center; }
.workspace-empty h2 { margin: 22px 0 8px; font-size: 22px; }
.workspace-empty p { margin: 0; color: var(--muted); }
.empty-radar { position: relative; display: grid; width: 112px; height: 112px; place-items: center; color: var(--signal); }
.empty-radar span { position: absolute; inset: 0; border: 1px solid #b8e1e4; border-radius: 50%; }
.empty-radar span:nth-child(2) { inset: 16px; }
.empty-radar span:nth-child(3) { inset: 33px; }

.device-banner { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding-bottom: 20px; }
.device-identity h2 { margin: 8px 0 5px; font-size: 26px; letter-spacing: -.04em; }
.identity-line { color: #678093; font-size: 12px; }
.state-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 9px;
  border-radius: 999px;
  color: #60788b;
  background: #edf2f5;
  font-size: 11px;
  font-weight: 700;
}
.state-pill i, .auth-indicator i { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.state-pill.connected { color: #11784e; background: #dcf2e8; }
.state-pill.ready { color: #0b7180; background: #daf1f3; }
.state-pill.occupied { color: #93600f; background: #fbecd2; }
.banner-actions { display: flex; align-items: center; gap: 9px; }

.telemetry-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--paper);
}
.telemetry-strip > div { min-width: 0; padding: 13px 15px; border-right: 1px solid var(--line); }
.telemetry-strip > div:last-child { border-right: 0; }
.telemetry-strip span, .telemetry-strip strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.telemetry-strip span { margin-bottom: 6px; color: var(--muted); font-size: 10px; letter-spacing: .06em; text-transform: uppercase; }
.telemetry-strip strong { font-size: 13px; }
.healthy { color: var(--live); }
.device-error { margin-top: 14px; }
.workspace-tabs { margin-top: 20px; }
.workspace-tabs :deep(.el-tabs__header) { margin-bottom: 18px; }
.workspace-tabs :deep(.el-tabs__item) { height: 46px; padding: 0 22px; }
.tab-label { display: inline-flex; align-items: center; gap: 7px; }

.control-grid, .management-grid, .ota-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(330px, .85fr);
  gap: 18px;
}
.control-grid.disabled .work-card { opacity: .82; }
.work-card { min-width: 0; padding: 21px; border: 1px solid var(--line); border-radius: 14px; background: white; }
.card-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.card-heading .section-kicker { color: var(--signal-dark); }
.card-heading h3 { margin: 5px 0 0; font-size: 18px; }
.subtle { color: #8ba0af; font-size: 12px; }
.field-label { display: block; margin: 0 0 8px; color: #526c80; font-size: 12px; font-weight: 700; }
.inline-actions { display: flex; align-items: center; justify-content: flex-end; gap: 9px; margin-top: 12px; }
.inline-actions :deep(.el-input-number) { width: 112px; }
.unit-label { margin-right: auto; color: var(--muted); font-size: 12px; }
.keyboard-receiver {
  margin-top: 18px;
  padding: 14px;
  border: 1px solid #cde3e5;
  border-radius: 11px;
  background: #f3fafb;
}
.receiver-heading,
.receiver-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.receiver-heading { margin-bottom: 9px; }
.receiver-heading .field-label { margin: 0; }
.receiver-heading > span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #78909f;
  font-size: 11px;
}
.receiver-heading > span i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #aab8c3;
  box-shadow: 0 0 0 3px rgba(170, 184, 195, .14);
}
.receiver-heading > span.active { color: var(--live); }
.receiver-heading > span.active i {
  background: var(--live);
  box-shadow: 0 0 0 3px rgba(31, 157, 104, .14);
}
.keyboard-receiver :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px var(--live) inset;
}
.receiver-footer { margin-top: 7px; }
.receiver-footer > span { color: var(--muted); font-size: 11px; line-height: 1.5; }
.receiver-footer :deep(.el-button) { flex: 0 0 auto; }
.quick-key-row { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; margin-top: 22px; }
.quick-key-row > span { margin-right: 4px; color: var(--muted); font-size: 12px; }
.advanced-keys { margin-top: 14px; border-top: 1px solid #edf1f4; border-bottom: 0; }
.advanced-keys :deep(.el-collapse-item__header) { color: #60788b; font-size: 12px; }
.modifier-row { display: flex; flex-wrap: wrap; gap: 12px; }
.raw-report-row { display: flex; gap: 10px; margin-top: 10px; }

.mouse-section { padding: 3px 0 18px; }
.mouse-section-title { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 14px; }
.mouse-section-title strong { font-size: 14px; }
.mouse-section-title span { color: var(--muted); font: 11px Consolas, monospace; }
.mouse-pad { display: grid; gap: 6px; justify-items: center; margin: 0 auto 15px; }
.mouse-pad-middle { display: flex; align-items: center; gap: 8px; }
.mouse-origin { display: grid; width: 45px; height: 35px; place-items: center; border: 1px dashed #b8cbd6; border-radius: 9px; color: #7c91a0; font: 11px Consolas, monospace; }
.mouse-click-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding: 10px 11px;
  border: 1px solid #dce9ee;
  border-radius: 10px;
  background: #f7fafc;
}
.mouse-click-row > span {
  flex: 0 0 auto;
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.mouse-click-row :deep(.el-button-group) {
  display: flex;
  min-width: 0;
  flex: 1;
}
.mouse-click-row :deep(.el-button) {
  min-width: 0;
  flex: 1;
  padding-right: 9px;
  padding-left: 9px;
}
.mouse-click-row :deep(.el-button .el-icon) { margin-right: 5px; }
.mouse-options { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; }
.mouse-options label { display: flex; align-items: center; gap: 7px; color: var(--muted); font-size: 12px; }
.mouse-options :deep(.el-input-number) { width: 90px; }
.absolute-section { padding: 18px 0 0; border-top: 1px solid var(--line); }
.coordinate-row { display: flex; align-items: center; gap: 9px; }
.coordinate-row label { display: flex; align-items: center; gap: 6px; color: var(--muted); font: 12px Consolas, monospace; }
.coordinate-row :deep(.el-input-number) { width: 118px; }

.auth-card { display: flex; flex-direction: column; gap: 12px; align-self: start; background: linear-gradient(145deg, #f5fbfc, white); }
.auth-card .card-heading { margin-bottom: 0; }
.auth-indicator { display: inline-flex; align-items: center; gap: 6px; color: #8a9aa7; font-size: 11px; font-weight: 700; }
.auth-indicator.authenticated { color: var(--live); }
.card-note { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.7; }
.session-ticket { display: grid; grid-template-columns: auto 1fr; gap: 7px 12px; padding: 12px; border: 1px dashed #9cd0d5; border-radius: 9px; background: #ecf8f9; font-size: 12px; }
.session-ticket span { color: var(--muted); }
.management-stats { display: grid; grid-template-columns: repeat(4, 1fr); margin-bottom: 20px; border: 1px solid var(--line); border-radius: 10px; }
.management-stats div { padding: 11px; border-right: 1px solid var(--line); }
.management-stats div:last-child { border-right: 0; }
.management-stats span, .management-stats strong { display: block; }
.management-stats span { color: var(--muted); font-size: 10px; }
.management-stats strong { margin-top: 5px; font-size: 12px; }
.rename-row { display: flex; gap: 9px; }
.danger-zone { display: flex; align-items: flex-start; flex-direction: column; gap: 14px; margin-top: 22px; padding-top: 18px; border-top: 1px solid #f1d7d4; }
.danger-zone strong, .danger-zone span { display: block; }
.danger-zone strong { color: #8c3b35; font-size: 13px; }
.danger-zone span { margin-top: 5px; color: var(--muted); font-size: 11px; }
.danger-actions { display: flex; width: 100%; }
.danger-actions :deep(.el-button) { flex: 1; }

.ota-checks { display: grid; gap: 9px; margin-bottom: 18px; padding: 13px; border-radius: 10px; background: #eef8f5; }
.ota-checks span { display: flex; align-items: center; gap: 7px; color: #386d5b; font-size: 12px; }
.firmware-limit { color: #60788b; font-size: 11px; }
.firmware-upload { margin-bottom: 18px; }
.ota-card > .el-button { width: 100%; margin-top: 14px; }
.ota-card .el-alert { margin-top: 16px; }
.diagnostic-list { margin: 0 0 18px; }
.diagnostic-list > div { display: flex; justify-content: space-between; gap: 20px; padding: 10px 0; border-bottom: 1px solid #edf1f4; }
.diagnostic-list dt { color: var(--muted); font-size: 12px; }
.diagnostic-list dd { margin: 0; color: var(--ink); font-size: 12px; text-align: right; }
.ap-form { margin-top: 18px; }
.ap-pin-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.mono { font-family: Consolas, "SFMono-Regular", monospace; }

@media (max-width: 1180px) {
  .console-hero { grid-template-columns: 1fr; }
  .signal-path { justify-content: flex-start; }
  .telemetry-strip { grid-template-columns: repeat(3, 1fr); }
  .telemetry-strip > div:nth-child(3) { border-right: 0; }
  .telemetry-strip > div:nth-child(n+4) { border-top: 1px solid var(--line); }
  .control-grid, .management-grid, .ota-grid { grid-template-columns: 1fr; }
}
@media (max-width: 850px) {
  .console-layout { grid-template-columns: 1fr; grid-template-rows: auto auto; min-height: 0; }
  .device-rail { border-right: 0; border-bottom: 1px solid var(--line); }
  .device-list {
    display: grid;
    min-height: 0;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    grid-auto-rows: max-content;
    align-content: start;
    gap: 8px;
  }
  .device-card { align-self: start; margin-bottom: 0; }
  .device-banner { align-items: flex-start; flex-direction: column; }
  .banner-actions { flex-wrap: wrap; }
}
@media (max-width: 620px) {
  .console-hero { padding: 24px 20px; border-radius: 12px 12px 0 0; }
  .signal-path { display: none; }
  .discovery-bar { flex-wrap: wrap; }
  .ip-input { width: 100%; }
  .device-workspace { padding: 20px 16px; }
  .device-banner, .danger-zone { align-items: flex-start; flex-direction: column; }
  .banner-actions, .danger-actions { flex-wrap: wrap; }
  .telemetry-strip { grid-template-columns: 1fr 1fr; }
  .telemetry-strip > div { border-top: 1px solid var(--line); }
  .telemetry-strip > div:nth-child(-n+2) { border-top: 0; }
  .telemetry-strip > div:nth-child(even) { border-right: 0; }
  .coordinate-row, .raw-report-row { flex-wrap: wrap; }
  .management-stats { grid-template-columns: 1fr 1fr; }
  .management-stats div:nth-child(2) { border-right: 0; }
  .management-stats div:nth-child(n+3) { border-top: 1px solid var(--line); }
  .ap-pin-grid { grid-template-columns: 1fr; gap: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .signal-wire.live i { animation: none; }
  .device-card { transition: none; }
}
</style>
