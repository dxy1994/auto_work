<template>
  <div class="page-container">
    <section class="item-directory">
      <header class="item-directory__header">
        <div class="item-directory__intro">
          <span class="item-directory__eyebrow">物品目录</span>
          <div class="item-directory__title-line">
            <h1>游戏物品</h1>
            <span class="item-directory__count">{{ total }} 件</span>
          </div>
          <p>维护交易物品、套装组成以及自动识别所需的图片素材。</p>
        </div>
        <div class="item-directory__actions">
          <el-select v-model="filterGameId" class="item-filter item-filter--game" placeholder="全部游戏" clearable filterable @change="handleSearch">
            <el-option v-for="g in gameList" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
          <el-select v-model="filterType" class="item-filter item-filter--type" placeholder="全部类型" clearable @change="handleSearch">
            <el-option label="单品" :value="0" />
            <el-option label="套装" :value="1" />
          </el-select>
          <el-input v-model="keyword" class="item-search" placeholder="搜索物品名称" clearable @input="handleSearch">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button type="primary" @click="openItemDialog()">
            <el-icon><Plus /></el-icon> 新增物品
          </el-button>
        </div>
      </header>

      <div class="item-table-viewport">
      <el-table
        ref="tableRef"
        class="item-table"
        :data="list"
        border
        stripe
        height="100%"
        v-loading="loading"
        row-key="id"
        highlight-current-row
        :row-class-name="tableRowClassName"
        @current-change="onCurrentChange"
        @expand-change="handleExpandChange"
      >
        <el-table-column type="expand" width="46">
          <template #default="{ row }">
            <div v-if="row.is_bundle" class="expand-area">
              <div class="expand-heading">
                <div>
                  <strong>套装内容</strong>
                  <span>{{ row._children?.length || 0 }} 件子物品</span>
                </div>
                <el-button size="small" type="primary" plain @click="openChildSelect(row)">
                  <el-icon><Plus /></el-icon> 选择已有物品
                </el-button>
              </div>
              <el-table class="child-item-table" :data="row._children || []" border size="small" v-loading="row._childrenLoading" highlight-current-row @current-change="onCurrentChange">
                <el-table-column label="物品" min-width="240">
                  <template #default="{ row: child }">
                    <div class="item-identity item-identity--compact">
                      <el-avatar :size="34" shape="square" :src="child.selected_image || child.image || undefined" class="item-avatar">{{ itemInitial(child.name) }}</el-avatar>
                      <div class="item-identity__copy">
                        <strong>{{ child.name }}</strong>
                        <div class="item-meta"><code>{{ child.code }}</code><span v-if="child.category">{{ child.category }}</span></div>
                      </div>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="识别素材" min-width="210">
                  <template #default="{ row: child }">
                    <div class="recognition-panel recognition-panel--compact">
                      <div class="image-state">
                        <span class="image-state-label">默认</span>
                        <el-image v-if="child.image" class="recognition-thumb" :src="child.image" :preview-src-list="[child.image]" fit="cover" preview-teleported />
                        <div v-else class="image-placeholder">未传</div>
                      </div>
                      <div class="image-state">
                        <span class="image-state-label">选中</span>
                        <el-image v-if="child.selected_image" class="recognition-thumb" :src="child.selected_image" :preview-src-list="[child.selected_image]" fit="cover" preview-teleported />
                        <div v-else class="image-placeholder">未传</div>
                      </div>
                      <el-tag :type="recognitionStateType(child)" size="small" effect="plain" class="recognition-count">{{ recognitionCount(child) }}/2</el-tag>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column prop="quantity" label="数量" width="70" align="center" />
                <el-table-column label="参考价" width="100" align="right"><template #default="{ row: child }">{{ formatItemPrice(child.price) }}</template></el-table-column>
                <el-table-column label="操作" width="128" align="right">
                  <template #default="{ row: child }">
                    <el-button size="small" link type="primary" @click="openItemDialog(child)"><el-icon><EditPen /></el-icon> 编辑</el-button>
                    <el-popconfirm title="确认从套装中移除？" @confirm="handleRemoveChild(row.id, child.id)">
                      <template #reference><el-button size="small" link type="danger">移除</el-button></template>
                    </el-popconfirm>
                  </template>
                </el-table-column>
                <template #empty><el-empty description="这个套装还没有子物品" :image-size="62" /></template>
              </el-table>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="物品" min-width="260">
          <template #default="{ row }">
            <div class="item-identity">
              <el-avatar :size="44" shape="square" :src="row.selected_image || row.image || undefined" class="item-avatar">{{ itemInitial(row.name) }}</el-avatar>
              <div class="item-identity__copy">
                <div class="item-name-line">
                  <strong>{{ row.name }}</strong>
                  <el-tag :type="row.is_bundle ? 'warning' : 'info'" size="small" effect="plain">{{ row.is_bundle ? '套装' : '单品' }}</el-tag>
                </div>
                <div class="item-meta"><code>{{ row.code }}</code><span v-if="row.category">{{ row.category }}</span></div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="归属配置" min-width="145">
          <template #default="{ row }">
            <div class="item-context">
              <strong>{{ gameNameMap[row.game_id] || '未关联游戏' }}</strong>
              <span>{{ row.position ? `坐标 ${row.position}` : '未设置位置坐标' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="识别素材" min-width="220">
          <template #default="{ row }">
            <div class="recognition-panel">
              <div class="image-state">
                <span class="image-state-label">默认</span>
                <el-image v-if="row.image" class="recognition-thumb" :src="row.image" :preview-src-list="[row.image]" fit="cover" preview-teleported />
                <div v-else class="image-placeholder">未上传</div>
              </div>
              <div class="image-state">
                <span class="image-state-label">选中</span>
                <el-image v-if="row.selected_image" class="recognition-thumb" :src="row.selected_image" :preview-src-list="[row.selected_image]" fit="cover" preview-teleported />
                <div v-else class="image-placeholder">未上传</div>
              </div>
              <div class="recognition-readiness">
                <el-tag :type="recognitionStateType(row)" size="small" effect="plain">{{ recognitionCount(row) }}/2</el-tag>
                <span>{{ recognitionStateLabel(row) }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="参考配置" width="116" align="right">
          <template #default="{ row }">
            <div class="item-metrics"><strong>{{ formatItemPrice(row.price) }}</strong><span>排序 {{ row.sort_order ?? 0 }}</span></div>
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="130" show-overflow-tooltip>
          <template #default="{ row }"><span :class="['item-remark', { 'is-empty': !row.remark }]">{{ row.remark || '暂无备注' }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="142" fixed="right" align="right">
          <template #default="{ row }">
            <div class="item-row-actions">
              <el-button size="small" link type="primary" @click="openItemDialog(row)"><el-icon><EditPen /></el-icon> 编辑</el-button>
              <el-popconfirm title="确认删除？" @confirm="handleDeleteItem(row.id)">
                <template #reference><el-button size="small" link type="danger"><el-icon><Delete /></el-icon> 删除</el-button></template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
        <template #empty><el-empty :description="keyword || filterGameId || filterType !== null ? '没有匹配的物品' : '还没有物品，点击右上角新增'" :image-size="80" /></template>
      </el-table>
      </div>

      <div class="pagination-wrap" v-if="total > pageSize">
        <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="fetchList" />
      </div>
    </section>

    <!-- 物品编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑物品' : '新增物品'" width="620px" destroy-on-close>
      <el-form :model="form" label-width="100px" ref="formRef" :rules="rules">
        <el-form-item label="所属游戏" prop="game_id">
          <el-select v-model="form.game_id" placeholder="选择游戏" style="width:100%" :disabled="isEdit">
            <el-option v-for="g in gameList" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="物品名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.is_bundle">
            <el-radio :value="0">单品</el-radio>
            <el-radio :value="1">套装</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="未选中图片">
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept="image/*"
            :on-change="handleImageChange"
            :on-remove="handleImageRemove"
            :file-list="imageFileList"
            list-type="picture"
          >
            <el-button size="small" type="primary">选择图片</el-button>
            <template #tip><div class="el-upload__tip">可选。用于识别物品未选中状态；未上传时指令不会携带该图片。</div></template>
          </el-upload>
          <el-input v-if="form.image" v-model="form.image" placeholder="或直接输入URL" size="small" style="margin-top:6px" />
        </el-form-item>
        <el-form-item label="选中图片">
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept="image/*"
            :on-change="handleSelectedImageChange"
            :on-remove="handleSelectedImageRemove"
            :file-list="selectedImageFileList"
            list-type="picture"
          >
            <el-button size="small" type="primary">选择图片</el-button>
            <template #tip><div class="el-upload__tip">可选。用于识别物品高亮状态，可与未选中图片独立配置。</div></template>
          </el-upload>
          <el-input v-if="form.selected_image" v-model="form.selected_image" placeholder="或直接输入URL" size="small" style="margin-top:6px" />
        </el-form-item>
        <el-form-item label="位置坐标">
          <el-input v-model="form.position" placeholder="如：X:100,Y:200 或 3-5" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" placeholder="请选择分类" style="width:100%">
            <el-option label="游戏币" value="游戏币" />
            <el-option label="物品" value="物品" />
            <el-option label="账户" value="账户" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="参考价格">
          <el-input-number v-model="form.price" :min="0" :precision="2" :step="1" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :max="999" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 选择已有物品加入套装弹窗 -->
    <el-dialog v-model="childSelectVisible" title="选择已有物品加入套装" width="700px" destroy-on-close @opened="onChildDialogOpened">
      <el-input v-model="childKeyword" placeholder="搜索物品名称..." clearable style="margin-bottom:12px" @input="fetchAvailableItems">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-table :data="availableItems" border stripe size="small" @selection-change="onChildSelectionChange" @row-click="onChildRowClick" ref="childTableRef" v-loading="childLoading">
        <el-table-column type="selection" width="50" />
        <el-table-column label="物品" min-width="220">
          <template #default="{ row }">
            <div class="item-identity">
              <div class="item-name">{{ row.name }}</div>
              <div class="item-meta"><span class="item-code">{{ row.code }}</span></div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="识别素材" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="recognitionStateType(row)" size="small" effect="plain">{{ recognitionCount(row) }}/2</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="100" align="center">
          <template #default="{ row }">
            <el-input-number v-model="row._quantity" :min="1" :max="99" size="small" controls-position="right" style="width:90px" @click.stop />
          </template>
        </el-table-column>
        <el-table-column prop="price" label="价格" width="90" align="right" />
        <el-table-column prop="category" label="分类" width="100" />
      </el-table>
      <div class="pagination-wrap" v-if="childTotal > childPageSize" style="margin-top:12px">
        <el-pagination v-model:current-page="childPage" :page-size="childPageSize" :total="childTotal" layout="prev, pager, next" @current-change="fetchAvailableItems" />
      </div>
      <template #footer>
        <el-button @click="childSelectVisible = false">取消</el-button>
        <el-button type="primary" :loading="childSubmitting" @click="handleAddChildren">添加选中物品</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getAllGames, getGameItems, getBundleChildren, addBundleChildren, removeBundleChild, createGameItem, updateGameItem, deleteGameItem, uploadFile } from '../api'

const gameList = ref([])
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const filterGameId = ref(null)
const filterType = ref(null)
const loading = ref(false)

const currentRow = ref(null)
function onCurrentChange(row) { currentRow.value = row }

const gameNameMap = computed(() => Object.fromEntries(gameList.value.map(g => [g.id, g.name])))

async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize, keyword: keyword.value }
    if (filterGameId.value) params.game_id = filterGameId.value
    if (filterType.value !== null && filterType.value !== '') params.is_bundle = filterType.value
    const res = await getGameItems(params)
    // 为套装行预留子物品加载
    const items = res.items.map(i => ({ ...i, _children: null, _childrenLoading: false }))
    list.value = items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function handleSearch() { page.value = 1; fetchList() }

// ── 展开行控制 ──
const tableRef = ref(null)

// 隐藏非套装行的展开图标
function tableRowClassName({ row }) {
  return row.is_bundle ? '' : 'hide-expand-icon'
}

// 展开时加载子物品
async function handleExpandChange(row, expandedRows) {
  if (row.is_bundle && !row._children) {
    await loadChildren(row)
  }
}

async function loadChildren(row) {
  if (!row.is_bundle || row._children) return
  row._childrenLoading = true
  try {
    row._children = await getBundleChildren(row.id)
  } finally {
    row._childrenLoading = false
  }
}

// ── 物品编辑 ──
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const submitting = ref(false)
const formRef = ref(null)
const rules = {
  game_id: [{ required: true, message: '请选择游戏', trigger: 'change' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
}

const defaultForm = () => ({
  game_id: null, name: '', code: '', image: '', selected_image: '', is_bundle: 0,
  category: '物品', price: 0, position: '', sort_order: 0, remark: '',
})
const form = reactive(defaultForm())

// 生成随机物品编码（8位大写字母+数字，如 A3K9M7XQ）
function genItemCode() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
  let code = ''
  for (let i = 0; i < 8; i++) {
    code += chars[Math.floor(Math.random() * chars.length)]
  }
  return code
}

// 物品图片上传
const imageFileList = ref([])
const imageFile = ref(null)
const selectedImageFileList = ref([])
const selectedImageFile = ref(null)

function recognitionCount(item) {
  return Number(Boolean(item?.image)) + Number(Boolean(item?.selected_image))
}

function recognitionStateType(item) {
  const count = recognitionCount(item)
  if (count === 2) return 'success'
  if (count === 1) return 'warning'
  return 'info'
}

function recognitionStateLabel(item) {
  const count = recognitionCount(item)
  if (count === 2) return '素材完整'
  if (count === 1) return '待补充'
  return '未配置'
}

function itemInitial(name) {
  return String(name || '物').trim().charAt(0).toUpperCase()
}

function formatItemPrice(value) {
  const price = Number(value)
  return Number.isFinite(price) ? price.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) : '-'
}

function handleImageChange(file) {
  imageFile.value = file.raw
  imageFileList.value = [file]
}

function handleImageRemove() {
  imageFile.value = null
  imageFileList.value = []
  form.image = ''
}

function handleSelectedImageChange(file) {
  selectedImageFile.value = file.raw
  selectedImageFileList.value = [file]
}

function handleSelectedImageRemove() {
  selectedImageFile.value = null
  selectedImageFileList.value = []
  form.selected_image = ''
}

function openItemDialog(row = null) {
  isEdit.value = !!row
  editId.value = row?.id ?? null
  imageFile.value = null
  selectedImageFile.value = null
  if (row?.image) {
    imageFileList.value = [{ name: row.image.split('/').pop() || 'item.png', url: row.image }]
  } else {
    imageFileList.value = []
  }
  if (row?.selected_image) {
    selectedImageFileList.value = [{ name: row.selected_image.split('/').pop() || 'selected-item.png', url: row.selected_image }]
  } else {
    selectedImageFileList.value = []
  }
  const base = row ? { ...row, is_bundle: row.is_bundle ? 1 : 0 } : { ...defaultForm(), game_id: filterGameId.value, code: genItemCode() }
  Object.assign(form, base)
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    // 先上传图片
    if (imageFile.value) {
      const res = await uploadFile(imageFile.value)
      if (res.code === 0) form.image = res.url
    }
    if (selectedImageFile.value) {
      const res = await uploadFile(selectedImageFile.value)
      if (res.code === 0) form.selected_image = res.url
    }
    const data = { ...form }
    if (isEdit.value) {
      await updateGameItem(editId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createGameItem(data)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

async function handleDeleteItem(id) {
  try {
    await deleteGameItem(id)
    ElMessage.success('已删除')
    fetchList()
  } catch (e) { ElMessage.error(e.message) }
}

// 从套装中移除子物品（不删除物品本身）
async function handleRemoveChild(bundleId, childId) {
  try {
    await removeBundleChild(bundleId, childId)
    ElMessage.success('已从套装中移除')
    // 刷新该套装的子物品列表
    const bundleRow = list.value.find(r => r.id === bundleId)
    if (bundleRow) {
      bundleRow._children = null
      await loadChildren(bundleRow)
    }
  } catch (e) { ElMessage.error(e.message) }
}

// ── 套装子物品选择 ──
const childSelectVisible = ref(false)
const availableItems = ref([])
const selectedChildren = ref([])
const childSubmitting = ref(false)
const childLoading = ref(false)
const childTableRef = ref(null)
const currentBundleId = ref(null)
const currentBundleGameId = ref(null)
const childPage = ref(1)
const childPageSize = 10
const childTotal = ref(0)
const childKeyword = ref('')

function onChildSelectionChange(selection) {
  selectedChildren.value = selection
}

function onChildRowClick(row) {
  childTableRef.value?.toggleRowSelection(row)
}

async function fetchAvailableItems() {
  childLoading.value = true
  try {
    const res = await getGameItems({
      game_id: currentBundleGameId.value,
      is_bundle: 0,
      exclude_bundle_id: currentBundleId.value,
      keyword: childKeyword.value || undefined,
      page: childPage.value,
      page_size: childPageSize,
    })
    availableItems.value = res.items.map(i => ({ ...i, _quantity: i._quantity || 1 }))
    childTotal.value = res.total
  } finally {
    childLoading.value = false
  }
}

function onChildDialogOpened() {
  childKeyword.value = ''
  childPage.value = 1
  fetchAvailableItems()
}

async function openChildSelect(bundleRow) {
  currentBundleId.value = bundleRow.id
  currentBundleGameId.value = bundleRow.game_id
  selectedChildren.value = []
  childKeyword.value = ''
  childPage.value = 1
  childSelectVisible.value = true
}

async function handleAddChildren() {
  if (selectedChildren.value.length === 0) {
    ElMessage.warning('请至少选择一个物品')
    return
  }
  childSubmitting.value = true
  try {
    const items = selectedChildren.value.map(i => ({ item_id: i.id, quantity: i._quantity || 1 }))
    await addBundleChildren(currentBundleId.value, items)
    ElMessage.success(`已添加 ${selectedChildren.value.length} 个物品`)
    childSelectVisible.value = false
    // 刷新该套装的子物品列表
    const bundleRow = list.value.find(r => r.id === currentBundleId.value)
    if (bundleRow) {
      bundleRow._children = null
      await loadChildren(bundleRow)
    }
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    childSubmitting.value = false
  }
}

onMounted(async () => {
  gameList.value = await getAllGames()
  fetchList()
})
</script>

<style scoped>
.page-container { padding: 0; }
.item-directory {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e3e9f1;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 5px 18px rgba(43, 60, 82, .045);
}
.item-directory__header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 22px 20px 20px;
  border-bottom: 1px solid #e8edf3;
}
.item-directory__intro { min-width: 210px; }
.item-directory__eyebrow {
  display: block;
  margin-bottom: 5px;
  color: #409eff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .14em;
}
.item-directory__title-line { display: flex; align-items: center; gap: 10px; }
.item-directory__title-line h1 { margin: 0; color: #25364a; font-size: 21px; line-height: 1.3; }
.item-directory__count {
  padding: 2px 8px;
  color: #66778c;
  border: 1px solid #dde5ee;
  border-radius: 999px;
  background: #f7f9fc;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.item-directory__intro p { margin: 6px 0 0; color: #8793a3; font-size: 13px; }
.item-directory__actions { display: flex; flex: 0 0 auto; align-items: center; justify-content: flex-end; gap: 10px; flex-wrap: wrap; }
.item-filter--game { width: 168px; }
.item-filter--type { width: 112px; }
.item-search { width: 208px; }
.item-table-viewport { min-height: 0; flex: 1; overflow: hidden; }
.item-table { width: 100%; border-right: 0; border-left: 0; }
.item-table :deep(.el-table__header th.el-table__cell) {
  height: 44px;
  color: #66778c;
  background: #f7f9fc;
  font-size: 12px;
  font-weight: 600;
}
.item-table :deep(.el-table__body td.el-table__cell) { padding: 11px 0; }
.item-table :deep(.el-table__row) { transition: background-color .18s ease; }
.pagination-wrap { display: flex; justify-content: center; padding: 18px 20px; border-top: 1px solid #edf0f4; }
.expand-area { padding: 15px 18px 18px 50px; background: linear-gradient(90deg, #f7faff 0, #fbfcfe 100%); }
.expand-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 11px; }
.expand-heading > div { display: flex; align-items: baseline; gap: 10px; }
.expand-heading strong { color: #30445c; font-size: 13px; }
.expand-heading span { color: #97a3b2; font-size: 12px; }
.child-item-table { border-radius: 7px; }
.item-identity { display: flex; min-width: 0; align-items: center; gap: 12px; }
.item-identity--compact { gap: 10px; }
.item-avatar {
  flex: 0 0 auto;
  color: #3278c8;
  border: 1px solid #d8e6f7;
  border-radius: 9px;
  background: linear-gradient(145deg, #edf6ff, #dcecff);
  font-weight: 700;
}
.item-identity__copy { min-width: 0; }
.item-name-line { display: flex; min-width: 0; align-items: center; gap: 8px; }
.item-name-line strong,
.item-identity__copy > strong { overflow: hidden; color: #25364a; font-size: 14px; line-height: 1.4; text-overflow: ellipsis; white-space: nowrap; }
.item-meta { display: flex; min-width: 0; align-items: center; gap: 9px; margin-top: 4px; color: #8a97a8; font-size: 11px; }
.item-meta code { overflow: hidden; color: #687a8f; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; text-overflow: ellipsis; white-space: nowrap; }
.item-context,
.item-metrics { display: grid; gap: 5px; }
.item-context strong { overflow: hidden; color: #40546c; font-size: 13px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.item-context span,
.item-metrics span { color: #96a1af; font-size: 11px; }
.item-metrics { justify-items: end; }
.item-metrics strong { color: #30445c; font-size: 14px; font-variant-numeric: tabular-nums; }
.recognition-panel { display: flex; min-width: 0; align-items: flex-end; gap: 8px; }
.recognition-panel--compact { gap: 7px; }
.image-state { display: flex; flex-direction: column; gap: 4px; }
.image-state-label { color: #909cac; font-size: 10px; line-height: 1; text-align: center; }
.recognition-thumb,
.image-placeholder {
  width: 46px;
  height: 46px;
  border: 1px solid #dde5ee;
  border-radius: 7px;
  box-sizing: border-box;
}
.recognition-thumb { display: block; }
.image-placeholder {
  display: grid;
  place-items: center;
  color: #a5afbc;
  background: repeating-linear-gradient(135deg, #f7f9fc, #f7f9fc 6px, #f1f4f8 6px, #f1f4f8 12px);
  font-size: 10px;
}
.recognition-readiness { display: grid; gap: 4px; margin-bottom: 1px; }
.recognition-readiness span { color: #8d99a9; font-size: 10px; white-space: nowrap; }
.recognition-count { margin-bottom: 11px; font-variant-numeric: tabular-nums; }
.item-remark { color: #617288; font-size: 12px; }
.item-remark.is-empty { color: #a7b0bc; }
.item-row-actions { display: flex; justify-content: flex-end; gap: 2px; }
.item-row-actions .el-button + .el-button { margin-left: 5px; }

@media (max-width: 1100px) {
  .item-directory__header { align-items: flex-start; flex-direction: column; }
  .item-directory__actions { width: 100%; justify-content: flex-start; }
}
@media (max-width: 700px) {
  .item-directory__header { padding: 18px 16px; }
  .item-directory__actions { display: grid; grid-template-columns: 1fr 1fr; }
  .item-filter--game,
  .item-filter--type,
  .item-search { width: 100%; }
  .item-search { grid-column: 1 / -1; }
  .item-directory__actions > .el-button { grid-column: 1 / -1; margin: 0; }
  .expand-area { padding-left: 16px; }
  .expand-heading { align-items: flex-start; flex-direction: column; }
}
@media (max-width: 430px) {
  .item-directory__actions { grid-template-columns: 1fr; }
  .item-search,
  .item-directory__actions > .el-button { grid-column: auto; width: 100%; }
}

/* 隐藏非套装行的展开图标 */
:deep(.hide-expand-icon .el-table__expand-icon) {
  visibility: hidden;
  pointer-events: none;
}
@media (prefers-reduced-motion: reduce) {
  .item-table :deep(.el-table__row) { transition: none; }
}
</style>
