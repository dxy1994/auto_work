<template>
  <div class="page-container">
    <div class="toolbar">
      <el-select v-model="filterGameId" placeholder="选择游戏" clearable style="width: 180px" @change="handleSearch">
        <el-option v-for="g in gameList" :key="g.id" :label="g.name" :value="g.id" />
      </el-select>
      <el-select v-model="filterType" placeholder="全部类型" clearable style="width: 120px" @change="handleSearch">
        <el-option label="单品" :value="0" />
        <el-option label="套装" :value="1" />
      </el-select>
      <el-input v-model="keyword" placeholder="搜索物品名称..." clearable style="width: 200px" @input="handleSearch">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" @click="openItemDialog()">
        <el-icon><Plus /></el-icon> 新增物品
      </el-button>
    </div>

    <el-table
      ref="tableRef"
      :data="list"
      border stripe
      v-loading="loading"
      row-key="id"
      highlight-current-row
      :row-class-name="tableRowClassName"
      @current-change="onCurrentChange"
      @expand-change="handleExpandChange"
    >
      <el-table-column type="expand">
        <template #default="{ row }">
          <div v-if="row.is_bundle" class="expand-area">
            <div class="expand-title">套装子物品：</div>
            <el-table :data="row._children || []" border size="small" v-loading="row._childrenLoading" highlight-current-row @current-change="onCurrentChange">
              <el-table-column label="物品" min-width="220">
                <template #default="{ row: child }">
                  <div class="item-identity">
                    <div class="item-name">{{ child.name }}</div>
                    <div class="item-meta">
                      <span class="item-code">{{ child.code }}</span>
                      <span v-if="child.category">{{ child.category }}</span>
                    </div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="识别素材（可选）" min-width="230">
                <template #default="{ row: child }">
                  <div class="recognition-panel">
                    <div class="image-state">
                      <span class="image-state-label">未选中</span>
                      <el-image v-if="child.image" class="recognition-thumb" :src="child.image" :preview-src-list="[child.image]" fit="cover" preview-teleported />
                      <div v-else class="image-placeholder">未上传</div>
                    </div>
                    <div class="image-state">
                      <span class="image-state-label">选中</span>
                      <el-image v-if="child.selected_image" class="recognition-thumb" :src="child.selected_image" :preview-src-list="[child.selected_image]" fit="cover" preview-teleported />
                      <div v-else class="image-placeholder">未上传</div>
                    </div>
                    <el-tag :type="recognitionStateType(child)" size="small" effect="plain" class="recognition-count">
                      {{ recognitionCount(child) }}/2
                    </el-tag>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="quantity" label="数量" width="70" align="center" />
              <el-table-column prop="price" label="参考价格" width="100" align="right" />
              <el-table-column label="操作" width="120">
                <template #default="{ row: child }">
                  <el-button size="small" link type="primary" @click="openItemDialog(child)">编辑</el-button>
                  <el-popconfirm title="确认从套装中移除？" @confirm="handleRemoveChild(row.id, child.id)">
                    <template #reference><el-button size="small" link type="danger">移除</el-button></template>
                  </el-popconfirm>
                </template>
              </el-table-column>
            </el-table>
            <el-button size="small" type="primary" style="margin-top:8px" @click="openChildSelect(row)">+ 选择已有物品</el-button>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="物品" min-width="240">
        <template #default="{ row }">
          <div class="item-identity">
            <div class="item-name-line">
              <span class="item-name">{{ row.name }}</span>
              <el-tag :type="row.is_bundle ? 'warning' : 'info'" size="small" effect="plain">
                {{ row.is_bundle ? '套装' : '单品' }}
              </el-tag>
            </div>
            <div class="item-meta">
              <span class="item-code">{{ row.code }}</span>
              <span v-if="row.category">{{ row.category }}</span>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="所属游戏" width="120">
        <template #default="{ row }">{{ gameNameMap[row.game_id] || '-' }}</template>
      </el-table-column>
      <el-table-column label="识别素材（可选）" min-width="230">
        <template #default="{ row }">
          <div class="recognition-panel">
            <div class="image-state">
              <span class="image-state-label">未选中</span>
              <el-image v-if="row.image" class="recognition-thumb" :src="row.image" :preview-src-list="[row.image]" fit="cover" preview-teleported />
              <div v-else class="image-placeholder">未上传</div>
            </div>
            <div class="image-state">
              <span class="image-state-label">选中</span>
              <el-image v-if="row.selected_image" class="recognition-thumb" :src="row.selected_image" :preview-src-list="[row.selected_image]" fit="cover" preview-teleported />
              <div v-else class="image-placeholder">未上传</div>
            </div>
            <el-tag :type="recognitionStateType(row)" size="small" effect="plain" class="recognition-count">
              {{ recognitionCount(row) }}/2
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="position" label="位置坐标" width="130">
        <template #default="{ row }">{{ row.position || '-' }}</template>
      </el-table-column>
      <el-table-column prop="price" label="参考价格" width="100" align="right" />
      <el-table-column prop="sort_order" label="排序" width="70" align="center" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="openItemDialog(row)">编辑</el-button>
          <el-popconfirm title="确认删除？" @confirm="handleDeleteItem(row.id)">
            <template #reference><el-button size="small" link type="danger">删除</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap" v-if="total > 0">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="fetchList" />
    </div>

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
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
.toolbar .el-button { margin-left: auto; }
.pagination-wrap { display: flex; justify-content: center; margin-top: 20px; }
.expand-area { padding: 12px 20px; }
.expand-title { font-weight: 600; margin-bottom: 8px; color: #606266; }
.item-identity { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.item-name-line { display: flex; align-items: center; gap: 8px; }
.item-name { color: #303133; font-weight: 600; line-height: 1.35; overflow-wrap: anywhere; }
.item-meta { display: flex; align-items: center; gap: 10px; color: #909399; font-size: 12px; }
.item-code { color: #606266; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.recognition-panel { display: flex; align-items: flex-end; gap: 8px; }
.image-state { display: flex; flex-direction: column; gap: 4px; }
.image-state-label { color: #909399; font-size: 11px; line-height: 1; text-align: center; }
.recognition-thumb,
.image-placeholder {
  width: 48px;
  height: 48px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  box-sizing: border-box;
}
.recognition-thumb { display: block; }
.image-placeholder {
  display: grid;
  place-items: center;
  background: #f5f7fa;
  color: #a8abb2;
  font-size: 11px;
}
.recognition-count { margin-bottom: 13px; font-variant-numeric: tabular-nums; }

@media (max-width: 900px) {
  .toolbar .el-button { margin-left: 0; }
}

/* 隐藏非套装行的展开图标 */
:deep(.hide-expand-icon .el-table__expand-icon) {
  visibility: hidden;
  pointer-events: none;
}
</style>
