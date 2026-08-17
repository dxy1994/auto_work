<template>
  <div class="control-page">
    <header class="control-header">
      <div>
        <div class="control-kicker">GLOBAL SETTINGS</div>
        <h1>系统控制</h1>
        <p>快速切换全局行为，需要时再展开查看影响范围。</p>
      </div>
      <div v-if="loaded" class="header-meta">
        <strong>2 项全局设置</strong>
        <span>最近保存 {{ formatTime(updatedAt) }}</span>
      </div>
    </header>

    <el-skeleton v-if="loading && !loaded" :rows="4" animated class="control-skeleton" />

    <el-result
      v-else-if="loadError && !loaded"
      icon="error"
      title="系统控制状态加载失败"
      :sub-title="loadError"
    >
      <template #extra>
        <el-button type="primary" :loading="loading" @click="loadControls">重新加载</el-button>
      </template>
    </el-result>

    <main v-else class="settings-board">
      <div class="settings-board__heading">
        <div>
          <span>CONTROL PANEL</span>
          <strong>全局控制项</strong>
        </div>
        <small>切换成功后立即保存，所有浏览器共享相同设置。</small>
      </div>

      <section class="control-item" :class="{ 'is-disabled': !autoTradeEnabled }">
        <div class="control-item__row">
          <span class="control-symbol control-symbol--trade" aria-hidden="true">
            <el-icon><Operation /></el-icon>
          </span>

          <div class="control-item__copy">
            <span class="control-item__eyebrow">运行控制</span>
            <h2>自动游戏交易</h2>
            <p>
              {{ autoTradeEnabled
                ? '允许新订单进入游戏交易排队和执行流程。'
                : '暂停新交易，订单监控和聊天仍继续运行。' }}
            </p>
            <button
              type="button"
              class="detail-toggle"
              :aria-expanded="tradeDetailsVisible"
              aria-controls="trade-control-details"
              @click="tradeDetailsVisible = !tradeDetailsVisible"
            >
              {{ tradeDetailsVisible ? '收起详情' : '查看运行链路与影响' }}
              <el-icon :class="{ expanded: tradeDetailsVisible }"><ArrowDown /></el-icon>
            </button>
          </div>

          <div class="control-item__action">
            <span class="setting-state" :class="{ active: autoTradeEnabled }">
              <i></i>{{ autoTradeEnabled ? '已开启' : '已关闭' }}
            </span>
            <el-switch
              :model-value="autoTradeEnabled"
              :loading="saving"
              :disabled="saving"
              size="large"
              aria-label="执行自动游戏交易"
              @change="changeAutoTrade"
            />
          </div>
        </div>

        <div
          v-show="tradeDetailsVisible"
          id="trade-control-details"
          class="control-item__detail"
        >
          <div class="detail-label">订单执行链路</div>
          <div class="pipeline" aria-label="自动交易执行链路">
            <div class="pipeline-node always-on">
              <span>01</span>
              <div><strong>订单监控</strong><small>持续运行</small></div>
            </div>
            <div class="pipeline-link"><i></i></div>
            <div class="pipeline-node always-on">
              <span>02</span>
              <div><strong>聊天招呼</strong><small>持续运行</small></div>
            </div>
            <div class="pipeline-link" :class="{ cut: !autoTradeEnabled }"><i></i></div>
            <div class="pipeline-node game-trade" :class="{ offline: !autoTradeEnabled }">
              <span>03</span>
              <div>
                <strong>游戏交易</strong>
                <small>{{ autoTradeEnabled ? '允许新任务' : '停止新任务' }}</small>
              </div>
            </div>
          </div>

          <div class="impact-grid">
            <article>
              <el-icon><ChatLineRound /></el-icon>
              <div><strong>订单与聊天不受影响</strong><p>平台监控和招呼消息照常运行。</p></div>
            </article>
            <article>
              <el-icon><Timer /></el-icon>
              <div><strong>排队订单原地等待</strong><p>重新开启后在下一轮扫描继续。</p></div>
            </article>
            <article>
              <el-icon><VideoPlay /></el-icon>
              <div><strong>执行中任务不中断</strong><p>已经启动的交易会继续完成。</p></div>
            </article>
          </div>

          <el-alert
            v-if="!autoTradeEnabled"
            title="招呼已完成但尚未进入队列的订单，重新开启后可能需要在订单页点击重试。"
            type="warning"
            :closable="false"
            show-icon
          />
        </div>
      </section>

      <section class="control-item">
        <div class="control-item__row">
          <span class="control-symbol control-symbol--guide" aria-hidden="true">i</span>

          <div class="control-item__copy">
            <span class="control-item__eyebrow">界面偏好</span>
            <h2>展示页面说明</h2>
            <p>
              {{ pageGuidesVisible
                ? '业务页面顶部显示默认折叠的详细操作手册。'
                : '隐藏说明入口，不影响页面功能和业务数据。' }}
            </p>
            <button
              type="button"
              class="detail-toggle"
              :aria-expanded="guideDetailsVisible"
              aria-controls="guide-control-details"
              @click="guideDetailsVisible = !guideDetailsVisible"
            >
              {{ guideDetailsVisible ? '收起详情' : '查看展示范围与同步规则' }}
              <el-icon :class="{ expanded: guideDetailsVisible }"><ArrowDown /></el-icon>
            </button>
          </div>

          <div class="control-item__action">
            <span class="setting-state" :class="{ active: pageGuidesVisible }">
              <i></i>{{ pageGuidesVisible ? '已展示' : '已隐藏' }}
            </span>
            <el-switch
              :model-value="pageGuidesVisible"
              :loading="saving"
              :disabled="saving"
              size="large"
              aria-label="展示页面说明"
              @change="changePageGuidesVisibility"
            />
          </div>
        </div>

        <div
          v-show="guideDetailsVisible"
          id="guide-control-details"
          class="control-item__detail control-item__detail--guide"
        >
          <div class="preference-facts">
            <article>
              <strong>展示范围</strong>
              <p>覆盖全部业务页面，包括当前系统控制页面。</p>
            </article>
            <article>
              <strong>默认状态</strong>
              <p>说明入口默认折叠，只有点击后才展开完整手册。</p>
            </article>
            <article>
              <strong>同步方式</strong>
              <p>这是系统级设置，其他浏览器刷新后会读取相同状态。</p>
            </article>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSystemControlStore } from '../stores/systemControls'

const saving = ref(false)
const tradeDetailsVisible = ref(false)
const guideDetailsVisible = ref(false)
const systemControls = useSystemControlStore()
const {
  loading,
  loaded,
  loadError,
  autoTradeEnabled,
  pageGuidesVisible,
  updatedAt,
} = storeToRefs(systemControls)

async function loadControls() {
  await systemControls.load(true)
}

async function changeAutoTrade(nextEnabled) {
  if (saving.value) return
  if (!nextEnabled) {
    try {
      await ElMessageBox.confirm(
        '关闭后不会再排队或启动新的游戏交易，已经执行中的交易不会被终止。确认关闭？',
        '关闭自动游戏交易',
        {
          confirmButtonText: '确认关闭',
          cancelButtonText: '保持开启',
          type: 'warning',
        },
      )
    } catch {
      return
    }
  }

  saving.value = true
  try {
    await systemControls.update({
      auto_game_trade_enabled: nextEnabled,
    })
    ElMessage.success(nextEnabled ? '自动游戏交易已开启' : '自动游戏交易已关闭')
  } catch (error) {
    ElMessage.error(error.message || '系统控制更新失败')
  } finally {
    saving.value = false
  }
}

async function changePageGuidesVisibility(nextVisible) {
  if (saving.value) return
  saving.value = true
  try {
    await systemControls.update({
      page_guides_visible: nextVisible,
    })
    ElMessage.success(nextVisible ? '页面说明已展示' : '页面说明已隐藏')
  } catch (error) {
    ElMessage.error(error.message || '页面说明设置更新失败')
  } finally {
    saving.value = false
  }
}

function formatTime(value) {
  if (!value) return '尚无记录'
  return String(value).replace('T', ' ').slice(0, 19)
}

onMounted(loadControls)
</script>

<style scoped>
.control-page {
  --ink: #172033;
  --muted: #667085;
  --line: #d9e1ec;
  --blue: #2563eb;
  --green: #16a34a;
  --amber: #d97706;
  max-width: 1040px;
  height: 100%;
  margin: 0 auto;
  overflow-y: auto;
  overscroll-behavior: contain;
  color: var(--ink);
  font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
}

.control-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 14px 4px 22px;
}

.control-kicker,
.control-item__eyebrow,
.detail-label,
.settings-board__heading > div > span {
  color: var(--blue);
  font-family: "JetBrains Mono", Consolas, monospace;
  font-weight: 700;
  letter-spacing: .12em;
}

.control-kicker { font-size: 11px; }
.control-header h1 {
  margin: 5px 0 3px;
  font-size: clamp(30px, 4vw, 40px);
  line-height: 1.08;
  letter-spacing: -.04em;
}
.control-header p { margin: 0; color: var(--muted); font-size: 14px; line-height: 1.6; }

.header-meta { display: grid; justify-items: end; gap: 4px; }
.header-meta strong { font-size: 13px; }
.header-meta span {
  color: #98a2b3;
  font: 500 10px/1.5 "JetBrains Mono", Consolas, monospace;
}

.control-skeleton,
.settings-board {
  border: 1px solid var(--line);
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 12px 34px rgba(31, 42, 68, .07);
}
.control-skeleton { padding: 30px; }
.settings-board { overflow: hidden; }

.settings-board__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 15px 24px;
  border-bottom: 1px solid var(--line);
  background: #f8fafc;
}
.settings-board__heading > div { display: flex; align-items: baseline; gap: 10px; }
.settings-board__heading > div > span { font-size: 9px; }
.settings-board__heading strong { font-size: 15px; }
.settings-board__heading small { color: var(--muted); font-size: 11px; }

.control-item + .control-item { border-top: 1px solid var(--line); }
.control-item__row {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  padding: 21px 24px;
}

.control-symbol {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  color: var(--blue);
  border: 1px solid #bed1f7;
  background: #eef4ff;
  box-shadow: 0 5px 12px rgba(37, 99, 235, .1);
}
.control-symbol--trade { border-radius: 50%; font-size: 20px; }
.control-symbol--guide {
  height: 48px;
  border: 0;
  border-radius: 6px 6px 11px 11px;
  background: var(--blue);
  color: #fff;
  font: 700 20px/1 Georgia, serif;
}
.is-disabled .control-symbol--trade { border-color: #e6c9ab; background: #fff7ed; color: var(--amber); }

.control-item__eyebrow { display: block; margin-bottom: 3px; font-size: 9px; }
.control-item__copy h2 { margin: 0 0 4px; font-size: 18px; letter-spacing: -.02em; }
.control-item__copy p { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.55; }

.detail-toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-top: 7px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--blue);
  cursor: pointer;
  font: 600 12px/1.5 inherit;
}
.detail-toggle:hover { color: #174cb7; }
.detail-toggle:focus-visible { outline: 2px solid rgba(37, 99, 235, .35); outline-offset: 3px; border-radius: 3px; }
.detail-toggle .el-icon { transition: transform .18s ease; }
.detail-toggle .el-icon.expanded { transform: rotate(180deg); }

.control-item__action {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 13px;
  border: 1px solid #e1e7ef;
  border-radius: 11px;
  background: #f8fafc;
}
.setting-state {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 52px;
  color: #8a5a25;
  font-size: 12px;
  font-weight: 700;
}
.setting-state i { width: 7px; height: 7px; border-radius: 50%; background: var(--amber); }
.setting-state.active { color: #147b32; }
.setting-state.active i { background: var(--green); }

.control-item__detail {
  padding: 20px 24px 24px 88px;
  border-top: 1px solid #e5eaf1;
  background: #f8fafc;
}
.detail-label { margin-bottom: 12px; font-size: 9px; }

.pipeline {
  display: grid;
  grid-template-columns: minmax(150px, 1fr) 50px minmax(150px, 1fr) 50px minmax(150px, 1fr);
  align-items: center;
}
.pipeline-node {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 64px;
  padding: 11px 13px;
  border: 1px solid #bdd8c5;
  border-radius: 9px;
  background: #fff;
  box-shadow: inset 3px 0 0 var(--green);
}
.pipeline-node.game-trade { border-color: #b9cff8; box-shadow: inset 3px 0 0 var(--blue); }
.pipeline-node.offline { border-color: #e5c6a8; box-shadow: inset 3px 0 0 var(--amber); }
.pipeline-node > span { color: #98a2b3; font: 700 10px/1.4 Consolas, monospace; }
.pipeline-node strong, .pipeline-node small { display: block; }
.pipeline-node strong { margin-bottom: 3px; font-size: 14px; }
.pipeline-node small { color: var(--green); font-size: 11px; }
.pipeline-node.game-trade small { color: var(--blue); }
.pipeline-node.offline small { color: var(--amber); }

.pipeline-link { position: relative; height: 2px; background: #7bc18e; }
.pipeline-link::after {
  position: absolute;
  top: -4px;
  right: -1px;
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-left: 7px solid #7bc18e;
  content: "";
}
.pipeline-link.cut { background: repeating-linear-gradient(90deg, #d1a06e 0 8px, transparent 8px 14px); }
.pipeline-link.cut::after { border-left-color: #d1a06e; }

.impact-grid,
.preference-facts {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 14px;
}
.impact-grid article,
.preference-facts article {
  display: flex;
  gap: 9px;
  padding: 12px;
  border: 1px solid #e1e7ef;
  border-radius: 8px;
  background: #fff;
}
.impact-grid .el-icon { flex: 0 0 auto; margin-top: 2px; color: var(--blue); }
.impact-grid strong,
.preference-facts strong { display: block; margin-bottom: 3px; font-size: 12px; }
.impact-grid p,
.preference-facts p { margin: 0; color: var(--muted); font-size: 11px; line-height: 1.55; }
.control-item__detail .el-alert { margin-top: 12px; }
.control-item__detail--guide { padding-top: 6px; }
.preference-facts { margin-top: 0; }
.preference-facts article { display: block; }

@media (max-width: 760px) {
  .control-item__row { grid-template-columns: 44px minmax(0, 1fr); }
  .control-item__action { grid-column: 1 / -1; justify-content: space-between; }
  .control-item__detail { padding-left: 24px; }
  .pipeline { grid-template-columns: 1fr; }
  .pipeline-link { width: 2px; height: 24px; margin-left: 31px; }
  .pipeline-link::after {
    top: auto;
    right: -4px;
    bottom: -1px;
    border-top: 7px solid #7bc18e;
    border-right: 5px solid transparent;
    border-bottom: 0;
    border-left: 5px solid transparent;
  }
  .pipeline-link.cut { background: repeating-linear-gradient(#d1a06e 0 8px, transparent 8px 14px); }
  .pipeline-link.cut::after { border-top-color: #d1a06e; border-left-color: transparent; }
  .impact-grid, .preference-facts { grid-template-columns: 1fr; }
}

@media (max-width: 600px) {
  .control-header, .settings-board__heading { align-items: flex-start; flex-direction: column; }
  .header-meta { justify-items: start; }
  .settings-board__heading { display: flex; }
  .control-item__row, .control-item__detail { padding-right: 17px; padding-left: 17px; }
}

@media (prefers-reduced-motion: reduce) {
  .detail-toggle .el-icon { transition: none; }
}
</style>
