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

    <el-table :data="list" border stripe v-loading="loading" row-key="id">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div v-if="row.is_bundle" class="expand-area">
            <div class="expand-title">套装子物品：</div>
            <el-table :data="row._children || []" border size="small" v-loading="row._childrenLoading">
              <el-table-column prop="code" label="编码" width="120" />
              <el-table-column prop="name" label="名称" min-width="150" />
              <el-table-column label="图片" width="80">
                <template #default="{ row: child }">
                  <el-image v-if="child.image" :src="child.image" :preview-src-list="[child.image]" style="width:40px;height:40px" fit="cover" />
                </template>
              </el-table-column>
              <el-table-column prop="price" label="价格" width="90" align="right" />
              <el-table-column label="操作" width="120">
                <template #default="{ row: child }">
                  <el-button size="small" link type="primary" @click="openItemDialog(child)">编辑</el-button>
                  <el-popconfirm title="确认删除？" @confirm="handleDeleteItem(child.id)">
                    <template #reference><el-button size="small" link type="danger">删除</el-button></template>
                  </el-popconfirm>
                </template>
              </el-table-column>
            </el-table>
            <el-button size="small" type="primary" style="margin-top:8px" @click="openChildSelect(row)">+ 选择已有物品</el-button>
          </div>
          <el-empty v-else description="非套装，无子物品" :image-size="40" />
        </template>
      </el-table-column>
      <el-table-column prop="code" label="编码" width="120" />
      <el-table-column prop="name" label="物品名称" min-width="150" />
      <el-table-column label="所属游戏" width="100">
        <template #default="{ row }">{{ gameNameMap[row.game_id] || '-' }}</template>
      </el-table-column>
      <el-table-column label="图片" width="80">
        <template #default="{ row }">
          <el-image v-if="row.image" :src="row.image" :preview-src-list="[row.image]" style="width:40px;height:40px" fit="cover" />
        </template>
      </el-table-column>
      <el-table-column label="类型" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_bundle ? 'warning' : 'info'" size="small">{{ row.is_bundle ? '套装' : '单品' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="category" label="分类" width="100" />
      <el-table-column prop="price" label="价格" width="90" align="right" />
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

    <div class="pagination-wrap" v-if="total > pageSize">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="fetchList" />
    </div>

    <!-- 物品编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑物品' : '新增物品'" width="550px" destroy-on-close>
      <el-form :model="form" label-width="90px" ref="formRef" :rules="rules">
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
            <el-radio :value="false">单品</el-radio>
            <el-radio :value="true">套装</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="form.category" placeholder="如：武器、防具" />
        </el-form-item>
        <el-form-item label="商品图片">
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
            <template #tip><div class="el-upload__tip">支持 jpg/png/gif/webp</div></template>
          </el-upload>
          <el-input v-if="form.image" v-model="form.image" placeholder="或直接输入URL" size="small" style="margin-top:6px" />
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
    <el-dialog v-model="childSelectVisible" title="选择已有物品加入套装" width="650px" destroy-on-close>
      <el-table :data="availableItems" border stripe size="small" @selection-change="onChildSelectionChange" ref="childTableRef">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="code" label="编码" width="130" />
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column label="图片" width="80">
          <template #default="{ row }">
            <el-image v-if="row.image" :src="row.image" :preview-src-list="[row.image]" style="width:40px;height:40px" fit="cover" />
          </template>
        </el-table-column>
        <el-table-column prop="price" label="价格" width="90" align="right" />
        <el-table-column prop="category" label="分类" width="100" />
      </el-table>
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
import { getAllGames, getGameItems, getAllItems, getBundleChildren, createGameItem, updateGameItem, deleteGameItem, uploadFile } from '../api'

const gameList = ref([])
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const filterGameId = ref(null)
const filterType = ref(null)
const loading = ref(false)

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

// 展开行时加载子物品
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
  game_id: null, name: '', code: '', image: '', is_bundle: false,
  category: '', price: 0, sort_order: 0, remark: '',
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

function handleImageChange(file) {
  imageFile.value = file.raw
  imageFileList.value = [file]
}

function handleImageRemove() {
  imageFile.value = null
  imageFileList.value = []
  form.image = ''
}

function openItemDialog(row = null, parentId = null) {
  isEdit.value = !!row
  editId.value = row?.id ?? null
  imageFile.value = null
  if (row?.image) {
    imageFileList.value = [{ name: row.image.split('/').pop() || 'item.png', url: row.image }]
  } else {
    imageFileList.value = []
  }
  const base = row ? { ...row, is_bundle: !!row.is_bundle } : { ...defaultForm(), game_id: filterGameId.value, code: genItemCode() }
  if (parentId) base.parent_id = parentId
  else if (!row) base.parent_id = null
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

// ── 套装子物品选择 ──
const childSelectVisible = ref(false)
const availableItems = ref([])
const selectedChildren = ref([])
const childSubmitting = ref(false)
const childTableRef = ref(null)
const currentBundleId = ref(null)

function onChildSelectionChange(selection) {
  selectedChildren.value = selection
}

async function openChildSelect(bundleRow) {
  currentBundleId.value = bundleRow.id
  selectedChildren.value = []
  // 加载同游戏下未被关联的单品物品
  availableItems.value = await getAllItems({ game_id: bundleRow.game_id, is_bundle: 0, no_parent: true })
  childSelectVisible.value = true
}

async function handleAddChildren() {
  if (selectedChildren.value.length === 0) {
    ElMessage.warning('请至少选择一个物品')
    return
  }
  childSubmitting.value = true
  try {
    for (const item of selectedChildren.value) {
      await updateGameItem(item.id, { parent_id: currentBundleId.value })
    }
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
</style>
