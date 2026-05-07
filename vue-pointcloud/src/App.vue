<template>
  <div class="app">
    <!-- 工具栏 -->
    <header class="toolbar">
      <span class="brand">Vue PointCloud</span>

      <label class="file-btn">
        📂 选择数据文件
        <input type="file" accept=".txt,.json" @change="handleFile" />
      </label>

      <span class="mode-badge" :class="{ active: mode }">{{ modeLabel }}</span>
      <span class="info">{{ statsText }}</span>

      <label class="demo-link">
        示例:
        <a href="#" @click.prevent="loadDemo('3d')">3D 点云</a>
        <a href="#" @click.prevent="loadDemo('2d')">2D 多边形</a>
      </label>
    </header>

    <!-- 进度条 -->
    <div class="progress-wrap" :class="{ visible: progressing }">
      <div class="progress-bar" :style="{ width: progress + '%' }"></div>
      <div class="progress-text">{{ progressText }}</div>
    </div>

    <!-- 图表区域 -->
    <div class="chart-area" ref="chartArea">
      <PointCloud
        ref="pointCloudRef"
        :options="chartOptions"
        :data-text="dataText"
        @progress="onProgress"
        @click-point="onClickPoint"
        @error="onError"
      />
      <div v-if="!dataText" class="empty-state">
        <div class="icon">📊</div>
        <p>点击上方按钮加载数据文件</p>
        <p class="sub">支持 3D 点云 (50万+点) / 2D 多边形</p>
      </div>
      <div v-if="selected" class="info-panel">
        <div class="title">选中点坐标</div>
        <div class="coord">
          X: <span>{{ selected.x.toFixed(4) }}</span>
          Y: <span>{{ selected.y.toFixed(4) }}</span>
          <template v-if="selected.z != null">
            Z: <span>{{ selected.z.toFixed(4) }}</span>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import PointCloud from './components/PointCloud.vue';

// ── 状态 ──────────────────────────────────────────────
const pointCloudRef = ref(null);
const dataText = ref('');
const mode = ref('');
const stats = ref(null);
const selected = ref(null);
const progress = ref(0);
const progressing = ref(false);
const progressText = ref('');
const error = ref('');

const chartOptions = {
  backgroundColor: '#1a1a2e',
};

// ── 计算属性 ──────────────────────────────────────────
const modeLabel = computed(() => {
  if (mode.value === '3d') return '3D 模式';
  if (mode.value === '2d') return '2D 模式';
  return '未加载';
});

const statsText = computed(() => {
  if (!stats.value) return '';
  if (stats.value.mode === '3D 散点') return `点数量: ${stats.value.pointCount.toLocaleString()}`;
  return `多边形: ${stats.value.polygonCount} | 顶点: ${stats.value.vertexCount.toLocaleString()}`;
});

// ── 事件处理 ──────────────────────────────────────────
function handleFile(e) {
  const file = e.target.files[0];
  if (!file) return;
  progressing.value = true;
  progressText.value = '读取文件...';

  const reader = new FileReader();
  reader.onload = (ev) => {
    dataText.value = ev.target.result;
  };
  reader.onerror = () => {
    error.value = '文件读取失败';
    progressing.value = false;
  };
  reader.readAsText(file);
}

function onProgress(pct) {
  progress.value = pct;
  progressText.value = `解析中 ${pct}%`;
  if (pct >= 100) {
    setTimeout(() => { progressing.value = false; }, 400);
  }
}

function onClickPoint(coord) {
  selected.value = coord;
}

function onError(msg) {
  alert(msg);
  progressing.value = false;
}

async function loadDemo(type) {
  const url = type === '3d' ? '/sample-3d.txt' : '/sample-2d.txt';
  progressing.value = true;
  progressText.value = '加载示例...';
  try {
    const res = await fetch(url);
    dataText.value = await res.text();
  } catch (e) {
    alert('加载示例失败: ' + e.message);
    progressing.value = false;
  }
}
</script>

<style>
:root {
  --bg: #1a1a2e;
  --surface: #16213e;
  --text: #e0e0e0;
  --accent: #0f3460;
  --highlight: #e94560;
  --border: #2a2a4a;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; }

.app {
  height: 100vh; display: flex; flex-direction: column; overflow: hidden;
}

/* 工具栏 */
.toolbar {
  display: flex; align-items: center; gap: 14px;
  padding: 10px 20px; background: var(--surface);
  border-bottom: 1px solid var(--border); flex-shrink: 0;
}
.toolbar .brand {
  font-size: 17px; font-weight: 700;
  background: linear-gradient(135deg, #e94560, #0f3460);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.toolbar label.file-btn {
  padding: 7px 16px; background: var(--accent); color: #fff;
  border-radius: 6px; cursor: pointer; font-size: 13px; transition: opacity .2s;
}
.toolbar label.file-btn:hover { opacity: .85; }
.toolbar input[type=file] { display: none; }
.toolbar .mode-badge {
  padding: 4px 12px; border-radius: 4px; font-size: 12px;
  background: var(--border); color: #aaa;
}
.toolbar .mode-badge.active { background: var(--highlight); color: #fff; }
.toolbar .info { font-size: 13px; color: #888; }
.toolbar .demo-link { margin-left: auto; font-size: 13px; color: #888; }
.toolbar .demo-link a { color: #74add1; text-decoration: none; margin-left: 6px; }
.toolbar .demo-link a:hover { text-decoration: underline; }

/* 进度条 */
.progress-wrap {
  height: 3px; background: var(--border); flex-shrink: 0;
  position: relative; opacity: 0; transition: opacity .3s;
}
.progress-wrap.visible { opacity: 1; }
.progress-bar {
  height: 100%; background: var(--highlight); width: 0%; transition: width .08s linear;
}
.progress-text {
  position: absolute; right: 8px; top: -20px; font-size: 12px; color: #ccc;
}

/* 图表区域 */
.chart-area {
  flex: 1; position: relative; min-height: 0;
}

/* 空状态 */
.empty-state {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  text-align: center; color: #555;
}
.empty-state .icon { font-size: 48px; margin-bottom: 12px; }
.empty-state p { font-size: 14px; }
.empty-state .sub { font-size: 12px; color: #444; margin-top: 4px; }

/* 选中信息面板 */
.info-panel {
  position: absolute; bottom: 20px; left: 20px;
  background: rgba(22,33,62,.92); border: 1px solid var(--border);
  border-radius: 8px; padding: 14px 18px; font-size: 13px;
  backdrop-filter: blur(10px); z-index: 50;
}
.info-panel .title { font-size: 11px; color: #888; margin-bottom: 4px; }
.info-panel .coord { font-size: 15px; color: #fff; }
.info-panel .coord span { color: var(--highlight); margin-right: 8px; }
</style>
