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

    <el-table :data="list" border stripe v-loading="loading">
      <el-table-column prop="name" label="别名" width="120" />
      <el-table-column prop="mac_address" label="MAC地址" width="160" />
      <el-table-column prop="ip_address" label="IP地址" width="140" />
      <el-table-column prop="hostname" label="主机名" width="130" />
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_heartbeat" label="最后心跳" width="170" />
      <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip />
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openMachineDialog(row)">编辑</el-button>
          <el-button size="small" type="success" @click="openGamesDrawer(row)">关联游戏</el-button>
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
        <el-form-item label="备注">
          <el-input v-model="machineForm.remark" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="machineDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleMachineSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 关联游戏抽屉 -->
    <el-drawer v-model="gamesDrawerVisible" :title="`关联游戏 - ${currentMachine?.name || currentMachine?.mac_address || ''}`" size="550px" destroy-on-close>
      <div class="games-toolbar">
        <el-select v-model="newGameId" placeholder="选择游戏" style="width: 200px">
          <el-option v-for="g in allGames" :key="g.id" :label="g.name" :value="g.id" />
        </el-select>
        <el-button type="primary" size="small" @click="handleAddGame" :disabled="!newGameId">添加</el-button>
      </div>
      <el-table :data="machineGames" border stripe size="small">
        <el-table-column label="游戏" min-width="120">
          <template #default="{ row }">{{ gameNameMap[row.game_id] || row.game_id }}</template>
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

      <!-- 游戏配置编辑弹窗 -->
      <el-dialog v-model="gameCfgVisible" title="编辑游戏配置" width="380px" append-to-body destroy-on-close>
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getMachines, createMachine, updateMachine, deleteMachine,
  getMachineGames, addMachineGame, updateMachineGame, removeMachineGame,
  getAllGames,
} from '../api'

const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const filterStatus = ref('')
const loading = ref(false)
const allGames = ref([])
const gameNameMap = computed(() => Object.fromEntries(allGames.value.map(g => [g.id, g.name])))

function statusLabel(s) { return { online: '在线', offline: '离线', busy: '忙碌', disabled: '禁用' }[s] || s }
function statusTagType(s) { return { online: 'success', offline: 'info', busy: 'warning', disabled: 'danger' }[s] || '' }

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
const defaultMachineForm = () => ({ mac_address: '', name: '', ip_address: '', hostname: '', os_info: '', remark: '' })
const machineForm = reactive(defaultMachineForm())

function openMachineDialog(row = null) {
  machineIsEdit.value = !!row; editId.value = row?.id ?? null
  Object.assign(machineForm, row ? { ...row } : defaultMachineForm())
  machineDialogVisible.value = true
}
async function handleMachineSubmit() {
  await machineFormRef.value?.validate(); submitting.value = true
  try {
    if (machineIsEdit.value) { await updateMachine(editId.value, { ...machineForm }); ElMessage.success('更新成功') }
    else { await createMachine({ ...machineForm }); ElMessage.success('添加成功') }
    machineDialogVisible.value = false; fetchList()
  } catch (e) { ElMessage.error(e.message) } finally { submitting.value = false }
}
async function handleDeleteMachine(id) { try { await deleteMachine(id); ElMessage.success('已删除'); fetchList() } catch (e) { ElMessage.error(e.message) } }

// ── 关联游戏 ──
const gamesDrawerVisible = ref(false)
const currentMachine = ref(null)
const machineGames = ref([])
const newGameId = ref(null)

async function openGamesDrawer(machine) {
  currentMachine.value = machine; gamesDrawerVisible.value = true; await fetchMachineGames()
}
async function fetchMachineGames() { if (!currentMachine.value) return; machineGames.value = await getMachineGames(currentMachine.value.id) }
async function handleAddGame() {
  try { await addMachineGame(currentMachine.value.id, { game_id: newGameId.value }); ElMessage.success('已添加'); newGameId.value = null; fetchMachineGames() }
  catch (e) { ElMessage.error(e.message) }
}
async function handleRemoveGame(mgId) { try { await removeMachineGame(mgId); ElMessage.success('已移除'); fetchMachineGames() } catch (e) { ElMessage.error(e.message) } }

// 游戏配置编辑
const gameCfgVisible = ref(false)
const gameCfgId = ref(null)
const gameCfgForm = reactive({ priority: 0, max_concurrent: 1 })
function editGameConfig(row) { gameCfgId.value = row.id; Object.assign(gameCfgForm, { priority: row.priority, max_concurrent: row.max_concurrent }); gameCfgVisible.value = true }
async function handleUpdateGameCfg() {
  try { await updateMachineGame(gameCfgId.value, { ...gameCfgForm }); ElMessage.success('已更新'); gameCfgVisible.value = false; fetchMachineGames() }
  catch (e) { ElMessage.error(e.message) }
}

onMounted(async () => { allGames.value = await getAllGames(); fetchList() })
</script>

<style scoped>
.page-container { padding: 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
.toolbar .el-button { margin-left: auto; }
.pagination-wrap { display: flex; justify-content: center; margin-top: 20px; }
.games-toolbar { display: flex; gap: 12px; margin-bottom: 12px; align-items: center; }
</style>
