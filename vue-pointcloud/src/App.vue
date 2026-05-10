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
        :server-data="serverData"
        @progress="onProgress"
        @click-point="onClickPoint"
        @error="onError"
      />
      <div v-if="!serverData" class="empty-state">
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
import { ref, computed, onBeforeUnmount } from 'vue';
import PointCloud from './components/PointCloud.vue';

const API_BASE = 'http://localhost:3001';

// ── 状态 ──────────────────────────────────────────────
const pointCloudRef = ref(null);
const serverData = ref(null);
const mode = ref('');
const stats = ref(null);
const selected = ref(null);
const progress = ref(0);
const progressing = ref(false);
const progressText = ref('');
const error = ref('');

// 轮询相关
let pollTimer = null;
let knownVersion = 0;

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

// ── 轮询监听 ──────────────────────────────────────────
function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/data/status`);
      const status = await res.json();
      if (status.version > knownVersion && status.hasData) {
        knownVersion = status.version;
        await downloadData();
      }
    } catch {
      // 后端未就绪时静默忽略
    }
  }, 1000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function downloadData() {
  try {
    const res = await fetch(`${API_BASE}/api/data`);
    const result = await res.json();
    serverData.value = { mode: result.mode, data: result.data };
  } catch (e) {
    alert('下载数据失败: ' + e.message);
    progressing.value = false;
  }
}

onBeforeUnmount(() => stopPolling());

// ── 事件处理 ──────────────────────────────────────────
async function handleFile(e) {
  const file = e.target.files[0];
  if (!file) return;

  progressing.value = true;
  progressText.value = '上传文件到后端...';
  progress.value = 30;

  try {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/api/upload`, {
      method: 'POST',
      body: formData,
    });
    const result = await res.json();

    if (!result.success) {
      throw new Error(result.error || '上传失败');
    }

    progress.value = 100;
    progressText.value = '后端处理完成，等待数据...';
    knownVersion = result.version;

    // 下载数据并渲染
    await downloadData();
    setTimeout(() => { progressing.value = false; }, 400);
    startPolling();
  } catch (err) {
    alert('上传失败: ' + err.message);
    progressing.value = false;
  }
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
  progress.value = 20;

  try {
    // 下载示例文件，然后上传到后端
    const txtRes = await fetch(`${API_BASE}${url}`);
    const text = await txtRes.text();
    const blob = new Blob([text], { type: 'text/plain' });
    const formData = new FormData();
    formData.append('file', blob, `sample-${type}.txt`);

    progress.value = 50;
    progressText.value = '上传到后端...';

    const uploadRes = await fetch(`${API_BASE}/api/upload`, {
      method: 'POST',
      body: formData,
    });
    const result = await uploadRes.json();

    if (!result.success) {
      throw new Error(result.error || '上传失败');
    }

    progress.value = 100;
    knownVersion = result.version;
    await downloadData();
    setTimeout(() => { progressing.value = false; }, 400);
    startPolling();
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
