<template>
  <div class="page-container">
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索名称/MAC/IP..." clearable style="width: 240px" @input="handleSearch">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select v-model="filterStatus" placeholder="全部状态" clearable style="width: 120px" @change="handleSearch">
        <el-option label="在线" value="online" />
        <el-option label="离线" value="offline" />
        <el-option label="忙碌" value="busy" />
        <el-option label="禁用" value="disabled" />
      </el-select>
      <el-button type="primary" @click="openMachineDialog()">
        <el-icon><Plus /></el-icon> 新增机器
      </el-button>
    </div>

    <div class="split-layout">
      <section class="left-panel">
        <div class="panel-heading">
          <div>
            <span class="panel-eyebrow">机器目录</span>
            <strong>运行节点</strong>
          </div>
          <span class="result-count">{{ total }} 台</span>
        </div>
        <div class="table-shell">
          <el-table
            ref="machineTableRef"
            :data="list"
            border
            stripe
            v-loading="loading"
            highlight-current-row
            row-key="id"
            height="100%"
            @current-change="selectMachine"
          >
            <el-table-column label="机器" min-width="190">
              <template #default="{ row }">
                <div class="machine-list-identity">
                  <strong>{{ machineDisplayName(row) }}</strong>
                  <span>{{ row.hostname || '未上报主机名' }}</span>
                  <small>{{ row.ip_address || '-' }} · {{ row.mac_address }}</small>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="88" align="center">
              <template #default="{ row }">
                <el-tag :type="typeTagType(row.type)" size="small">{{ typeLabel(row.type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="76" align="center">
              <template #default="{ row }">
                <span class="machine-status" :class="`status-${row.status}`">
                  <i aria-hidden="true"></i>{{ statusLabel(row.status) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="最后心跳" width="112" align="center">
              <template #default="{ row }">
                <span class="heartbeat-time">{{ formatMachineTime(row.last_heartbeat) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div class="pagination-wrap" v-if="total > 0">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="total, prev, pager, next"
            @current-change="fetchList"
          />
        </div>
      </section>

      <section class="right-panel">
        <div v-if="!currentRow" class="empty-detail">
          <el-empty description="请选择左侧机器查看实时会话与运行信息" />
        </div>

        <template v-else>
          <div class="machine-info-card">
            <div class="machine-info-heading">
              <div class="machine-avatar" :class="`status-${currentRow.status}`">
                <el-icon><Monitor /></el-icon>
              </div>
              <div>
                <span class="panel-eyebrow">当前机器</span>
                <h2>{{ machineDisplayName(currentRow) }}</h2>
                <p>{{ currentRow.hostname || '未上报主机名' }} · {{ currentRow.ip_address || '未配置 IP' }}</p>
              </div>
              <div class="machine-info-tags">
                <el-tag :type="statusTagType(currentRow.status)" effect="dark">{{ statusLabel(currentRow.status) }}</el-tag>
                <el-tag :type="typeTagType(currentRow.type)">{{ typeLabel(currentRow.type) }}</el-tag>
              </div>
            </div>
            <div class="machine-meta-grid">
              <div><span>MAC 地址</span><strong class="session-mono">{{ currentRow.mac_address || '-' }}</strong></div>
              <div><span>操作系统</span><strong>{{ currentRow.os_info || '-' }}</strong></div>
              <div><span>Wireless HID</span><strong>{{ mkDeviceNameMap[currentRow.mk_device_id] || '未关联' }}</strong></div>
              <div><span>视频流设备</span><strong>{{ vsDeviceNameMap[currentRow.vs_device_id] || '未关联' }}</strong></div>
              <div><span>最后心跳</span><strong>{{ formatSessionTime(currentRow.last_heartbeat) }}</strong></div>
              <div><span>备注</span><strong>{{ currentRow.remark || '-' }}</strong></div>
            </div>
          </div>

          <div class="machine-detail-actions">
            <el-button size="small" @click="openMachineDialog(currentRow)">
              <el-icon><Edit /></el-icon>编辑机器
            </el-button>
            <el-button
              v-if="currentRow.type !== 'account'"
              size="small"
              type="success"
              plain
              @click="openGameAccountsDrawer(currentRow)"
            >关联游戏账号</el-button>
            <el-button
              v-if="currentRow.type !== 'game'"
              size="small"
              type="warning"
              plain
              @click="openAccountsDrawer(currentRow)"
            >关联平台账号</el-button>
            <el-popconfirm title="确认删除当前机器？" @confirm="handleDeleteMachine(currentRow.id)">
              <template #reference><el-button size="small" type="danger" link>删除机器</el-button></template>
            </el-popconfirm>
          </div>

          <div class="session-panel" v-loading="sessionLoading && !sessionInfo">
            <div v-if="sessionInfo" class="session-status-card" :class="{ 'is-connected': sessionInfo.connected }">
              <div class="session-status-main">
                <span class="session-status-dot" aria-hidden="true"></span>
                <div>
                  <div class="session-status-title">{{ sessionInfo.connected ? 'Worker 会话已连接' : '当前没有活动会话' }}</div>
                  <div class="session-status-subtitle">
                    {{ sessionInfo.connected ? '数据每 5 秒自动刷新' : 'Worker 重新连接后，此处会自动显示会话信息' }}
                  </div>
                </div>
              </div>
              <div class="session-status-actions">
                <el-tag effect="dark" size="small" :type="sessionSummaryType(sessionInfo)">
                  {{ sessionSummaryLabel(sessionInfo) }}
                </el-tag>
                <el-tag size="small" :type="sessionInfo.connected ? 'success' : 'info'">{{ roleLabel(sessionInfo.role) }}</el-tag>
                <el-button size="small" :loading="sessionLoading" @click="fetchMachineSession">立即刷新</el-button>
              </div>
            </div>

            <el-alert
              v-if="sessionInfo?.connected && !sessionInfo?.runtime"
              class="session-alert"
              type="info"
              :closable="false"
              show-icon
              title="会话已连接，Worker 尚未上报运行态"
              description="脚本刚启动时可能短暂出现，收到下一次心跳后会自动更新。"
            />

            <template v-if="sessionInfo">
              <template v-if="sessionInfo.runtime && isGameRuntime(sessionInfo)">
                <div class="session-section-title">实时运行态</div>
                <section class="runtime-board" aria-label="当前游戏运行态">
                  <div class="runtime-board-header">
                    <div>
                      <span class="runtime-board-kicker">CURRENT GAME CONTEXT</span>
                      <strong>当前游戏上下文</strong>
                    </div>
                    <span class="runtime-board-role">{{ roleLabel(sessionInfo.runtime.role || sessionInfo.role) }}</span>
                  </div>

                  <div class="runtime-context-grid">
                    <article class="runtime-context-item">
                      <el-icon><Trophy /></el-icon>
                      <div>
                        <span>游戏</span>
                        <strong>{{ runtimeGameName(sessionInfo.runtime.game_id) }}</strong>
                        <small>{{ runtimeIdHint('游戏', sessionInfo.runtime.game_id) }}</small>
                      </div>
                    </article>
                    <article class="runtime-context-item">
                      <el-icon><UserFilled /></el-icon>
                      <div>
                        <span>游戏账号</span>
                        <strong>{{ runtimeAccountName(sessionInfo.runtime.game_account_id) }}</strong>
                        <small>{{ runtimeIdHint('账号', sessionInfo.runtime.game_account_id) }}</small>
                      </div>
                    </article>
                    <article class="runtime-context-item">
                      <el-icon><MapLocation /></el-icon>
                      <div>
                        <span>大区</span>
                        <strong>{{ runtimeRegionName(sessionInfo.runtime.region_id) }}</strong>
                        <small>{{ runtimeIdHint('大区', sessionInfo.runtime.region_id) }}</small>
                      </div>
                    </article>
                    <article class="runtime-context-item">
                      <el-icon><Avatar /></el-icon>
                      <div>
                        <span>游戏角色</span>
                        <strong>{{ displayValue(sessionInfo.runtime.character_name) }}</strong>
                        <small>Worker 当前上报角色</small>
                      </div>
                    </article>
                  </div>

                  <div class="runtime-health-strip">
                    <div
                      v-for="item in runtimeHealthItems(sessionInfo.runtime)"
                      :key="item.field"
                      class="runtime-health-item"
                      :class="item.className"
                    >
                      <span class="runtime-health-dot" aria-hidden="true"></span>
                      <div>
                        <small>{{ item.label }}</small>
                        <strong>{{ item.value }}</strong>
                      </div>
                    </div>
                  </div>

                  <div class="runtime-assignment">
                    <span>当前交易指派</span>
                    <strong class="session-mono">{{ displayValue(sessionInfo.runtime.current_assignment_id) }}</strong>
                  </div>
                </section>
              </template>

              <template v-if="sessionInfo.active_tasks?.length">
                <div class="session-section-title">活动监控任务</div>
                <el-table :data="sessionInfo.active_tasks" border size="small" class="session-task-table">
                  <el-table-column prop="account_id" label="账号" width="70" />
                  <el-table-column prop="task_id" label="任务编号" min-width="130" show-overflow-tooltip />
                  <el-table-column prop="status" label="状态" width="80" />
                  <el-table-column label="启动时间" width="150">
                    <template #default="{ row }">{{ formatTaskStartTime(row.start_time) }}</template>
                  </el-table-column>
                  <el-table-column prop="message" label="说明" min-width="130" show-overflow-tooltip />
                </el-table>
              </template>

              <el-collapse class="connection-details">
                <el-collapse-item name="connection">
                  <template #title>
                    <span class="connection-details-title">连接详情</span>
                  </template>
                  <el-descriptions :column="1" border size="small" class="session-descriptions">
                    <el-descriptions-item label="会话编号"><span class="session-mono">{{ displayValue(sessionInfo.session_id) }}</span></el-descriptions-item>
                    <el-descriptions-item label="连接角色">{{ roleLabel(sessionInfo.role) }}</el-descriptions-item>
                    <el-descriptions-item label="远端地址"><span class="session-mono">{{ displayValue(sessionInfo.remote_address) }}</span></el-descriptions-item>
                    <el-descriptions-item label="连接时间">{{ formatSessionTime(sessionInfo.connected_at) }}</el-descriptions-item>
                    <el-descriptions-item label="最后心跳">{{ formatSessionTime(sessionInfo.last_heartbeat) }}</el-descriptions-item>
                    <el-descriptions-item label="数据库状态">{{ statusLabel(sessionInfo.persisted_status) }}</el-descriptions-item>
                  </el-descriptions>
                </el-collapse-item>
              </el-collapse>

              <p class="session-footnote">会话信息来自当前后端进程内存；后端重启后，需要等待 Worker 重新连接并上报心跳。</p>
            </template>
          </div>
        </template>
      </section>
    </div>

    <!-- 机器编辑弹窗 -->
    <el-dialog v-model="machineDialogVisible" :title="machineIsEdit ? '编辑机器' : '新增机器'" width="500px" destroy-on-close>
      <el-form :model="machineForm" label-width="90px" ref="machineFormRef" :rules="machineRules">
        <el-form-item label="MAC地址" prop="mac_address">
          <el-input v-model="machineForm.mac_address" placeholder="AA:BB:CC:DD:EE:FF" :disabled="machineIsEdit" />
        </el-form-item>
        <el-form-item label="别名">
          <el-input v-model="machineForm.name" placeholder="如：1号机器" />
        </el-form-item>
        <el-form-item label="IP地址">
          <el-input v-model="machineForm.ip_address" placeholder="192.168.1.100" />
        </el-form-item>
        <el-form-item label="主机名">
          <el-input v-model="machineForm.hostname" />
        </el-form-item>
        <el-form-item label="操作系统">
          <el-input v-model="machineForm.os_info" placeholder="如：Windows 11" />
        </el-form-item>
        <el-form-item label="鼠标键盘设备">
          <el-select v-model="machineForm.mk_device_id" placeholder="选择设备" clearable style="width:100%" @clear="machineForm.mk_device_id = -1">
            <el-option v-for="d in allMkDevices" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="视频流设备">
          <el-select v-model="machineForm.vs_device_id" placeholder="选择设备" clearable style="width:100%" @clear="machineForm.vs_device_id = -1">
            <el-option v-for="d in allVsDevices" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="machineForm.is_active" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="禁用" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="machineForm.remark" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="machineDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleMachineSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 关联游戏账号抽屉 -->
    <el-drawer v-model="gameAccountsDrawerVisible" :title="`关联游戏账号 - ${currentMachine?.name || currentMachine?.mac_address || ''}`" size="560px" destroy-on-close>
      <div class="games-toolbar">
        <el-select v-model="newGameAccountId" placeholder="选择游戏账号" style="width: 320px" filterable>
          <el-option v-for="a in allGameAccounts" :key="a.id" :label="`${gameNameMap[a.game_id] || ''} - ${a.account_name} (${a.nickname || '无昵称'})`" :value="a.id" />
        </el-select>
        <el-button type="primary" size="small" @click="handleAddGameAccount" :disabled="!newGameAccountId">添加</el-button>
      </div>
      <el-table :data="machineGameAccounts" border stripe size="small" row-key="id">
        <el-table-column label="游戏" min-width="100">
          <template #default="{ row }">{{ gameNameMap[row.game_id] || row.game_id }}</template>
        </el-table-column>
        <el-table-column label="账号" min-width="120">
          <template #default="{ row }">{{ row.account_name }}</template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="90" align="center" />
        <el-table-column prop="max_concurrent" label="最大并发" width="90" align="center" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="editGameConfig(row)">编辑</el-button>
            <el-popconfirm title="确认移除？" @confirm="handleRemoveGame(row.id)">
              <template #reference><el-button size="small" link type="danger">移除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 配置编辑弹窗 -->
      <el-dialog v-model="gameCfgVisible" title="编辑配置" width="380px" append-to-body destroy-on-close>
        <el-form :model="gameCfgForm" label-width="80px">
          <el-form-item label="优先级">
            <el-input-number v-model="gameCfgForm.priority" :min="0" :max="999" />
          </el-form-item>
          <el-form-item label="最大并发">
            <el-input-number v-model="gameCfgForm.max_concurrent" :min="1" :max="99" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="gameCfgVisible = false">取消</el-button>
          <el-button type="primary" @click="handleUpdateGameCfg">保存</el-button>
        </template>
      </el-dialog>
    </el-drawer>

    <!-- 关联账户抽屉 -->
    <el-drawer v-model="accountsDrawerVisible" :title="`关联账户 - ${currentMachine?.name || currentMachine?.mac_address || ''}`" size="550px" destroy-on-close>
      <div class="games-toolbar account-binding-toolbar">
        <el-select v-model="newAccountId" placeholder="选择账户" style="width: 410px" filterable>
          <el-option
            v-for="a in allAccounts"
            :key="a.id"
            :label="accountOptionLabel(a)"
            :value="a.id"
            :disabled="Boolean(accountBindingMap[a.id])"
          >
            <span>{{ accountBaseLabel(a) }}</span>
            <span v-if="accountBindingMap[a.id]" class="account-binding-owner">
              已关联：{{ bindingMachineLabel(accountBindingMap[a.id]) }}
            </span>
          </el-option>
        </el-select>
        <el-button type="primary" size="small" @click="handleAddAccount" :disabled="!newAccountId">添加</el-button>
      </div>
      <div class="account-binding-tip">已关联账户不可重复分配，灰色项右侧显示当前所属机器。</div>
      <el-table :data="machineAccounts" border stripe size="small" row-key="id">
        <el-table-column label="网站" min-width="100">
          <template #default="{ row }">{{ websiteNameMap[row.website_id] || row.website_id }}</template>
        </el-table-column>
        <el-table-column label="标签" min-width="80">
          <template #default="{ row }">{{ accountMap[row.account_id]?.label || '' }}</template>
        </el-table-column>
        <el-table-column label="用户名" min-width="100">
          <template #default="{ row }">{{ accountMap[row.account_id]?.username || '' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-popconfirm title="确认移除？" @confirm="handleRemoveAccount(row.id)">
              <template #reference><el-button size="small" link type="danger">移除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getMachines, getMachineSession, createMachine, updateMachine, deleteMachine,
  getMachineGames, addMachineGame, updateMachineGame, removeMachineGame,
  getMachineAccounts, getPlatformAccountBindings, addMachineAccount, removeMachineAccount,
  getAllGames, getAllRegions, getAllAccounts, getAllWebsites,
  getAllMkDevices, getAllVsDevices, getAllGameAccounts,
} from '../api'

const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const filterStatus = ref('')
const loading = ref(false)
const currentRow = ref(null)
const machineTableRef = ref(null)
const allGames = ref([])
const allRegions = ref([])
const allAccounts = ref([])
const allWebsitesData = ref([])
const allMkDevices = ref([])
const allVsDevices = ref([])
const allGameAccounts = ref([])
const websiteNameMap = computed(() => Object.fromEntries(allWebsitesData.value.map(w => [w.id, w.name])))
const accountMap = computed(() => Object.fromEntries(allAccounts.value.map(a => [a.id, a])))
const gameNameMap = computed(() => Object.fromEntries(allGames.value.map(g => [g.id, g.name])))
const regionMap = computed(() => Object.fromEntries(allRegions.value.map(r => [r.id, r])))
const mkDeviceNameMap = computed(() => Object.fromEntries(allMkDevices.value.map(d => [d.id, d.name])))
const vsDeviceNameMap = computed(() => Object.fromEntries(allVsDevices.value.map(d => [d.id, d.name])))
const gameAccountMap = computed(() => Object.fromEntries(allGameAccounts.value.map(a => [a.id, a])))

function statusLabel(s) { return { online: '在线', offline: '离线', busy: '忙碌', disabled: '禁用' }[s] || s }
function statusTagType(s) { return { online: 'success', offline: 'info', busy: 'warning', disabled: 'danger' }[s] || '' }
function typeLabel(t) { return { game: '游戏', account: '账户', both: '游戏+账户' }[t] || '未绑定' }
function typeTagType(t) { return { game: '', account: 'warning', both: 'success' }[t] || 'info' }

async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize, keyword: keyword.value }
    if (filterStatus.value) params.status = filterStatus.value
    const res = await getMachines(params)
    const selectedId = currentRow.value?.id
    list.value = res.items
    total.value = res.total
    const selected = list.value.find(row => row.id === selectedId)
      || list.value[0]
      || null
    await selectMachine(selected)
    await nextTick()
    machineTableRef.value?.setCurrentRow(selected)
  } finally { loading.value = false }
}
function handleSearch() { page.value = 1; fetchList() }

// ── Worker 实时会话 ──
const sessionMachine = ref(null)
const sessionInfo = ref(null)
const sessionLoading = ref(false)
let sessionRefreshTimer = null

function displayValue(value) { return value === null || value === undefined || value === '' ? '-' : value }
function formatSessionTime(value) { return value ? String(value).replace('T', ' ') : '-' }
function formatTaskStartTime(value) {
  const timestamp = Number(value)
  return Number.isFinite(timestamp) && timestamp > 0 ? new Date(timestamp * 1000).toLocaleString() : '-'
}
function roleLabel(role) {
  return { game_executor: '游戏执行器', trader: '游戏执行器', monitor: '订单监控' }[role] || role || '角色未上报'
}
function runtimeStatusLabel(field, value) {
  const labels = {
    client_status: { logged_in: '已登录', not_ready: '尚未就绪', unknown: '未知' },
    ui_health: { ready: '界面正常', unhealthy: '界面异常', recovering: '恢复中' },
    executor_status: { idle: '空闲', busy: '执行中', running: '执行中' },
  }
  return labels[field]?.[value] || displayValue(value)
}
function runtimeGameName(gameId) {
  if (!gameId) return '未上报'
  return gameNameMap.value[gameId] || '未找到对应游戏'
}
function runtimeAccountName(accountId) {
  if (!accountId) return '未上报'
  const account = gameAccountMap.value[accountId]
  if (!account) return '未找到对应账号'
  const primary = account.account_name || account.nickname || `账号 #${accountId}`
  return account.nickname && account.nickname !== primary
    ? `${primary} · ${account.nickname}`
    : primary
}
function runtimeRegionName(regionId) {
  if (!regionId) return '未上报'
  return regionMap.value[regionId]?.name || '未找到对应大区'
}
function runtimeIdHint(label, value) {
  return value ? `${label} ID #${value}` : 'Worker 尚未上报'
}
function runtimeHealthClass(field, value) {
  const healthy = (
    (field === 'client_status' && value === 'logged_in')
    || (field === 'ui_health' && value === 'ready')
    || (field === 'executor_status' && value === 'idle')
  )
  if (healthy) return 'is-healthy'
  if (field === 'ui_health' && value === 'unhealthy') return 'is-danger'
  if (value === 'busy' || value === 'running' || value === 'recovering') {
    return 'is-active'
  }
  return 'is-muted'
}
function runtimeHealthItems(runtime) {
  return [
    {
      field: 'client_status',
      label: '游戏客户端',
      value: runtimeStatusLabel('client_status', runtime.client_status),
      className: runtimeHealthClass('client_status', runtime.client_status),
    },
    {
      field: 'ui_health',
      label: '游戏界面',
      value: runtimeStatusLabel('ui_health', runtime.ui_health),
      className: runtimeHealthClass('ui_health', runtime.ui_health),
    },
    {
      field: 'executor_status',
      label: '交易执行器',
      value: runtimeStatusLabel('executor_status', runtime.executor_status),
      className: runtimeHealthClass('executor_status', runtime.executor_status),
    },
  ]
}
function isGameRuntime(info) {
  const role = info?.runtime?.role || info?.role
  return role === 'game_executor' || role === 'trader'
}
function sessionSummaryLabel(info) {
  if (!info?.connected) return '会话离线'
  const runtime = info.runtime
  if (!runtime) return '等待运行态'
  const role = runtime.role || info.role
  if (role === 'monitor') {
    const activeTasks = Array.isArray(info.active_tasks) ? info.active_tasks : []
    if (activeTasks.some(task => task?.status === 'running')) return '监控运行中'
    if (activeTasks.some(task => task?.status === 'stopping')) return '任务停止中'
    return '监控待命'
  }
  if (runtime.ui_health === 'unhealthy') return '界面异常'
  if (runtime.ui_health === 'recovering') return '正在恢复'
  if (runtime.executor_status === 'busy' || runtime.executor_status === 'running') {
    return '交易执行中'
  }
  if (runtime.client_status === 'logged_in' && runtime.ui_health === 'ready') {
    return '已就绪'
  }
  return '尚未就绪'
}
function sessionSummaryType(info) {
  const label = sessionSummaryLabel(info)
  if (label === '界面异常') return 'danger'
  if (label === '正在恢复' || label === '交易执行中' || label === '尚未就绪' || label === '任务停止中') {
    return 'warning'
  }
  if (label === '已就绪' || label === '监控运行中') return 'success'
  return 'info'
}
function stopSessionRefresh() {
  if (sessionRefreshTimer !== null) {
    window.clearInterval(sessionRefreshTimer)
    sessionRefreshTimer = null
  }
}
async function fetchMachineSession() {
  const machineId = sessionMachine.value?.id
  if (!machineId || sessionLoading.value) return
  sessionLoading.value = true
  try {
    const result = await getMachineSession(machineId)
    if (sessionMachine.value?.id === machineId) sessionInfo.value = result
  } catch (error) {
    ElMessage.error(error.message || '会话信息加载失败')
  } finally {
    sessionLoading.value = false
  }
}
async function selectMachine(machine) {
  currentRow.value = machine || null
  if (!machine) {
    stopSessionRefresh()
    sessionMachine.value = null
    sessionInfo.value = null
    return
  }
  if (sessionMachine.value?.id === machine.id) {
    sessionMachine.value = machine
    return
  }
  stopSessionRefresh()
  sessionMachine.value = machine
  sessionInfo.value = null
  await fetchMachineSession()
  sessionRefreshTimer = window.setInterval(fetchMachineSession, 5000)
}
function machineDisplayName(machine) {
  return machine?.name || machine?.hostname || machine?.mac_address || '未命名机器'
}
function formatMachineTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(5, 16)
}

// ── 机器编辑 ──
const machineDialogVisible = ref(false)
const machineIsEdit = ref(false)
const editId = ref(null)
const submitting = ref(false)
const machineFormRef = ref(null)
const machineRules = { mac_address: [{ required: true, message: '请输入MAC地址', trigger: 'blur' }] }
const defaultMachineForm = () => ({ mac_address: '', name: '', ip_address: '', hostname: '', os_info: '', mk_device_id: null, vs_device_id: null, is_active: 1, remark: '' })
const machineForm = reactive(defaultMachineForm())

function openMachineDialog(row = null) {
  machineIsEdit.value = !!row; editId.value = row?.id ?? null
  Object.assign(machineForm, row ? { ...row } : defaultMachineForm())
  machineDialogVisible.value = true
}
async function handleMachineSubmit() {
  await machineFormRef.value?.validate(); submitting.value = true
  try {
    const data = { ...machineForm }
    // 空字符串转为 null，避免后端校验问题
    if (!data.name) data.name = null
    if (!data.ip_address) data.ip_address = null
    if (!data.hostname) data.hostname = null
    if (!data.os_info) data.os_info = null
    if (!data.remark) data.remark = null
    if (machineIsEdit.value) { await updateMachine(editId.value, data); ElMessage.success('更新成功') }
    else { await createMachine(data); ElMessage.success('添加成功') }
    machineDialogVisible.value = false; fetchList()
  } catch (e) { ElMessage.error(e.message) } finally { submitting.value = false }
}
async function handleDeleteMachine(id) { try { await deleteMachine(id); ElMessage.success('已删除'); fetchList() } catch (e) { ElMessage.error(e.message) } }

// ── 关联游戏账号 ──
const gameAccountsDrawerVisible = ref(false)
const currentMachine = ref(null)
const machineGameAccounts = ref([])
const newGameAccountId = ref(null)

async function openGameAccountsDrawer(machine) {
  currentMachine.value = machine; gameAccountsDrawerVisible.value = true; newGameAccountId.value = null; await fetchMachineGameAccounts()
}
async function fetchMachineGameAccounts() {
  if (!currentMachine.value) return
  const mgs = await getMachineGames(currentMachine.value.id)
  // 机器关联只保存账号，账号支持的大区由 game_account_regions 统一维护。
  machineGameAccounts.value = mgs.map(mg => {
    const ga = gameAccountMap.value[mg.game_account_id] || {}
    return { ...mg, game_id: ga.game_id, account_name: ga.account_name }
  })
}
async function handleAddGameAccount() {
  try {
    await addMachineGame(currentMachine.value.id, { game_account_id: newGameAccountId.value })
    ElMessage.success('已添加'); newGameAccountId.value = null; fetchMachineGameAccounts()
  } catch (e) { ElMessage.error(e.message) }
}
async function handleRemoveGame(mgId) { try { await removeMachineGame(mgId); ElMessage.success('已移除'); fetchMachineGameAccounts() } catch (e) { ElMessage.error(e.message) } }

// 游戏配置编辑
const gameCfgVisible = ref(false)
const gameCfgId = ref(null)
const gameCfgForm = reactive({ priority: 0, max_concurrent: 1 })
function editGameConfig(row) { gameCfgId.value = row.id; Object.assign(gameCfgForm, { priority: row.priority, max_concurrent: row.max_concurrent }); gameCfgVisible.value = true }
async function handleUpdateGameCfg() {
  try { await updateMachineGame(gameCfgId.value, { ...gameCfgForm }); ElMessage.success('已更新'); gameCfgVisible.value = false; fetchMachineGameAccounts() }
  catch (e) { ElMessage.error(e.message) }
}

// ── 关联账户 ──
const accountsDrawerVisible = ref(false)
const machineAccounts = ref([])
const accountBindings = ref([])
const newAccountId = ref(null)
const accountBindingMap = computed(() => Object.fromEntries(
  accountBindings.value.map(binding => [binding.account_id, binding]),
))

function accountBaseLabel(account) {
  return `${websiteNameMap.value[account.website_id] || ''} - ${account.label} (${account.username})`
}
function bindingMachineLabel(binding) {
  return binding.machine_name
    || binding.machine_hostname
    || binding.machine_mac_address
    || `机器 #${binding.machine_id}`
}
function accountOptionLabel(account) {
  const binding = accountBindingMap.value[account.id]
  return binding
    ? `${accountBaseLabel(account)}（已关联：${bindingMachineLabel(binding)}）`
    : accountBaseLabel(account)
}

async function openAccountsDrawer(machine) {
  currentMachine.value = machine
  newAccountId.value = null
  accountsDrawerVisible.value = true
  await Promise.all([fetchMachineAccounts(), fetchAccountBindings()])
}
async function fetchAccountBindings() {
  accountBindings.value = await getPlatformAccountBindings()
}
async function fetchMachineAccounts() {
  if (!currentMachine.value) return
  const mas = await getMachineAccounts(currentMachine.value.id)
  // 将 account 信息合并到每条记录中，方便表格展示
  machineAccounts.value = mas.map(ma => ({
    ...ma,
    website_id: accountMap.value[ma.account_id]?.website_id || null,
  }))
}
async function handleAddAccount() {
  try {
    await addMachineAccount(currentMachine.value.id, { account_id: newAccountId.value })
    ElMessage.success('已添加')
    newAccountId.value = null
    await Promise.all([fetchMachineAccounts(), fetchAccountBindings()])
  } catch (e) { ElMessage.error(e.message) }
}
async function handleRemoveAccount(maId) {
  try {
    await removeMachineAccount(maId)
    ElMessage.success('已移除')
    await Promise.all([fetchMachineAccounts(), fetchAccountBindings()])
  }
  catch (e) { ElMessage.error(e.message) }
}

onMounted(async () => {
  allGames.value = await getAllGames()
  allRegions.value = await getAllRegions()
  allAccounts.value = await getAllAccounts()
  allWebsitesData.value = await getAllWebsites()
  allMkDevices.value = await getAllMkDevices()
  allVsDevices.value = await getAllVsDevices()
  const gaRes = await getAllGameAccounts()
  allGameAccounts.value = gaRes.items || []
  fetchList()
})

onBeforeUnmount(stopSessionRefresh)
</script>

<style scoped>
.page-container {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  flex-shrink: 0;
  gap: 10px;
  margin-bottom: 14px;
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(31, 45, 61, .04);
}
.toolbar .el-button { margin-left: auto; }
.account-binding-toolbar {
  align-items: center;
}
.account-binding-owner {
  float: right;
  margin-left: 18px;
  color: #909399;
  font-size: 12px;
}
.account-binding-tip {
  margin: -4px 0 12px;
  color: #909399;
  font-size: 12px;
}
.split-layout {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(390px, .86fr) minmax(540px, 1.24fr);
  gap: 14px;
  min-height: 0;
  overflow: hidden;
}
.left-panel {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(31, 45, 61, .04);
}
.panel-heading {
  min-height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid #ebeef5;
}
.panel-heading > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.panel-heading strong {
  color: #303133;
  font-size: 15px;
  line-height: 20px;
}
.panel-eyebrow {
  color: #909399;
  font-size: 10px;
  line-height: 16px;
  letter-spacing: .09em;
}
.result-count {
  flex-shrink: 0;
  padding: 3px 9px;
  border-radius: 12px;
  background: #ecf5ff;
  color: #409eff;
  font-size: 12px;
  line-height: 18px;
}
.table-shell {
  flex: 1;
  min-height: 0;
}
.left-panel :deep(.el-table) {
  border-right: 0;
  border-left: 0;
}
.left-panel :deep(.el-table__header th.el-table__cell) {
  background: #f7f9fc;
  color: #606266;
}
.left-panel :deep(.el-table__body tr.current-row > td.el-table__cell) {
  background: #eaf4ff;
}
.machine-list-identity {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
  padding: 3px 0;
}
.machine-list-identity strong,
.machine-list-identity span,
.machine-list-identity small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.machine-list-identity strong { color: #263445; font-size: 13px; }
.machine-list-identity span { color: #687483; font-size: 11px; }
.machine-list-identity small {
  color: #9ba4ae;
  font: 10px/1.4 Consolas, "SFMono-Regular", monospace;
}
.machine-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #727c87;
  font-size: 11px;
  white-space: nowrap;
}
.machine-status i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #a7afb8;
}
.machine-status.status-online { color: #267a4a; }
.machine-status.status-online i {
  background: #35a265;
  box-shadow: 0 0 0 3px rgba(53, 162, 101, .12);
}
.machine-status.status-busy { color: #a26918; }
.machine-status.status-busy i { background: #d89225; }
.machine-status.status-disabled { color: #b74242; }
.machine-status.status-disabled i { background: #d45757; }
.heartbeat-time {
  color: #6e7985;
  font: 10px/1.4 Consolas, "SFMono-Regular", monospace;
  white-space: nowrap;
}
.pagination-wrap {
  display: flex;
  flex-shrink: 0;
  justify-content: center;
  padding: 10px 8px;
  border-top: 1px solid #ebeef5;
}
.right-panel {
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(31, 45, 61, .04);
}
.empty-detail {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.machine-info-card {
  overflow: hidden;
  border: 1px solid #d9e6f3;
  border-left: 4px solid #409eff;
  border-radius: 8px;
  background: linear-gradient(105deg, #f2f8ff 0%, #f9fcff 66%, #fff 100%);
}
.machine-info-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px 12px;
}
.machine-avatar {
  width: 42px;
  height: 42px;
  display: flex;
  flex: 0 0 42px;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: #dfeaf5;
  color: #5d7288;
  font-size: 22px;
}
.machine-avatar.status-online {
  background: #dff3e7;
  color: #278154;
}
.machine-avatar.status-busy {
  background: #fff0d7;
  color: #b16e14;
}
.machine-info-heading > div:nth-child(2) { min-width: 0; }
.machine-info-heading h2 {
  overflow: hidden;
  margin: 1px 0 3px;
  color: #1e2d3e;
  font-size: 18px;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.machine-info-heading p {
  overflow: hidden;
  margin: 0;
  color: #718092;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.machine-info-tags {
  display: flex;
  flex-shrink: 0;
  gap: 6px;
  margin-left: auto;
}
.machine-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-top: 1px solid #e0eaf3;
  background: rgba(255, 255, 255, .66);
}
.machine-meta-grid > div {
  min-width: 0;
  padding: 10px 13px;
  border-right: 1px solid #e6edf4;
  border-bottom: 1px solid #e6edf4;
}
.machine-meta-grid > div:nth-child(3n) { border-right: 0; }
.machine-meta-grid > div:nth-last-child(-n+3) { border-bottom: 0; }
.machine-meta-grid span,
.machine-meta-grid strong { display: block; }
.machine-meta-grid span { color: #8c97a3; font-size: 10px; }
.machine-meta-grid strong {
  overflow: hidden;
  margin-top: 4px;
  color: #3b4856;
  font-size: 12px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.machine-detail-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
  padding: 10px 12px;
  border: 1px solid #e4e8ed;
  border-radius: 7px;
  background: #fafbfc;
}
.machine-detail-actions .el-button { margin-left: 0; }
.machine-detail-actions .el-popconfirm { margin-left: auto; }
.games-toolbar { display: flex; gap: 12px; margin-bottom: 12px; align-items: center; }
.session-panel { min-height: 240px; }
.session-status-card { display: flex; justify-content: space-between; align-items: center; gap: 18px; padding: 18px; border: 1px solid #dcdfe6; border-left: 4px solid #909399; border-radius: 8px; background: #f7f8fa; }
.session-status-card.is-connected { border-color: #b8e3cc; border-left-color: #2f9e62; background: #f2fbf6; }
.session-status-main, .session-status-actions { display: flex; align-items: center; gap: 12px; }
.session-status-actions { flex-shrink: 0; }
.session-status-dot { width: 11px; height: 11px; border-radius: 50%; background: #909399; box-shadow: 0 0 0 5px rgba(144, 147, 153, .12); }
.is-connected .session-status-dot { background: #2f9e62; box-shadow: 0 0 0 5px rgba(47, 158, 98, .13); }
.session-status-title { color: #303133; font-size: 16px; font-weight: 650; }
.session-status-subtitle { margin-top: 4px; color: #73767a; font-size: 12px; }
.session-alert { margin-top: 16px; }
.session-section-title { margin: 24px 0 10px; color: #303133; font-size: 14px; font-weight: 650; letter-spacing: .02em; }
.session-descriptions :deep(.el-descriptions__label) { width: 118px; color: #606266; }
.session-mono { font-family: Consolas, "SFMono-Regular", monospace; font-size: 12px; }
.runtime-board {
  overflow: hidden;
  border: 1px solid #ccd8e5;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 7px 24px rgba(25, 53, 82, .08);
}
.runtime-board-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid #dce5ee;
  background: #0d2d4e;
  color: #fff;
}
.runtime-board-header > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.runtime-board-kicker {
  color: #7fc2f0;
  font: 700 10px/1.2 Consolas, "SFMono-Regular", monospace;
  letter-spacing: .14em;
}
.runtime-board-header strong { font-size: 15px; }
.runtime-board-role {
  padding: 4px 8px;
  border: 1px solid rgba(255, 255, 255, .25);
  border-radius: 4px;
  color: #dbe9f5;
  font-size: 11px;
}
.runtime-context-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.runtime-context-item {
  display: flex;
  min-width: 0;
  gap: 12px;
  padding: 16px;
  border-right: 1px solid #e6ebf0;
  border-bottom: 1px solid #e6ebf0;
}
.runtime-context-item:nth-child(2n) { border-right: 0; }
.runtime-context-item:nth-last-child(-n+2) { border-bottom: 0; }
.runtime-context-item > .el-icon {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border-radius: 8px;
  background: #eaf3fb;
  color: #276b9e;
  font-size: 18px;
}
.runtime-context-item > div { min-width: 0; }
.runtime-context-item span,
.runtime-context-item small { display: block; }
.runtime-context-item span { color: #7d8792; font-size: 11px; }
.runtime-context-item strong {
  display: block;
  overflow: hidden;
  margin: 4px 0;
  color: #1e2c3b;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.runtime-context-item small {
  color: #a0a8b1;
  font: 10px/1.3 Consolas, "SFMono-Regular", monospace;
}
.runtime-health-strip {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-top: 1px solid #dce5ee;
  background: #f7f9fb;
}
.runtime-health-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 12px 14px;
  border-right: 1px solid #e1e7ed;
}
.runtime-health-item:last-child { border-right: 0; }
.runtime-health-dot {
  width: 9px;
  height: 9px;
  flex: 0 0 9px;
  border-radius: 50%;
  background: #9aa3ad;
  box-shadow: 0 0 0 4px rgba(154, 163, 173, .12);
}
.runtime-health-item small,
.runtime-health-item strong { display: block; }
.runtime-health-item small { color: #8b949e; font-size: 10px; }
.runtime-health-item strong { margin-top: 2px; color: #3c4652; font-size: 12px; }
.runtime-health-item.is-healthy .runtime-health-dot {
  background: #2f9e62;
  box-shadow: 0 0 0 4px rgba(47, 158, 98, .13);
}
.runtime-health-item.is-active .runtime-health-dot {
  background: #d28a1d;
  box-shadow: 0 0 0 4px rgba(210, 138, 29, .13);
}
.runtime-health-item.is-danger .runtime-health-dot {
  background: #d64d4d;
  box-shadow: 0 0 0 4px rgba(214, 77, 77, .13);
}
.runtime-assignment {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 11px 15px;
  border-top: 1px solid #e2e8ee;
  color: #737e89;
  font-size: 11px;
}
.runtime-assignment strong {
  overflow: hidden;
  color: #344455;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.session-task-table { width: 100%; }
.connection-details {
  margin-top: 18px;
  border-top: 1px solid #e4e9ee;
  border-bottom: 1px solid #e4e9ee;
}
.connection-details-title {
  color: #526171;
  font-size: 13px;
  font-weight: 650;
}
.session-footnote { margin: 18px 2px 0; color: #909399; font-size: 12px; line-height: 1.6; }
@media (max-width: 1180px) {
  .page-container {
    height: auto;
    min-height: 100%;
  }
  .split-layout {
    display: flex;
    flex-direction: column;
    overflow: visible;
  }
  .left-panel {
    height: 470px;
    flex: none;
  }
  .right-panel {
    min-height: 600px;
    flex: none;
    overflow: visible;
  }
}
@media (max-width: 760px) {
  .toolbar { align-items: stretch; }
  .toolbar :deep(.el-input),
  .toolbar :deep(.el-select) {
    width: 100% !important;
  }
  .toolbar .el-button {
    width: 100%;
    margin-left: 0;
  }
  .right-panel { padding: 12px; }
  .machine-info-heading {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .machine-info-tags {
    width: 100%;
    margin-left: 54px;
  }
  .machine-meta-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .machine-meta-grid > div:nth-child(3n) { border-right: 1px solid #e6edf4; }
  .machine-meta-grid > div:nth-child(2n) { border-right: 0; }
  .machine-meta-grid > div:nth-last-child(-n+3) { border-bottom: 1px solid #e6edf4; }
  .machine-meta-grid > div:nth-last-child(-n+2) { border-bottom: 0; }
  .session-status-card { align-items: flex-start; flex-direction: column; }
  .session-status-actions { width: 100%; flex-wrap: wrap; }
  .runtime-context-grid { grid-template-columns: 1fr; }
  .runtime-context-item { border-right: 0; }
  .runtime-context-item:nth-last-child(-n+2) { border-bottom: 1px solid #e6ebf0; }
  .runtime-context-item:last-child { border-bottom: 0; }
  .runtime-health-strip { grid-template-columns: 1fr; }
  .runtime-health-item { border-right: 0; border-bottom: 1px solid #e1e7ed; }
  .runtime-health-item:last-child { border-bottom: 0; }
}
</style>
