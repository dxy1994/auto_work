<template>
  <div class="page-container">
    <div class="toolbar">
      <el-select v-model="filterGameId" placeholder="选择游戏" clearable style="width: 160px" @change="handleSearch">
        <el-option v-for="g in gameList" :key="g.id" :label="g.name" :value="g.id" />
      </el-select>
      <el-select v-model="filterStatus" placeholder="全部状态" clearable style="width: 120px" @change="handleSearch">
        <el-option label="待分配" value="pending" />
        <el-option label="已分配" value="assigned" />
        <el-option label="处理中" value="processing" />
        <el-option label="已完成" value="completed" />
        <el-option label="已取消" value="cancelled" />
      </el-select>
      <el-input v-model="keyword" placeholder="搜索订单号/客户..." clearable style="width: 220px" @input="handleSearch">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" @click="openCreateDialog()">
        <el-icon><Plus /></el-icon> 新建订单
      </el-button>
    </div>

    <el-table :data="list" border stripe v-loading="loading">
      <el-table-column prop="order_no" label="订单号" width="200" />
      <el-table-column label="游戏" width="110">
        <template #default="{ row }">{{ gameNameMap[row.game_id] || row.game_id }}</template>
      </el-table-column>
      <el-table-column label="大区" width="110">
        <template #default="{ row }">{{ regionNameMap[row.region_id] || row.region_id }}</template>
      </el-table-column>
      <el-table-column prop="customer_name" label="客户" width="100" />
      <el-table-column prop="total_amount" label="总金额" width="100" align="right">
        <template #default="{ row }">{{ Number(row.total_amount || 0).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="orderStatusType(row.status)" size="small">{{ orderStatusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="分配机器" width="140">
        <template #default="{ row }">{{ machineNameMap[row.assigned_machine_id] || '-' }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="openDetailDrawer(row)">明细</el-button>
          <el-button size="small" link type="primary" @click="openEditDialog(row)">编辑</el-button>
          <el-button size="small" link type="success" v-if="row.status === 'pending'" @click="openAssignDialog(row)">分配</el-button>
          <el-popconfirm title="确认删除？" @confirm="handleDeleteOrder(row.id)" v-if="row.status === 'pending' || row.status === 'cancelled'">
            <template #reference><el-button size="small" link type="danger">删除</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap" v-if="total > pageSize">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="fetchList" />
    </div>

    <!-- 新建订单弹窗（主子表联动） -->
    <el-dialog v-model="createDialogVisible" title="新建订单" width="750px" destroy-on-close>
      <el-form :model="createForm" label-width="90px" ref="createFormRef" :rules="createRules">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="游戏" prop="game_id">
              <el-select v-model="createForm.game_id" placeholder="选择游戏" style="width:100%" @change="onCreateGameChange">
                <el-option v-for="g in gameList" :key="g.id" :label="g.name" :value="g.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="大区" prop="region_id">
              <el-select v-model="createForm.region_id" placeholder="选择大区" style="width:100%">
                <el-option v-for="r in createRegionList" :key="r.id" :label="r.name" :value="r.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="客户名称">
              <el-input v-model="createForm.customer_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系方式">
              <el-input v-model="createForm.customer_contact" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="createForm.remark" type="textarea" rows="1" />
        </el-form-item>
      </el-form>

      <el-divider>订单明细</el-divider>
      <div class="detail-toolbar">
        <el-select v-model="newDetailItemId" placeholder="选择物品" filterable style="width: 200px">
          <el-option v-for="i in itemOptions" :key="i.id" :label="`${i.name} (${i.code})`" :value="i.id" />
        </el-select>
        <el-input-number v-model="newDetailQty" :min="1" :max="9999" size="default" style="width:120px" />
        <el-input-number v-model="newDetailPrice" :min="0" :precision="2" size="default" placeholder="单价" style="width:130px" />
        <el-button type="primary" size="small" @click="addDetailRow" :disabled="!newDetailItemId">添加</el-button>
      </div>
      <el-table :data="createForm.details" border size="small" style="margin-top:10px">
        <el-table-column label="物品" min-width="140">
          <template #default="{ row }">{{ row._itemName }}</template>
        </el-table-column>
        <el-table-column label="数量" width="90" align="center">
          <template #default="{ row }">
            <el-input-number v-model="row.quantity" :min="1" size="small" controls-position="right" style="width:80px" @change="calcRowSubtotal(row)" />
          </template>
        </el-table-column>
        <el-table-column label="单价" width="110" align="right">
          <template #default="{ row }">
            <el-input-number v-model="row.unit_price" :min="0" :precision="2" size="small" controls-position="right" style="width:100px" @change="calcRowSubtotal(row)" />
          </template>
        </el-table-column>
        <el-table-column label="小计" width="90" align="right">
          <template #default="{ row }">{{ Number(row.subtotal || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="" width="50">
          <template #default="{ $index }">
            <el-button size="small" link type="danger" @click="createForm.details.splice($index, 1)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="total-line">合计：¥ {{ createTotal }}</div>

      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleCreateOrder">创建订单</el-button>
      </template>
    </el-dialog>

    <!-- 编辑订单弹窗 -->
    <el-dialog v-model="editDialogVisible" title="编辑订单" width="500px" destroy-on-close>
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="客户名称">
          <el-input v-model="editForm.customer_name" />
        </el-form-item>
        <el-form-item label="联系方式">
          <el-input v-model="editForm.customer_contact" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width:100%">
            <el-option label="待分配" value="pending" />
            <el-option label="已分配" value="assigned" />
            <el-option label="处理中" value="processing" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleEditOrder">保存</el-button>
      </template>
    </el-dialog>

    <!-- 分配机器弹窗 -->
    <el-dialog v-model="assignDialogVisible" title="分配机器" width="400px" destroy-on-close>
      <el-form :model="assignForm" label-width="80px">
        <el-form-item label="选择机器">
          <el-select v-model="assignForm.assigned_machine_id" placeholder="选择机器" style="width:100%">
            <el-option v-for="m in machineList" :key="m.id" :label="m.name || m.mac_address" :value="m.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAssign">确认分配</el-button>
      </template>
    </el-dialog>

    <!-- 订单明细抽屉（子表联动） -->
    <el-drawer v-model="detailDrawerVisible" :title="`订单明细 - ${currentOrder?.order_no || ''}`" size="650px" destroy-on-close>
      <div class="detail-info">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="订单号">{{ currentOrder?.order_no }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="orderStatusType(currentOrder?.status)" size="small">{{ orderStatusLabel(currentOrder?.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="游戏">{{ gameNameMap[currentOrder?.game_id] }}</el-descriptions-item>
          <el-descriptions-item label="大区">{{ regionNameMap[currentOrder?.region_id] }}</el-descriptions-item>
          <el-descriptions-item label="客户">{{ currentOrder?.customer_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="总金额">¥ {{ Number(currentOrder?.total_amount || 0).toFixed(2) }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <el-divider>明细列表</el-divider>
      <div v-if="currentOrder?.status === 'pending'" class="detail-toolbar">
        <el-select v-model="addDetailItemId" placeholder="选择物品添加" filterable style="width: 200px">
          <el-option v-for="i in itemOptions" :key="i.id" :label="`${i.name} (${i.code})`" :value="i.id" />
        </el-select>
        <el-input-number v-model="addDetailQty" :min="1" :max="9999" size="default" style="width:110px" />
        <el-button type="primary" size="small" @click="handleAddDetail" :disabled="!addDetailItemId">添加</el-button>
      </div>
      <el-table :data="detailList" border stripe size="small">
        <el-table-column prop="item_name" label="物品名称" min-width="140" />
        <el-table-column label="图片" width="60">
          <template #default="{ row }">
            <el-image v-if="row.item_image" :src="row.item_image" :preview-src-list="[row.item_image]" style="width:36px;height:36px" fit="cover" />
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="70" align="center" />
        <el-table-column prop="unit_price" label="单价" width="80" align="right">
          <template #default="{ row }">{{ Number(row.unit_price || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="subtotal" label="小计" width="80" align="right">
          <template #default="{ row }">{{ Number(row.subtotal || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="detailStatusType(row.status)" size="small">{{ detailStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" v-if="currentOrder?.status === 'pending'">
          <template #default="{ row }">
            <el-popconfirm title="确认删除？" @confirm="handleDeleteDetail(row.id)">
              <template #reference><el-button size="small" link type="danger">删除</el-button></template>
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
  getAllGames, getAllRegions, getAllMachines, getAllItems,
  getOrders, getOrder, createOrder, updateOrder, deleteOrder,
  addOrderDetail, deleteOrderDetail,
} from '../api'

const gameList = ref([])
const allRegions = ref([])
const machineList = ref([])
const allItems = ref([])
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const filterGameId = ref(null)
const filterStatus = ref('')
const loading = ref(false)

const gameNameMap = computed(() => Object.fromEntries(gameList.value.map(g => [g.id, g.name])))
const regionNameMap = computed(() => Object.fromEntries(allRegions.value.map(r => [r.id, r.name])))
const machineNameMap = computed(() => Object.fromEntries(machineList.value.map(m => [m.id, m.name || m.mac_address])))

function orderStatusLabel(s) { return { pending: '待分配', assigned: '已分配', processing: '处理中', completed: '已完成', cancelled: '已取消' }[s] || s }
function orderStatusType(s) { return { pending: 'warning', assigned: 'primary', processing: '', completed: 'success', cancelled: 'info' }[s] || '' }
function detailStatusLabel(s) { return { pending: '待处理', processing: '处理中', completed: '已完成', failed: '失败' }[s] || s }
function detailStatusType(s) { return { pending: 'warning', processing: '', completed: 'success', failed: 'danger' }[s] || '' }

async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize, keyword: keyword.value }
    if (filterGameId.value) params.game_id = filterGameId.value
    if (filterStatus.value) params.status = filterStatus.value
    const res = await getOrders(params)
    list.value = res.items; total.value = res.total
  } finally { loading.value = false }
}
function handleSearch() { page.value = 1; fetchList() }

// ── 新建订单 ──
const createDialogVisible = ref(false)
const submitting = ref(false)
const createFormRef = ref(null)
const createRules = {
  game_id: [{ required: true, message: '请选择游戏', trigger: 'change' }],
  region_id: [{ required: true, message: '请选择大区', trigger: 'change' }],
}
const createRegionList = ref([])
const itemOptions = computed(() => allItems.value.filter(i => i.game_id === createForm.game_id || !createForm.game_id))

const defaultCreateForm = () => ({ game_id: null, region_id: null, customer_name: '', customer_contact: '', remark: '', details: [] })
const createForm = reactive({ ...defaultCreateForm(), details: [] })

const newDetailItemId = ref(null)
const newDetailQty = ref(1)
const newDetailPrice = ref(0)

function openCreateDialog() {
  Object.assign(createForm, { ...defaultCreateForm(), details: [] })
  newDetailItemId.value = null; newDetailQty.value = 1; newDetailPrice.value = 0
  createRegionList.value = []
  createDialogVisible.value = true
}

async function onCreateGameChange() {
  createForm.region_id = null
  createRegionList.value = createForm.game_id ? await getAllRegions(createForm.game_id) : []
}

function addDetailRow() {
  const item = allItems.value.find(i => i.id === newDetailItemId.value)
  if (!item) return
  const price = newDetailPrice.value || Number(item.price) || 0
  const qty = newDetailQty.value
  createForm.details.push({
    item_id: item.id, _itemName: item.name, quantity: qty,
    unit_price: price, subtotal: price * qty,
  })
  newDetailItemId.value = null; newDetailQty.value = 1; newDetailPrice.value = 0
}

function calcRowSubtotal(row) { row.subtotal = (row.unit_price || 0) * (row.quantity || 0) }

const createTotal = computed(() => createForm.details.reduce((s, d) => s + (d.subtotal || 0), 0).toFixed(2))

async function handleCreateOrder() {
  await createFormRef.value?.validate()
  if (!createForm.details.length) { ElMessage.warning('请至少添加一个明细'); return }
  submitting.value = true
  try {
    await createOrder({
      game_id: createForm.game_id, region_id: createForm.region_id,
      customer_name: createForm.customer_name, customer_contact: createForm.customer_contact,
      remark: createForm.remark,
      details: createForm.details.map(d => ({ item_id: d.item_id, quantity: d.quantity, unit_price: d.unit_price })),
    })
    ElMessage.success('订单创建成功'); createDialogVisible.value = false; fetchList()
  } catch (e) { ElMessage.error(e.message) } finally { submitting.value = false }
}

// ── 编辑订单 ──
const editDialogVisible = ref(false)
const editForm = reactive({ customer_name: '', customer_contact: '', status: '', remark: '' })
const editOrderId = ref(null)

function openEditDialog(row) {
  editOrderId.value = row.id
  Object.assign(editForm, { customer_name: row.customer_name, customer_contact: row.customer_contact, status: row.status, remark: row.remark })
  editDialogVisible.value = true
}
async function handleEditOrder() {
  submitting.value = true
  try { await updateOrder(editOrderId.value, { ...editForm }); ElMessage.success('更新成功'); editDialogVisible.value = false; fetchList() }
  catch (e) { ElMessage.error(e.message) } finally { submitting.value = false }
}

// ── 分配机器 ──
const assignDialogVisible = ref(false)
const assignForm = reactive({ assigned_machine_id: null })
const assignOrderId = ref(null)

function openAssignDialog(row) { assignOrderId.value = row.id; assignForm.assigned_machine_id = null; assignDialogVisible.value = true }
async function handleAssign() {
  if (!assignForm.assigned_machine_id) { ElMessage.warning('请选择机器'); return }
  try { await updateOrder(assignOrderId.value, { status: 'assigned', assigned_machine_id: assignForm.assigned_machine_id }); ElMessage.success('分配成功'); assignDialogVisible.value = false; fetchList() }
  catch (e) { ElMessage.error(e.message) }
}

// ── 删除订单 ──
async function handleDeleteOrder(id) { try { await deleteOrder(id); ElMessage.success('已删除'); fetchList() } catch (e) { ElMessage.error(e.message) } }

// ── 订单明细抽屉 ──
const detailDrawerVisible = ref(false)
const currentOrder = ref(null)
const detailList = ref([])
const addDetailItemId = ref(null)
const addDetailQty = ref(1)

async function openDetailDrawer(order) {
  currentOrder.value = order
  detailDrawerVisible.value = true
  const res = await getOrder(order.id)
  detailList.value = res.details || []
  currentOrder.value = res
}

async function handleAddDetail() {
  try {
    await addOrderDetail(currentOrder.value.id, { item_id: addDetailItemId.value, quantity: addDetailQty.value })
    ElMessage.success('已添加'); addDetailItemId.value = null; addDetailQty.value = 1
    const res = await getOrder(currentOrder.value.id)
    detailList.value = res.details || []; currentOrder.value = res; fetchList()
  } catch (e) { ElMessage.error(e.message) }
}

async function handleDeleteDetail(detailId) {
  try {
    await deleteOrderDetail(detailId); ElMessage.success('已删除')
    const res = await getOrder(currentOrder.value.id)
    detailList.value = res.details || []; currentOrder.value = res; fetchList()
  } catch (e) { ElMessage.error(e.message) }
}

onMounted(async () => {
  gameList.value = await getAllGames()
  allRegions.value = await getAllRegions()
  machineList.value = await getAllMachines()
  allItems.value = await getAllItems()
  fetchList()
})
</script>

<style scoped>
.page-container { padding: 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
.toolbar .el-button { margin-left: auto; }
.pagination-wrap { display: flex; justify-content: center; margin-top: 20px; }
.detail-toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; }
.total-line { text-align: right; font-weight: 600; font-size: 15px; margin-top: 12px; color: #e6a23c; }
.detail-info { margin-bottom: 8px; }
</style>
