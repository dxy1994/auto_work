<template>
  <div class="control-page">
    <header class="control-header">
      <div>
        <div class="control-kicker">CONTROL / AUTO TRADE</div>
        <h1>系统控制</h1>
        <p>控制中控是否继续发起新的游戏内自动交易。</p>
      </div>
      <div v-if="loaded" class="header-state" :class="{ active: autoTradeEnabled }">
        <span class="state-light"></span>
        {{ autoTradeEnabled ? '自动交易已接通' : '自动交易已切断' }}
      </div>
    </header>

    <el-skeleton v-if="loading && !loaded" :rows="6" animated class="control-skeleton" />

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

    <main v-else class="control-board" :class="{ disabled: !autoTradeEnabled }">
      <section class="pipeline-panel" aria-label="自动交易执行链路">
        <div class="panel-label">订单执行链路</div>
        <div class="pipeline">
          <div class="pipeline-node always-on">
            <span class="node-index">01</span>
            <div>
              <strong>订单监控</strong>
              <small>持续运行</small>
            </div>
          </div>
          <div class="pipeline-link"><i></i></div>
          <div class="pipeline-node always-on">
            <span class="node-index">02</span>
            <div>
              <strong>聊天招呼</strong>
              <small>持续运行</small>
            </div>
          </div>
          <div class="pipeline-link" :class="{ cut: !autoTradeEnabled }"><i></i></div>
          <div class="pipeline-node game-trade" :class="{ offline: !autoTradeEnabled }">
            <span class="node-index">03</span>
            <div>
              <strong>游戏交易</strong>
              <small>{{ autoTradeEnabled ? '允许新任务' : '停止新任务' }}</small>
            </div>
          </div>
        </div>
      </section>

      <section class="switch-panel">
        <div class="switch-copy">
          <div class="switch-title-row">
            <span class="signal-disc"><i></i></span>
            <div>
              <h2>执行自动游戏交易</h2>
              <p>
                {{ autoTradeEnabled
                  ? '新订单可以进入游戏交易排队和执行流程。'
                  : '新订单不会排队或下发游戏交易任务。' }}
              </p>
            </div>
          </div>
          <div class="update-time">
            最近更新：{{ formatTime(updatedAt) }}
          </div>
        </div>

        <div class="switch-action">
          <span>{{ autoTradeEnabled ? '开启' : '关闭' }}</span>
          <el-switch
            :model-value="autoTradeEnabled"
            :loading="saving"
            :disabled="saving"
            size="large"
            aria-label="执行自动游戏交易"
            @change="changeAutoTrade"
          />
        </div>
      </section>

      <section class="impact-panel">
        <div class="panel-label">切换影响</div>
        <div class="impact-grid">
          <article>
            <el-icon><ChatLineRound /></el-icon>
            <div>
              <strong>订单与聊天不受影响</strong>
              <p>订单监控继续采集，平台聊天和招呼消息照常发送。</p>
            </div>
          </article>
          <article>
            <el-icon><Timer /></el-icon>
            <div>
              <strong>排队订单原地等待</strong>
              <p>关闭期间不唤醒队首；重新开启后，系统会在下一轮扫描中继续处理。</p>
            </div>
          </article>
          <article>
            <el-icon><VideoPlay /></el-icon>
            <div>
              <strong>执行中任务不中断</strong>
              <p>已经启动的游戏交易继续完成；尚未启动的新指派会被阻止。</p>
            </div>
          </article>
        </div>
        <el-alert
          v-if="!autoTradeEnabled"
          title="招呼已完成但尚未进入队列的订单，需要重新开启后在订单页点击重试。"
          type="warning"
          :closable="false"
          show-icon
        />
      </section>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSystemControls, updateSystemControls } from '../api'

const loading = ref(false)
const saving = ref(false)
const loaded = ref(false)
const loadError = ref('')
const autoTradeEnabled = ref(false)
const updatedAt = ref(null)

async function loadControls() {
  loading.value = true
  loadError.value = ''
  try {
    const response = await getSystemControls()
    autoTradeEnabled.value = Boolean(response.auto_game_trade_enabled)
    updatedAt.value = response.updated_at
    loaded.value = true
  } catch (error) {
    loadError.value = error.message || '无法连接中控后端'
  } finally {
    loading.value = false
  }
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
    const response = await updateSystemControls({
      auto_game_trade_enabled: nextEnabled,
    })
    autoTradeEnabled.value = Boolean(response.auto_game_trade_enabled)
    updatedAt.value = response.updated_at
    ElMessage.success(nextEnabled ? '自动游戏交易已开启' : '自动游戏交易已关闭')
  } catch (error) {
    ElMessage.error(error.message || '系统控制更新失败')
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
  --panel: #ffffff;
  --blue: #2563eb;
  --green: #16a34a;
  --amber: #d97706;
  max-width: 1180px;
  margin: 0 auto;
  color: var(--ink);
  font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
}

.control-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 18px 4px 28px;
}

.control-kicker,
.panel-label,
.node-index {
  font-family: "JetBrains Mono", Consolas, monospace;
  letter-spacing: .12em;
}

.control-kicker {
  color: var(--blue);
  font-size: 12px;
  font-weight: 700;
}

.control-header h1 {
  margin: 7px 0 4px;
  font-size: clamp(30px, 4vw, 44px);
  line-height: 1.08;
  letter-spacing: -.04em;
}

.control-header p {
  margin: 0;
  color: var(--muted);
  line-height: 1.7;
}

.header-state {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 14px;
  border: 1px solid #f0c9a3;
  border-radius: 999px;
  background: #fff8ef;
  color: #9a4c0b;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}

.header-state.active {
  border-color: #a7dab6;
  background: #f0fbf3;
  color: #147b32;
}

.state-light {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--amber);
  box-shadow: 0 0 0 4px rgba(217, 119, 6, .12);
}

.header-state.active .state-light {
  background: var(--green);
  box-shadow: 0 0 0 4px rgba(22, 163, 74, .12);
}

.control-skeleton,
.control-board {
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--panel);
  box-shadow: 0 16px 40px rgba(31, 42, 68, .07);
}

.control-skeleton {
  padding: 36px;
}

.control-board {
  overflow: hidden;
}

.pipeline-panel,
.switch-panel,
.impact-panel {
  padding: 28px 32px;
}

.panel-label {
  margin-bottom: 20px;
  color: #8490a4;
  font-size: 11px;
  font-weight: 700;
}

.pipeline-panel {
  border-bottom: 1px solid var(--line);
  background-color: #f8fafc;
  background-image:
    linear-gradient(#e9eef5 1px, transparent 1px),
    linear-gradient(90deg, #e9eef5 1px, transparent 1px);
  background-size: 24px 24px;
}

.pipeline {
  display: grid;
  grid-template-columns: minmax(170px, 1fr) 76px minmax(170px, 1fr) 76px minmax(170px, 1fr);
  align-items: center;
}

.pipeline-node {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 84px;
  padding: 16px 18px;
  border: 1px solid #bdd8c5;
  border-radius: 12px;
  background: #fff;
  box-shadow: inset 4px 0 0 var(--green);
}

.pipeline-node.game-trade {
  border-color: #b9cff8;
  box-shadow: inset 4px 0 0 var(--blue);
}

.pipeline-node.offline {
  border-color: #e5c6a8;
  box-shadow: inset 4px 0 0 var(--amber);
}

.node-index {
  color: #98a2b3;
  font-size: 12px;
}

.pipeline-node strong,
.pipeline-node small {
  display: block;
}

.pipeline-node strong {
  margin-bottom: 6px;
  font-size: 16px;
}

.pipeline-node small {
  color: var(--green);
  font-size: 12px;
}

.pipeline-node.game-trade small {
  color: var(--blue);
}

.pipeline-node.offline small {
  color: var(--amber);
}

.pipeline-link {
  position: relative;
  height: 2px;
  background: #7bc18e;
}

.pipeline-link::after {
  content: "";
  position: absolute;
  top: -4px;
  right: -1px;
  width: 0;
  height: 0;
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-left: 7px solid #7bc18e;
}

.pipeline-link.cut {
  background: repeating-linear-gradient(90deg, #d1a06e 0 8px, transparent 8px 14px);
}

.pipeline-link.cut::after {
  border-left-color: #d1a06e;
}

.switch-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  border-bottom: 1px solid var(--line);
}

.switch-title-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.signal-disc {
  display: grid;
  place-items: center;
  flex: 0 0 46px;
  width: 46px;
  height: 46px;
  border: 1px solid #b9cff8;
  border-radius: 50%;
  background: #eef4ff;
}

.signal-disc i {
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: var(--blue);
  box-shadow: 0 0 0 6px rgba(37, 99, 235, .12);
}

.disabled .signal-disc {
  border-color: #e5c6a8;
  background: #fff7ed;
}

.disabled .signal-disc i {
  background: var(--amber);
  box-shadow: 0 0 0 6px rgba(217, 119, 6, .12);
}

.switch-panel h2 {
  margin: 0 0 7px;
  font-size: 21px;
  letter-spacing: -.02em;
}

.switch-panel p {
  margin: 0;
  color: var(--muted);
  line-height: 1.6;
}

.update-time {
  margin: 14px 0 0 62px;
  color: #98a2b3;
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 11px;
}

.switch-action {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 13px 16px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #f8fafc;
}

.switch-action > span {
  min-width: 28px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 700;
}

.impact-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.impact-grid article {
  display: flex;
  gap: 12px;
  min-height: 116px;
  padding: 17px;
  border: 1px solid #e4e9f1;
  border-radius: 12px;
}

.impact-grid .el-icon {
  flex: 0 0 auto;
  margin-top: 2px;
  color: var(--blue);
  font-size: 20px;
}

.impact-grid strong {
  display: block;
  margin-bottom: 7px;
  font-size: 14px;
}

.impact-grid p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.65;
}

.impact-panel .el-alert {
  margin-top: 18px;
}

@media (max-width: 900px) {
  .pipeline {
    grid-template-columns: 1fr;
  }

  .pipeline-link {
    width: 2px;
    height: 34px;
    margin-left: 42px;
  }

  .pipeline-link::after {
    top: auto;
    right: -4px;
    bottom: -1px;
    border-top: 7px solid #7bc18e;
    border-right: 5px solid transparent;
    border-bottom: 0;
    border-left: 5px solid transparent;
  }

  .pipeline-link.cut {
    background: repeating-linear-gradient(#d1a06e 0 8px, transparent 8px 14px);
  }

  .pipeline-link.cut::after {
    border-top-color: #d1a06e;
    border-left-color: transparent;
  }

  .impact-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .control-header,
  .switch-panel {
    align-items: stretch;
    flex-direction: column;
  }

  .pipeline-panel,
  .switch-panel,
  .impact-panel {
    padding: 22px 18px;
  }

  .switch-action {
    justify-content: space-between;
  }

  .update-time {
    margin-left: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .control-page *,
  .control-page *::before,
  .control-page *::after {
    transition: none !important;
  }
}
</style>
