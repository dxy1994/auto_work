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

    <el-table :data="list" border stripe v-loading="loading" highlight-current-row @current-change="onCurrentChange" row-key="id">
      <el-table-column prop="order_no" label="订单号" width="160" show-overflow-tooltip />
      <el-table-column label="来源" width="80">
        <template #default="{ row }">{{ websiteNameMap[row.website_id] || row.website_id || '-' }}</template>
      </el-table-column>
      <el-table-column label="游戏" width="80">
        <template #default="{ row }">{{ gameNameMap[row.game_id] || row.game_id }}</template>
      </el-table-column>
      <el-table-column prop="product_title" label="商品标题" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.product_title || row.remark || '-' }}</template>
      </el-table-column>
      <el-table-column prop="trade_item_name" label="交易物品" width="120" show-overflow-tooltip>
        <template #default="{ row }">{{ row.trade_item_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="资产类型" width="90">
        <template #default="{ row }">{{ row.asset_type || '-' }}</template>
      </el-table-column>
      <el-table-column prop="buyer_character" label="买家" width="90" show-overflow-tooltip />
      <el-table-column prop="platform_price" label="平台售价" width="110" align="right">
        <template #default="{ row }">
          <span v-if="row.platform_price">₩ {{ Number(row.platform_price).toLocaleString() }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="orderStatusType(row.status)" size="small">{{ orderStatusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="交付" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="deliveryStatusType(row.delivery_status)" size="small">{{ deliveryStatusLabel(row.delivery_status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="150" />
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="openDetailDrawer(row)">明细</el-button>
          <el-button size="small" link type="primary" @click="openEditDialog(row)">编辑</el-button>
          <el-button size="small" link type="success" v-if="row.status === 'pending'" @click="openAssignDialog(row)">分配</el-button>
          <el-button size="small" link type="warning" v-if="row.delivery_status === 'greeting' && row.status !== 'completed' && row.status !== 'cancelled'" @click="handleRowReGreeting(row)">重新招呼</el-button>
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
      <el-table :data="createForm.details" border size="small" highlight-current-row @current-change="onCurrentChange" style="margin-top:10px">
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
    <el-drawer v-model="detailDrawerVisible" :title="`订单明细 - ${currentOrder?.order_no || ''}`" size="700px" destroy-on-close>
      <!-- 平台信息 -->
      <el-descriptions :column="2" border size="small" title="平台信息" class="detail-section">
        <el-descriptions-item label="来源平台">{{ websiteNameMap[currentOrder?.website_id] || currentOrder?.website_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="平台订单号">{{ currentOrder?.source_order_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="平台下单时间">{{ currentOrder?.platform_order_time || '-' }}</el-descriptions-item>
        <el-descriptions-item label="平台分类">
          <el-tag size="small" v-if="currentOrder?.platform_item_type">{{ currentOrder.platform_item_type }}</el-tag>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="商品标题" :span="2">{{ currentOrder?.product_title || currentOrder?.remark || '-' }}</el-descriptions-item>
        <el-descriptions-item label="交易物品">{{ currentOrder?.trade_item_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="资产类型">{{ currentOrder?.asset_type || '-' }}</el-descriptions-item>
      </el-descriptions>

      <!-- 交易信息 -->
      <el-descriptions :column="3" border size="small" title="交易信息" class="detail-section">
        <el-descriptions-item label="平台售价">₩ {{ currentOrder?.platform_price ? Number(currentOrder.platform_price).toLocaleString() : '-' }}</el-descriptions-item>
        <el-descriptions-item label="上架数量">{{ currentOrder?.quantity || '-' }}</el-descriptions-item>
        <el-descriptions-item label="已售数量">{{ currentOrder?.sale_quantity || '-' }}</el-descriptions-item>
        <el-descriptions-item label="买家角色">{{ currentOrder?.buyer_character || '-' }}</el-descriptions-item>
        <el-descriptions-item label="交付资产">{{ currentOrder?.asset_type }} × {{ currentOrder?.asset_amount || 0 }}</el-descriptions-item>
        <el-descriptions-item label="交付状态">
          <el-tag :type="deliveryStatusType(currentOrder?.delivery_status)" size="small">{{ deliveryStatusLabel(currentOrder?.delivery_status) }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 订单信息 -->
      <el-descriptions :column="2" border size="small" title="订单信息" class="detail-section">
        <el-descriptions-item label="游戏">{{ gameNameMap[currentOrder?.game_id] || currentOrder?.game_id }}</el-descriptions-item>
        <el-descriptions-item label="大区">{{ regionNameMap[currentOrder?.region_id] || currentOrder?.region_id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="orderStatusType(currentOrder?.status)" size="small">{{ orderStatusLabel(currentOrder?.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="总金额">¥ {{ Number(currentOrder?.total_amount || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ currentOrder?.customer_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="联系方式">{{ currentOrder?.customer_contact || '-' }}</el-descriptions-item>
        <el-descriptions-item label="分配机器">{{ machineNameMap[currentOrder?.assigned_machine_id] || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{ currentOrder?.remark || '-' }}</el-descriptions-item>
        <el-descriptions-item v-if="currentOrder?.last_error_code" label="异常编码" :span="2">
          <el-tag type="danger" size="small">{{ currentOrder.last_error_code }}</el-tag>
          <span style="margin-left:8px">{{ currentOrder.last_error_message || '' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ currentOrder?.created_at }}</el-descriptions-item>
      </el-descriptions>

      <el-divider>明细列表</el-divider>
      <div v-if="currentOrder?.delivery_status === 'greeting' && currentOrder?.status !== 'completed' && currentOrder?.status !== 'cancelled'" style="margin-bottom:8px">
        <el-button type="warning" size="small" :loading="reGreetingLoading" @click="handleReGreeting">
          <el-icon><RefreshRight /></el-icon> 重新招呼
        </el-button>
      </div>
      <div v-if="currentOrder?.status === 'pending'" class="detail-toolbar">
        <el-select v-model="addDetailItemId" placeholder="选择物品添加" filterable style="width: 200px">
          <el-option v-for="i in itemOptions" :key="i.id" :label="`${i.name} (${i.code})`" :value="i.id" />
        </el-select>
        <el-input-number v-model="addDetailQty" :min="1" :max="9999" size="default" style="width:110px" />
        <el-button type="primary" size="small" @click="handleAddDetail" :disabled="!addDetailItemId">添加</el-button>
      </div>
      <el-table :data="detailList" border stripe size="small" highlight-current-row @current-change="onCurrentChange" row-key="id">
        <el-table-column prop="item_name" label="物品名称" min-width="140" />
        <el-table-column prop="bundle_name" label="来源套装" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag size="small" type="info" v-if="row.bundle_name">{{ row.bundle_name }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
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
        <el-table-column label="进货价" width="80" align="right">
          <template #default="{ row }">{{ row.purchase_price != null ? Number(row.purchase_price).toFixed(2) : '-' }}</template>
        </el-table-column>
        <el-table-column label="出货价" width="80" align="right">
          <template #default="{ row }">{{ row.selling_price != null ? Number(row.selling_price).toFixed(2) : '-' }}</template>
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
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import {
  getAllGames, getAllRegions, getAllMachines, getAllItems, getAllWebsites,
  getOrders, getOrder, createOrder, updateOrder, deleteOrder,
  addOrderDetail, deleteOrderDetail, reGreeting,
} from '../api'

const gameList = ref([])
const allRegions = ref([])
const machineList = ref([])
const allItems = ref([])
const websiteList = ref([])
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const filterGameId = ref(null)
const filterStatus = ref('')
const loading = ref(false)
const route = useRoute()

const currentRow = ref(null)
function onCurrentChange(row) { currentRow.value = row }

const gameNameMap = computed(() => Object.fromEntries(gameList.value.map(g => [g.id, g.name])))
const regionNameMap = computed(() => Object.fromEntries(allRegions.value.map(r => [r.id, r.name])))
const machineNameMap = computed(() => Object.fromEntries(machineList.value.map(m => [m.id, m.name || m.mac_address])))
const websiteNameMap = computed(() => Object.fromEntries(websiteList.value.map(w => [w.id, w.name])))

function orderStatusLabel(s) { return { pending: '待分配', assigned: '已分配', processing: '处理中', completed: '已完成', cancelled: '已取消' }[s] || s }
function orderStatusType(s) { return { pending: 'warning', assigned: 'primary', processing: '', completed: 'success', cancelled: 'info' }[s] || '' }
function detailStatusLabel(s) { return { pending: '待处理', processing: '处理中', completed: '已完成', failed: '失败' }[s] || s }
function detailStatusType(s) { return { pending: 'warning', processing: '', completed: 'success', failed: 'danger' }[s] || '' }
function deliveryStatusLabel(s) { return { greeting: '待招呼', detected: '待分配', waiting_assignment: '等待指派', assigned: '已指派', delivering: '交付中', delivered: '已交付', review_required: '待人工复核', suspended: '已挂起', failed: '失败' }[s] || s || '待分配' }
function deliveryStatusType(s) { return { greeting: 'warning', detected: 'info', waiting_assignment: 'warning', assigned: 'primary', delivering: '', delivered: 'success', review_required: 'danger', suspended: 'danger', failed: 'danger' }[s] || 'info' }

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

let lastAlertNavigation = ''
async function openAlertOrderFromRoute() {
  const orderId = Number(route.query.alert_order_id)
  if (!Number.isInteger(orderId) || orderId <= 0) return
  const navigationKey = `${orderId}:${route.query.alert_nonce || ''}`
  if (navigationKey === lastAlertNavigation) return
  lastAlertNavigation = navigationKey
  try {
    await openDetailDrawer({ id: orderId })
  } catch (error) {
    ElMessage.error(error.message || '订单详情加载失败')
  }
}

watch(
  () => [route.query.alert_order_id, route.query.alert_nonce],
  () => openAlertOrderFromRoute(),
)

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

// ── 重新招呼 ──
const reGreetingLoading = ref(false)

async function handleReGreeting() {
  reGreetingLoading.value = true
  try {
    const res = await reGreeting(currentOrder.value.id)
    ElMessage.success(res.message || '已重新触发招呼')
    // 刷新订单详情
    const orderRes = await getOrder(currentOrder.value.id)
    detailList.value = orderRes.details || []; currentOrder.value = orderRes; fetchList()
  } catch (e) { ElMessage.error(e.message) }
  finally { reGreetingLoading.value = false }
}

async function handleRowReGreeting(row) {
  try {
    const res = await reGreeting(row.id)
    ElMessage.success(res.message || '已重新触发招呼')
    fetchList()
  } catch (e) { ElMessage.error(e.message) }
}

onMounted(async () => {
  gameList.value = await getAllGames()
  allRegions.value = await getAllRegions()
  machineList.value = await getAllMachines()
  allItems.value = await getAllItems()
  websiteList.value = await getAllWebsites()
  await fetchList()
  await openAlertOrderFromRoute()
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
.detail-section { margin-bottom: 16px; }
</style>
