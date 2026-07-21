<template>
  <div class="page-container">
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索游戏名称..." clearable style="width: 220px" @input="handleSearch">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" @click="openGameDialog()">
        <el-icon><Plus /></el-icon> 新增游戏
      </el-button>
    </div>

    <el-table :data="list" border stripe v-loading="loading" highlight-current-row @current-change="onCurrentChange" row-key="id">
      <el-table-column prop="code" label="编码" width="120" />
      <el-table-column prop="name" label="游戏名称" min-width="150" />
      <el-table-column prop="platform" label="平台" width="100" />
      <el-table-column prop="trade_timeout_seconds" label="交易超时" width="100" align="center">
        <template #default="{ row }">{{ row.trade_timeout_seconds ?? 300 }} 秒</template>
      </el-table-column>
      <el-table-column prop="sort_order" label="排序" width="70" align="center" />
      <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip />
      <el-table-column label="操作" width="350" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openGameDialog(row)">编辑</el-button>
          <el-button size="small" type="success" @click="openRegionDialog(row)">大区</el-button>
          <el-button size="small" type="warning" @click="openScriptDrawer(row)">话术</el-button>
          <el-popconfirm title="确认删除？" @confirm="handleDeleteGame(row.id)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap" v-if="total > pageSize">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="fetchList" />
    </div>

    <!-- 游戏编辑弹窗 -->
    <el-dialog v-model="gameDialogVisible" :title="gameIsEdit ? '编辑游戏' : '新增游戏'" width="500px" destroy-on-close>
      <el-form :model="gameForm" label-width="80px" ref="gameFormRef" :rules="gameRules">
        <el-form-item label="游戏名称" prop="name">
          <el-input v-model="gameForm.name" placeholder="如：DNF" />
        </el-form-item>
        <el-form-item label="编码" prop="code">
          <el-input v-model="gameForm.code" placeholder="唯一编码，如 dnf" :disabled="gameIsEdit" />
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="gameForm.platform" placeholder="选择平台" clearable style="width:100%">
            <el-option label="PC" value="PC" />
            <el-option label="手游" value="手游" />
            <el-option label="主机" value="主机" />
          </el-select>
        </el-form-item>
        <el-form-item label="交易执行">
          <el-select v-model="gameForm.trade_type" placeholder="选择交易执行方式" style="width:100%">
            <el-option label="脚本" value="script" />
            <el-option label="Web" value="web" />
          </el-select>
        </el-form-item>
        <el-form-item label="交易超时">
          <el-input-number
            v-model="gameForm.trade_timeout_seconds"
            :min="30"
            :max="7200"
            :step="30"
            controls-position="right"
          />
          <span style="margin-left:8px;color:#909399">秒（等待买家交易申请）</span>
        </el-form-item>
        <el-form-item label="游戏图标">
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept="image/*"
            :on-change="handleGameIconChange"
            :on-remove="handleGameIconRemove"
            :file-list="gameIconFileList"
            list-type="picture"
          >
            <el-button size="small" type="primary">选择图片</el-button>
            <template #tip><div class="el-upload__tip">支持 jpg/png/gif/webp</div></template>
          </el-upload>
          <el-input v-if="gameForm.icon" v-model="gameForm.icon" placeholder="或直接输入URL" size="small" style="margin-top:6px" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="gameForm.sort_order" :min="0" :max="999" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="gameForm.remark" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="gameDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleGameSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 大区管理抽屉 -->
    <el-drawer v-model="regionDrawerVisible" :title="`大区管理 - ${currentGame?.name || ''}`" size="600px" destroy-on-close>
      <div class="region-toolbar">
        <el-button type="primary" size="small" @click="openRegionEdit()">
          <el-icon><Plus /></el-icon> 新增大区
        </el-button>
      </div>
      <el-table :data="regionList" border stripe size="small" highlight-current-row @current-change="onCurrentChange" row-key="id">
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name" label="大区名称" min-width="150" />
        <el-table-column label="选区坐标" width="100" align="center">
          <template #default="{ row }">
            {{ row.select_x != null && row.select_y != null ? `${row.select_x}, ${row.select_y}` : '未配置' }}
          </template>
        </el-table-column>
        <el-table-column prop="sort_order" label="排序" width="70" align="center" />
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openRegionEdit(row)">编辑</el-button>
            <el-button size="small" link type="success" @click="openRegionScriptEntry(row)">话术</el-button>
            <el-popconfirm title="确认删除？" @confirm="handleDeleteRegion(row.id)">
              <template #reference>
                <el-button size="small" link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 大区编辑弹窗 -->
      <el-dialog v-model="regionEditVisible" :title="regionIsEdit ? '编辑大区' : '新增大区'" width="520px" append-to-body destroy-on-close>
        <el-form :model="regionForm" label-width="80px" ref="regionFormRef" :rules="regionRules">
          <el-form-item label="大区名称" prop="name">
            <el-input v-model="regionForm.name" placeholder="如：华东一区" />
          </el-form-item>
          <el-form-item label="编码" prop="code">
            <el-input v-model="regionForm.code" placeholder="如 huadong_1" />
          </el-form-item>
          <el-form-item label="选区坐标">
            <div class="coordinate-inputs">
              <el-form-item prop="select_x">
                <el-input-number v-model="regionForm.select_x" :min="0" :max="799" :step="1" placeholder="X" />
              </el-form-item>
              <span>×</span>
              <el-form-item prop="select_y">
                <el-input-number v-model="regionForm.select_y" :min="0" :max="599" :step="1" placeholder="Y" />
              </el-form-item>
            </div>
          </el-form-item>
          <el-alert title="优先使用配置坐标；留空时由工作机 OCR 定位大区" type="info" :closable="false" show-icon />
          <el-form-item v-if="regionIsEdit" label="排序">
            <el-input-number v-model="regionForm.sort_order" :min="0" :max="999" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="regionEditVisible = false">取消</el-button>
          <el-button type="primary" :loading="regionSubmitting" @click="handleRegionSubmit">保存</el-button>
        </template>
      </el-dialog>
    </el-drawer>

    <!-- 话术管理抽屉（游戏话术 + 大区话术联动） -->
    <el-drawer v-model="scriptDrawerVisible" :title="`话术管理 - ${scriptGame?.name || ''}`" size="750px" destroy-on-close>
      <el-tabs v-model="scriptActiveTab">
        <!-- 游戏默认话术 -->
        <el-tab-pane label="游戏默认话术" name="game">
          <div class="region-toolbar">
            <el-button type="primary" size="small" @click="openScriptEdit()">
              <el-icon><Plus /></el-icon> 新增话术
            </el-button>
          </div>
          <el-table :data="gameScriptList" border stripe size="small" highlight-current-row @current-change="onCurrentChange" row-key="id">
            <el-table-column prop="title" label="标题" min-width="140" />
            <el-table-column prop="category" label="分类" width="100" />
            <el-table-column prop="content" label="内容" min-width="200" show-overflow-tooltip />
            <el-table-column label="图片" width="70">
              <template #default="{ row }">
                <el-image v-if="row.image_url" :src="row.image_url" :preview-src-list="[row.image_url]" style="width:36px;height:36px" fit="cover" />
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="sort_order" label="排序" width="60" align="center" />
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="openScriptEdit(row)">编辑</el-button>
                <el-popconfirm title="确认删除？" @confirm="handleDeleteScript(row.id)">
                  <template #reference><el-button size="small" link type="danger">删除</el-button></template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 大区话术 -->
        <el-tab-pane label="大区话术" name="region">
          <div class="region-toolbar" style="display:flex;gap:10px;align-items:center">
            <el-select v-model="scriptRegionId" placeholder="选择大区" style="width:180px" @change="fetchRegionScripts">
              <el-option v-for="r in regionList" :key="r.id" :label="r.name" :value="r.id" />
            </el-select>
            <el-button type="primary" size="small" @click="openRegionScriptEdit()" :disabled="!scriptRegionId">
              <el-icon><Plus /></el-icon> 新增大区话术
            </el-button>
          </div>
          <el-table :data="regionScriptList" border stripe size="small" highlight-current-row @current-change="onCurrentChange" row-key="id">
            <el-table-column prop="title" label="标题" min-width="130" />
            <el-table-column prop="category" label="分类" width="90" />
            <el-table-column prop="content" label="内容" min-width="160" show-overflow-tooltip />
            <el-table-column label="图片" width="80">
              <template #default="{ row }">
                <el-image v-if="row.image_url" :src="row.image_url" :preview-src-list="[row.image_url]" style="width:40px;height:40px" fit="cover" />
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="210">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="openRegionScriptEdit(row)">编辑</el-button>
                <el-button size="small" link type="success" @click="copyRegionScript(row)">复制</el-button>
                <el-popconfirm title="确认删除？" @confirm="handleDeleteRegionScript(row.id)">
                  <template #reference><el-button size="small" link type="danger">删除</el-button></template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>

      <!-- 游戏话术编辑弹窗 -->
      <el-dialog v-model="scriptEditVisible" :title="scriptIsEdit ? '编辑话术' : '新增话术'" width="500px" append-to-body destroy-on-close>
        <el-form :model="scriptForm" label-width="80px" ref="scriptFormRef" :rules="scriptRules">
          <el-form-item label="标题" prop="title">
            <el-input v-model="scriptForm.title" />
          </el-form-item>
          <el-form-item label="分类">
            <el-select v-model="scriptForm.category" placeholder="选择分类" clearable filterable allow-create style="width:100%">
              <el-option label="招呼" value="招呼" />
              <el-option label="促单" value="促单" />
              <el-option label="售后" value="售后" />
              <el-option label="其他" value="其他" />
            </el-select>
          </el-form-item>
          <el-form-item label="内容" prop="content">
            <el-input v-model="scriptForm.content" type="textarea" rows="4" placeholder="话术内容..." />
          </el-form-item>
          <el-form-item label="图片">
            <el-upload
              :auto-upload="false"
              :limit="1"
              accept="image/*"
              :on-change="handleScriptImageChange"
              :on-remove="handleScriptImageRemove"
              :file-list="scriptImageFileList"
              list-type="picture"
            >
              <el-button size="small" type="primary">选择图片</el-button>
              <template #tip><div class="el-upload__tip">支持 jpg/png/gif/webp</div></template>
            </el-upload>
            <el-input v-if="scriptForm.image_url" v-model="scriptForm.image_url" placeholder="或直接输入URL" size="small" style="margin-top:6px" />
          </el-form-item>
          <el-form-item label="排序">
            <el-input-number v-model="scriptForm.sort_order" :min="0" :max="999" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="scriptEditVisible = false">取消</el-button>
          <el-button type="primary" :loading="scriptSubmitting" @click="handleScriptSubmit">保存</el-button>
        </template>
      </el-dialog>

      <!-- 大区话术编辑弹窗 -->
      <el-dialog v-model="regionScriptEditVisible" :title="regionScriptIsEdit ? '编辑大区话术' : '新增大区话术'" width="500px" append-to-body destroy-on-close>
        <el-form :model="regionScriptForm" label-width="90px" ref="regionScriptFormRef" :rules="regionScriptRules">
          <el-form-item label="标题" prop="title">
            <el-input v-model="regionScriptForm.title" />
          </el-form-item>
          <el-form-item label="关联游戏话术">
            <el-select v-model="regionScriptForm.game_script_id" placeholder="可选，继承默认话术" clearable style="width:100%">
              <el-option v-for="s in gameScriptList" :key="s.id" :label="s.title" :value="s.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="分类">
            <el-select v-model="regionScriptForm.category" placeholder="选择分类" clearable filterable allow-create style="width:100%">
              <el-option label="招呼" value="招呼" />
              <el-option label="促单" value="促单" />
              <el-option label="售后" value="售后" />
              <el-option label="其他" value="其他" />
            </el-select>
          </el-form-item>
          <el-form-item label="内容" prop="content">
            <el-input v-model="regionScriptForm.content" type="textarea" rows="4" />
          </el-form-item>
          <el-form-item label="图片">
            <el-upload
              :auto-upload="false"
              :limit="1"
              accept="image/*"
              :on-change="handleRegionScriptImageChange"
              :on-remove="handleRegionScriptImageRemove"
              :file-list="regionScriptImageFileList"
              list-type="picture"
            >
              <el-button size="small" type="primary">选择图片</el-button>
              <template #tip><div class="el-upload__tip">支持 jpg/png/gif/webp</div></template>
            </el-upload>
            <el-input v-if="regionScriptForm.image_url" v-model="regionScriptForm.image_url" placeholder="或直接输入URL" size="small" style="margin-top:6px" />
          </el-form-item>
          <el-form-item label="排序">
            <el-input-number v-model="regionScriptForm.sort_order" :min="0" :max="999" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="regionScriptEditVisible = false">取消</el-button>
          <el-button type="primary" :loading="regionScriptSubmitting" @click="handleRegionScriptSubmit">保存</el-button>
        </template>
      </el-dialog>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getGames, createGame, updateGame, deleteGame, getGameRegions, createRegion, updateRegion, deleteRegion, getGameScripts, getAllGameScripts, createGameScript, updateGameScript, deleteGameScript, getRegionScripts, createRegionScript, updateRegionScript, deleteRegionScript, uploadFile } from '../api'

// ── 游戏列表 ──
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const loading = ref(false)

const currentRow = ref(null)
function onCurrentChange(row) { currentRow.value = row }

async function fetchList() {
  loading.value = true
  try {
    const res = await getGames({ page: page.value, page_size: pageSize, keyword: keyword.value })
    list.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function handleSearch() { page.value = 1; fetchList() }

// ── 游戏编辑 ──
const gameDialogVisible = ref(false)
const gameIsEdit = ref(false)
const editId = ref(null)
const submitting = ref(false)
const gameFormRef = ref(null)
const gameRules = {
  name: [{ required: true, message: '请输入游戏名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
}

const defaultGameForm = () => ({
  name: '', code: '', platform: '', trade_type: 'script',
  trade_timeout_seconds: 300, icon: '', sort_order: 0, remark: '',
})
const gameForm = reactive(defaultGameForm())

// 游戏图标上传
const gameIconFileList = ref([])
const gameIconFile = ref(null)

function handleGameIconChange(file) {
  gameIconFile.value = file.raw
  gameIconFileList.value = [file]
}

function handleGameIconRemove() {
  gameIconFile.value = null
  gameIconFileList.value = []
  gameForm.icon = ''
}

function openGameDialog(row = null) {
  gameIsEdit.value = !!row
  editId.value = row?.id ?? null
  gameIconFile.value = null
  if (row?.icon) {
    gameIconFileList.value = [{ name: row.icon.split('/').pop() || 'icon.png', url: row.icon }]
  } else {
    gameIconFileList.value = []
  }
  Object.assign(gameForm, row ? { ...row } : defaultGameForm())
  gameDialogVisible.value = true
}

async function handleGameSubmit() {
  await gameFormRef.value?.validate()
  submitting.value = true
  try {
    // 先上传图标文件
    if (gameIconFile.value) {
      const res = await uploadFile(gameIconFile.value)
      if (res.code === 0) gameForm.icon = res.url
    }
    if (gameIsEdit.value) {
      await updateGame(editId.value, { ...gameForm })
      ElMessage.success('更新成功')
    } else {
      await createGame({ ...gameForm })
      ElMessage.success('添加成功')
    }
    gameDialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

async function handleDeleteGame(id) {
  try {
    await deleteGame(id)
    ElMessage.success('已删除')
    fetchList()
  } catch (e) { ElMessage.error(e.message) }
}

// ── 大区管理（抽屉联动） ──
const regionDrawerVisible = ref(false)
const currentGame = ref(null)
const regionList = ref([])

async function openRegionDialog(game) {
  currentGame.value = game
  regionDrawerVisible.value = true
  await fetchRegions()
}

async function fetchRegions(game = null) {
  const g = game || currentGame.value
  if (!g) return
  try {
    const res = await getGameRegions({ game_id: g.id, page_size: 1000 })
    regionList.value = res.items
  } catch (e) {
    ElMessage.error('加载大区列表失败: ' + e.message)
  }
}

// ── 大区编辑 ──
const regionEditVisible = ref(false)
const regionIsEdit = ref(false)
const regionEditId = ref(null)
const regionSubmitting = ref(false)
const regionFormRef = ref(null)
const validateCoordinatePair = (_rule, _value, callback) => {
  const onlyOneProvided = (regionForm.select_x == null) !== (regionForm.select_y == null)
  if (onlyOneProvided) callback(new Error('X、Y 坐标必须同时填写或同时留空'))
  else callback()
}
const regionRules = {
  name: [{ required: true, message: '请输入大区名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  select_x: [{ validator: validateCoordinatePair, trigger: 'change' }],
  select_y: [{ validator: validateCoordinatePair, trigger: 'change' }],
}
const defaultRegionForm = () => ({ name: '', code: '', select_x: null, select_y: null })
const regionForm = reactive(defaultRegionForm())

// 生成随机大区编码（8位大写字母+数字，如 A3K9M7XQ）
function genRegionCode() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
  let code = ''
  for (let i = 0; i < 8; i++) {
    code += chars[Math.floor(Math.random() * chars.length)]
  }
  return code
}

function openRegionEdit(row = null) {
  regionIsEdit.value = !!row
  regionEditId.value = row?.id ?? null
  Object.assign(regionForm, row ? { ...row } : { ...defaultRegionForm(), code: genRegionCode() })
  regionEditVisible.value = true
}

async function handleRegionSubmit() {
  await regionFormRef.value?.validate()
  regionSubmitting.value = true
  try {
    if (regionIsEdit.value) {
      await updateRegion(regionEditId.value, { ...regionForm })
      ElMessage.success('更新成功')
    } else {
      const { sort_order, ...createPayload } = regionForm
      await createRegion({ ...createPayload, game_id: currentGame.value.id })
      ElMessage.success('添加成功')
    }
    regionEditVisible.value = false
    fetchRegions()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    regionSubmitting.value = false
  }
}

async function handleDeleteRegion(id) {
  try {
    await deleteRegion(id)
    ElMessage.success('已删除')
    fetchRegions()
  } catch (e) { ElMessage.error(e.message) }
}

// 从大区列表进入话术
async function openRegionScriptEntry(region) {
  scriptGame.value = currentGame.value
  scriptDrawerVisible.value = true
  scriptActiveTab.value = 'region'
  scriptRegionId.value = region.id
  await fetchGameScripts()
  await fetchRegionScripts()
}

// ── 话术管理（抽屉联动） ──
const scriptDrawerVisible = ref(false)
const scriptGame = ref(null)
const scriptActiveTab = ref('game')
const gameScriptList = ref([])
const regionScriptList = ref([])
const scriptRegionId = ref(null)

async function openScriptDrawer(game) {
  scriptGame.value = game
  currentGame.value = game
  scriptActiveTab.value = 'game'
  scriptRegionId.value = null
  regionScriptList.value = []
  scriptDrawerVisible.value = true
  // 加载大区和游戏话术
  await fetchRegions(game)
  await fetchGameScripts()
}

async function fetchGameScripts() {
  if (!scriptGame.value) return
  gameScriptList.value = await getAllGameScripts(scriptGame.value.id)
}

async function fetchRegionScripts() {
  if (!scriptRegionId.value) { regionScriptList.value = []; return }
  const res = await getRegionScripts({ region_id: scriptRegionId.value, page_size: 1000 })
  regionScriptList.value = res.items
}

// ── 游戏话术编辑 ──
const scriptEditVisible = ref(false)
const scriptIsEdit = ref(false)
const scriptEditId = ref(null)
const scriptSubmitting = ref(false)
const scriptFormRef = ref(null)
const scriptRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: false, message: '请输入内容', trigger: 'blur' }],
}
const defaultScriptForm = () => ({ title: '', content: '', image_url: '', category: '', sort_order: 0 })
const scriptForm = reactive(defaultScriptForm())

// 游戏话术图片上传
const scriptImageFileList = ref([])
const scriptImageFile = ref(null)

function handleScriptImageChange(file) {
  scriptImageFile.value = file.raw
  scriptImageFileList.value = [file]
}

function handleScriptImageRemove() {
  scriptImageFile.value = null
  scriptImageFileList.value = []
  scriptForm.image_url = ''
}

function openScriptEdit(row = null) {
  scriptIsEdit.value = !!row; scriptEditId.value = row?.id ?? null
  scriptImageFile.value = null
  if (row?.image_url) {
    scriptImageFileList.value = [{ name: row.image_url.split('/').pop() || 'image.png', url: row.image_url }]
  } else {
    scriptImageFileList.value = []
  }
  Object.assign(scriptForm, row ? { ...row } : defaultScriptForm())
  scriptEditVisible.value = true
}

async function handleScriptSubmit() {
  await scriptFormRef.value?.validate(); scriptSubmitting.value = true
  try {
    // 先上传图片文件
    if (scriptImageFile.value) {
      const res = await uploadFile(scriptImageFile.value)
      if (res.code === 0) scriptForm.image_url = res.url
    }
    if (scriptIsEdit.value) { await updateGameScript(scriptEditId.value, { ...scriptForm }); ElMessage.success('更新成功') }
    else { await createGameScript({ ...scriptForm, game_id: scriptGame.value.id }); ElMessage.success('添加成功') }
    scriptEditVisible.value = false; fetchGameScripts()
  } catch (e) { ElMessage.error(e.message) } finally { scriptSubmitting.value = false }
}

async function handleDeleteScript(id) {
  try { await deleteGameScript(id); ElMessage.success('已删除'); fetchGameScripts() } catch (e) { ElMessage.error(e.message) }
}

// ── 大区话术编辑 ──
const regionScriptEditVisible = ref(false)
const regionScriptIsEdit = ref(false)
const regionScriptEditId = ref(null)
const regionScriptSubmitting = ref(false)
const regionScriptFormRef = ref(null)
const regionScriptRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: false, message: '请输入内容', trigger: 'blur' }],
}
const defaultRegionScriptForm = () => ({ title: '', content: '', image_url: '', game_script_id: null, category: '', sort_order: 0 })
const regionScriptForm = reactive(defaultRegionScriptForm())

// 图片上传
const regionScriptImageFileList = ref([])
const regionScriptImageFile = ref(null)

function handleRegionScriptImageChange(file) {
  regionScriptImageFile.value = file.raw
  regionScriptImageFileList.value = [file]
}

function handleRegionScriptImageRemove() {
  regionScriptImageFile.value = null
  regionScriptImageFileList.value = []
  regionScriptForm.image_url = ''
}

function openRegionScriptEdit(row = null) {
  regionScriptIsEdit.value = !!row; regionScriptEditId.value = row?.id ?? null
  regionScriptImageFile.value = null
  if (row?.image_url) {
    regionScriptImageFileList.value = [{ name: row.image_url.split('/').pop() || 'image.png', url: row.image_url }]
  } else {
    regionScriptImageFileList.value = []
  }
  Object.assign(regionScriptForm, row ? { ...row } : defaultRegionScriptForm())
  regionScriptEditVisible.value = true
}

async function handleRegionScriptSubmit() {
  await regionScriptFormRef.value?.validate(); regionScriptSubmitting.value = true
  try {
    // 先上传图片文件
    if (regionScriptImageFile.value) {
      const res = await uploadFile(regionScriptImageFile.value)
      if (res.code === 0) regionScriptForm.image_url = res.url
    }
    if (regionScriptIsEdit.value) { await updateRegionScript(regionScriptEditId.value, { ...regionScriptForm }); ElMessage.success('更新成功') }
    else { await createRegionScript({ ...regionScriptForm, region_id: scriptRegionId.value }); ElMessage.success('添加成功') }
    regionScriptEditVisible.value = false; fetchRegionScripts()
  } catch (e) { ElMessage.error(e.message) } finally { regionScriptSubmitting.value = false }
}

async function handleDeleteRegionScript(id) {
  try { await deleteRegionScript(id); ElMessage.success('已删除'); fetchRegionScripts() } catch (e) { ElMessage.error(e.message) }
}

function copyRegionScript(row) {
  openRegionScriptEdit({ ...row, id: null })
  regionScriptIsEdit.value = false
}

onMounted(fetchList)
</script>

<style scoped>
.page-container { padding: 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; }
.toolbar .el-button { margin-left: auto; }
.pagination-wrap { display: flex; justify-content: center; margin-top: 20px; }
.region-toolbar { margin-bottom: 12px; }
.coordinate-inputs {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.coordinate-inputs .el-input-number { width: 120px; }
</style>
