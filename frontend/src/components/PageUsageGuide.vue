<template>
  <details class="page-usage-guide">
    <summary class="page-usage-guide__summary">
      <span class="page-usage-guide__mark" aria-hidden="true">i</span>
      <span class="page-usage-guide__heading">
        <span class="page-usage-guide__eyebrow">PAGE GUIDE · 使用说明</span>
        <strong>{{ title }} · 使用说明</strong>
        <span class="page-usage-guide__summary-text">{{ guide.summary }}</span>
      </span>
      <span class="page-usage-guide__toggle" aria-hidden="true">
        <span class="when-open">收起说明</span>
        <span class="when-closed">展开说明</span>
        <span class="page-usage-guide__chevron">⌄</span>
      </span>
    </summary>

    <div class="page-usage-guide__body">
      <div class="page-usage-guide__main">
        <section class="page-usage-guide__scope" aria-label="页面功能范围">
          <div class="page-usage-guide__section-title">
            <span>01 · SCOPE</span>
            <strong>本页能做什么</strong>
          </div>
          <ul>
            <li v-for="item in guide.scope" :key="item">{{ item }}</li>
          </ul>
        </section>

        <section class="page-usage-guide__steps" aria-label="推荐操作顺序">
          <div class="page-usage-guide__section-title">
            <span>02 · WORKFLOW</span>
            <strong>按这个顺序操作</strong>
          </div>
          <ol>
            <li v-for="(step, index) in guide.steps" :key="step">
              <span>{{ String(index + 1).padStart(2, '0') }}</span>
              <p>{{ step }}</p>
            </li>
          </ol>
        </section>
      </div>

      <div class="page-usage-guide__reference">
        <section class="page-usage-guide__concepts" aria-label="关键字段和状态说明">
          <div class="page-usage-guide__section-title">
            <span>03 · REFERENCE</span>
            <strong>关键字段与状态</strong>
          </div>
          <dl>
            <div v-for="item in guide.concepts" :key="item.name">
              <dt>{{ item.name }}</dt>
              <dd>{{ item.detail }}</dd>
            </div>
          </dl>
        </section>

        <section class="page-usage-guide__troubleshooting" aria-label="常见问题排查">
          <div class="page-usage-guide__section-title">
            <span>04 · CHECK</span>
            <strong>遇到问题先检查</strong>
          </div>
          <ul>
            <li v-for="item in guide.troubleshooting" :key="item">{{ item }}</li>
          </ul>
        </section>

        <aside class="page-usage-guide__tips" aria-label="使用注意事项">
          <div class="page-usage-guide__section-title">
            <span>05 · CAUTION</span>
            <strong>重要提醒</strong>
          </div>
          <ul>
            <li v-for="tip in guide.tips" :key="tip">{{ tip }}</li>
          </ul>
        </aside>
      </div>
    </div>
  </details>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    required: true,
  },
  guide: {
    type: Object,
    required: true,
  },
})
</script>

<style scoped>
.page-usage-guide {
  --guide-ink: #203047;
  --guide-blue: #2f6fed;
  --guide-blue-soft: #edf4ff;
  --guide-line: #cbdaf4;
  --guide-muted: #64748b;
  position: relative;
  margin: 0 0 18px;
  overflow: hidden;
  border: 1px solid var(--guide-line);
  border-left: 5px solid var(--guide-blue);
  border-radius: 10px;
  background: linear-gradient(105deg, #f9fbff 0%, #fff 72%);
  box-shadow: 0 5px 18px rgba(45, 80, 140, .07);
}

.page-usage-guide__summary {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  min-height: 78px;
  padding: 13px 16px 13px 14px;
  color: var(--guide-ink);
  cursor: pointer;
  list-style: none;
}

.page-usage-guide__summary::-webkit-details-marker { display: none; }
.page-usage-guide__summary:focus-visible {
  outline: 3px solid rgba(47, 111, 237, .28);
  outline-offset: -3px;
}
.page-usage-guide__summary:hover { background: rgba(237, 244, 255, .55); }

.page-usage-guide__mark {
  display: grid;
  place-items: center;
  width: 32px;
  height: 40px;
  color: #fff;
  border-radius: 5px 5px 9px 9px;
  background: var(--guide-blue);
  font: 700 18px/1 Georgia, serif;
  box-shadow: 0 5px 12px rgba(47, 111, 237, .25);
}

.page-usage-guide__heading {
  display: grid;
  min-width: 0;
  gap: 3px;
}
.page-usage-guide__heading strong { font-size: 16px; letter-spacing: .01em; }
.page-usage-guide__eyebrow {
  color: var(--guide-blue);
  font: 700 10px/1.3 Consolas, "SFMono-Regular", monospace;
  letter-spacing: .12em;
}
.page-usage-guide__summary-text {
  overflow: hidden;
  color: var(--guide-muted);
  font-size: 13px;
  line-height: 1.55;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.page-usage-guide__toggle {
  display: flex;
  gap: 7px;
  align-items: center;
  color: var(--guide-muted);
  font-size: 12px;
}
.page-usage-guide__chevron {
  display: inline-block;
  color: var(--guide-blue);
  font-size: 19px;
  transition: transform .18s ease;
}
.page-usage-guide:not([open]) .when-open,
.page-usage-guide[open] .when-closed { display: none; }
.page-usage-guide[open] .page-usage-guide__chevron { transform: rotate(180deg); }

.page-usage-guide__body {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(310px, .9fr);
  gap: 22px;
  padding: 2px 18px 18px 62px;
}
.page-usage-guide__main,
.page-usage-guide__reference { display: grid; align-content: start; gap: 18px; }
.page-usage-guide__section-title {
  display: flex;
  align-items: baseline;
  gap: 9px;
  margin-bottom: 10px;
}
.page-usage-guide__section-title span {
  color: var(--guide-blue);
  font: 700 10px/1.4 Consolas, "SFMono-Regular", monospace;
  letter-spacing: .08em;
}
.page-usage-guide__section-title strong { color: var(--guide-ink); font-size: 13px; }
.page-usage-guide__scope ul,
.page-usage-guide__steps ol,
.page-usage-guide__troubleshooting ul,
.page-usage-guide__tips ul { padding: 0; margin: 0; list-style: none; }
.page-usage-guide__scope ul { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 14px; }
.page-usage-guide__scope li {
  position: relative;
  padding: 9px 11px 9px 26px;
  border: 1px solid #e2eaf7;
  border-radius: 7px;
  background: #fff;
  color: #40516a;
  font-size: 12px;
  line-height: 1.55;
}
.page-usage-guide__scope li::before {
  position: absolute;
  top: 14px;
  left: 11px;
  width: 6px;
  height: 6px;
  border: 2px solid var(--guide-blue);
  border-radius: 2px;
  content: "";
}
.page-usage-guide__steps ol { display: grid; gap: 7px; }
.page-usage-guide__steps li { display: grid; grid-template-columns: 26px 1fr; gap: 8px; align-items: start; }
.page-usage-guide__steps li > span {
  padding-top: 2px;
  color: var(--guide-blue);
  font: 700 11px/1.5 Consolas, "SFMono-Regular", monospace;
}
.page-usage-guide__steps p { margin: 0; color: #40516a; font-size: 13px; line-height: 1.55; }
.page-usage-guide__concepts dl { display: grid; gap: 1px; margin: 0; overflow: hidden; border: 1px solid #e2e8f0; border-radius: 8px; background: #e2e8f0; }
.page-usage-guide__concepts dl > div { padding: 9px 11px; background: #fff; }
.page-usage-guide__concepts dt { margin-bottom: 3px; color: var(--guide-ink); font-size: 12px; font-weight: 700; }
.page-usage-guide__concepts dd { margin: 0; color: var(--guide-muted); font-size: 11px; line-height: 1.55; }
.page-usage-guide__troubleshooting,
.page-usage-guide__tips {
  padding: 11px 13px;
  border-radius: 8px;
}
.page-usage-guide__troubleshooting { border: 1px solid #f0dfbd; background: #fffaf0; }
.page-usage-guide__tips { border: 1px solid #e4ebf6;
  background: var(--guide-blue-soft);
}
.page-usage-guide__troubleshooting ul,
.page-usage-guide__tips ul { display: grid; gap: 7px; }
.page-usage-guide__troubleshooting li,
.page-usage-guide__tips li {
  position: relative;
  padding-left: 15px;
  color: #40516a;
  font-size: 12px;
  line-height: 1.55;
}
.page-usage-guide__troubleshooting li::before,
.page-usage-guide__tips li::before {
  position: absolute;
  top: .58em;
  left: 1px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--guide-blue);
  content: "";
}
.page-usage-guide__troubleshooting li::before { background: #d97706; }

@media (max-width: 900px) {
  .page-usage-guide__body { grid-template-columns: 1fr; padding-left: 18px; }
}
@media (max-width: 620px) {
  .page-usage-guide__summary { grid-template-columns: 32px 1fr; }
  .page-usage-guide__toggle { display: none; }
  .page-usage-guide__summary-text { white-space: normal; }
  .page-usage-guide__scope ul { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) {
  .page-usage-guide__chevron { transition: none; }
}
</style>
