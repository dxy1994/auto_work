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

    <el-table :data="list" border stripe v-loading="loading" highlight-current-row @current-change="onCurrentChange" row-key="id">
      <el-table-column prop="name" label="别名" width="120" />
      <el-table-column prop="mac_address" label="MAC地址" width="160" />
      <el-table-column prop="ip_address" label="IP地址" width="140" />
      <el-table-column prop="hostname" label="主机名" width="130" />
      <el-table-column label="类型" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="typeTagType(row.type)" size="small">{{ typeLabel(row.type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="鼠标键盘设备" width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ mkDeviceNameMap[row.mk_device_id] || '-' }}</template>
      </el-table-column>
      <el-table-column label="视频流设备" width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ vsDeviceNameMap[row.vs_device_id] || '-' }}</template>
      </el-table-column>
      <el-table-column prop="os_info" label="操作系统" width="120" show-overflow-tooltip />
      <el-table-column prop="last_heartbeat" label="最后心跳" width="170" />
      <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip />
      <el-table-column label="操作" width="380" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openMachineDialog(row)">编辑</el-button>
          <el-button v-if="row.type !== 'account'" size="small" type="success" @click="openGameAccountsDrawer(row)">关联账号</el-button>
          <el-button v-if="row.type !== 'game'" size="small" type="warning" @click="openAccountsDrawer(row)">关联商户</el-button>
          <el-popconfirm title="确认删除？" @confirm="handleDeleteMachine(row.id)">
            <template #reference><el-button size="small" type="danger">删除</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap" v-if="total > pageSize">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="fetchList" />
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
    <el-drawer v-model="gameAccountsDrawerVisible" :title="`关联游戏账号 - ${currentMachine?.name || currentMachine?.mac_address || ''}`" size="650px" destroy-on-close>
      <div class="games-toolbar">
        <el-select v-model="newGameAccountId" placeholder="选择游戏账号" style="width: 240px" filterable @change="onGameAccountChanged">
          <el-option v-for="a in allGameAccounts" :key="a.id" :label="`${gameNameMap[a.game_id] || ''} - ${a.account_name} (${a.nickname || '无昵称'})`" :value="a.id" />
        </el-select>
        <el-select v-model="newRegionId" placeholder="选择大区" style="width: 180px" filterable :disabled="!newGameAccountId">
          <el-option v-for="rid in availableRegions" :key="rid" :label="regionNameMap[rid] || rid" :value="rid" />
        </el-select>
        <el-button type="primary" size="small" @click="handleAddGameAccount" :disabled="!newGameAccountId">添加</el-button>
      </div>
      <el-table :data="machineGameAccounts" border stripe size="small" highlight-current-row @current-change="onCurrentChange" row-key="id">
        <el-table-column label="游戏" min-width="100">
          <template #default="{ row }">{{ gameNameMap[row.game_id] || row.game_id }}</template>
        </el-table-column>
        <el-table-column label="大区" min-width="100">
          <template #default="{ row }">{{ regionNameMap[row.region_id] || row.region_id }}</template>
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
      <div class="games-toolbar">
        <el-select v-model="newAccountId" placeholder="选择账户" style="width: 280px" filterable>
          <el-option v-for="a in allAccounts" :key="a.id" :label="`${websiteNameMap[a.website_id] || ''} - ${a.label} (${a.username})`" :value="a.id" />
        </el-select>
        <el-button type="primary" size="small" @click="handleAddAccount" :disabled="!newAccountId">添加</el-button>
      </div>
      <el-table :data="machineAccounts" border stripe size="small" highlight-current-row @current-change="onCurrentChange" row-key="id">
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
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getMachines, createMachine, updateMachine, deleteMachine,
  getMachineGames, addMachineGame, updateMachineGame, removeMachineGame,
  getMachineAccounts, addMachineAccount, removeMachineAccount,
  getAllGames, getAllAccounts, getAllWebsites,
  getAllRegions, getAllMkDevices, getAllVsDevices, getAllGameAccounts,
} from '../api'

const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const filterStatus = ref('')
const loading = ref(false)
const currentRow = ref(null)
function onCurrentChange(row) { currentRow.value = row }
const allGames = ref([])
const allAccounts = ref([])
const allWebsitesData = ref([])
const allRegions = ref([])
const allMkDevices = ref([])
const allVsDevices = ref([])
const allGameAccounts = ref([])
const websiteNameMap = computed(() => Object.fromEntries(allWebsitesData.value.map(w => [w.id, w.name])))
const accountMap = computed(() => Object.fromEntries(allAccounts.value.map(a => [a.id, a])))
const gameNameMap = computed(() => Object.fromEntries(allGames.value.map(g => [g.id, g.name])))
const regionNameMap = computed(() => Object.fromEntries(allRegions.value.map(r => [r.id, r.name])))
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
    list.value = res.items; total.value = res.total
  } finally { loading.value = false }
}
function handleSearch() { page.value = 1; fetchList() }

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
const newRegionId = ref(null)
const availableRegions = ref([])

function onGameAccountChanged(gaId) {
  newRegionId.value = null
  if (!gaId) { availableRegions.value = []; return }
  const ga = allGameAccounts.value.find(a => a.id === gaId)
  availableRegions.value = ga?.region_ids || (ga?.region_id ? [ga.region_id] : [])
}

async function openGameAccountsDrawer(machine) {
  currentMachine.value = machine; gameAccountsDrawerVisible.value = true; newGameAccountId.value = null; newRegionId.value = null; availableRegions.value = []; await fetchMachineGameAccounts()
}
async function fetchMachineGameAccounts() {
  if (!currentMachine.value) return
  const mgs = await getMachineGames(currentMachine.value.id)
  // 合并 game_account 信息，优先使用 machine_games 自身的 region_id
  machineGameAccounts.value = mgs.map(mg => {
    const ga = gameAccountMap.value[mg.game_account_id] || {}
    return { ...mg, game_id: ga.game_id, region_id: mg.region_id || ga.region_id, account_name: ga.account_name }
  })
}
async function handleAddGameAccount() {
  try {
    await addMachineGame(currentMachine.value.id, { game_account_id: newGameAccountId.value, region_id: newRegionId.value || null })
    ElMessage.success('已添加'); newGameAccountId.value = null; newRegionId.value = null; fetchMachineGameAccounts()
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
const newAccountId = ref(null)

async function openAccountsDrawer(machine) {
  currentMachine.value = machine; accountsDrawerVisible.value = true; await fetchMachineAccounts()
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
    ElMessage.success('已添加'); newAccountId.value = null; fetchMachineAccounts()
  } catch (e) { ElMessage.error(e.message) }
}
async function handleRemoveAccount(maId) {
  try { await removeMachineAccount(maId); ElMessage.success('已移除'); fetchMachineAccounts() }
  catch (e) { ElMessage.error(e.message) }
}

onMounted(async () => {
  allGames.value = await getAllGames()
  allAccounts.value = await getAllAccounts()
  allWebsitesData.value = await getAllWebsites()
  allRegions.value = await getAllRegions()
  allMkDevices.value = await getAllMkDevices()
  allVsDevices.value = await getAllVsDevices()
  const gaRes = await getAllGameAccounts()
  allGameAccounts.value = gaRes.items || []
  fetchList()
})
</script>

<style scoped>
.page-container { padding: 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
.toolbar .el-button { margin-left: auto; }
.pagination-wrap { display: flex; justify-content: center; margin-top: 20px; }
.games-toolbar { display: flex; gap: 12px; margin-bottom: 12px; align-items: center; }
</style>
