## Vue 3 + PointCloudRenderer 集成

将 `PointCloudRenderer.js` 复制到你的 `src/utils/` 目录下，然后在 Vue 组件中使用。

### 基础组件 (Vue 3 Composition API)

```vue
<template>
  <div class="point-cloud-viewer">
    <!-- 工具栏 -->
    <div class="toolbar">
      <input type="file" accept=".txt,.json" @change="onFileUpload" />
      <button @click="loadSample">测试数据 (10万点)</button>

      <select v-model="viewMode" @change="onModeChange">
        <option value="2d">2D (Z→颜色)</option>
        <option value="3d">3D</option>
      </select>

      <label>点大小</label>
      <input type="range" min="1" max="10" step="0.5" v-model.number="pointSize" @input="onSizeChange" />

      <button @click="exportImage">导出图片</button>

      <span v-if="stats" class="stats">
        {{ stats.total.toLocaleString() }} 点
      </span>
    </div>

    <!-- 进度条 -->
    <div v-if="loading" class="progress-bar">
      <span class="progress-text">{{ progress.text }}</span>
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: progress.percent + '%' }"></div>
      </div>
      <span class="progress-text">{{ progress.percent }}%</span>
    </div>

    <!-- 图表容器 -->
    <div ref="chartRef" class="chart-container"></div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue';
import { PointCloudRenderer } from '../utils/PointCloudRenderer';

const chartRef = ref(null);
const viewMode = ref('2d');
const pointSize = ref(3);
const loading = ref(false);
const stats = ref(null);

const progress = reactive({
  percent: 0,
  text: '',
});

let renderer = null;

onMounted(() => {
  if (!chartRef.value) return;

  renderer = new PointCloudRenderer(chartRef.value, {
    theme: 'dark',
    backgroundColor: '#1a1b2e',
  });

  // 进度事件
  renderer.on('progress', (p) => {
    progress.percent = p.percent;
    progress.text = p.text;
    loading.value = true;
  });

  // 加载完成
  renderer.on('load', ({ total, bounds }) => {
    loading.value = false;
    stats.value = { total, bounds };
  });

  // 错误
  renderer.on('error', ({ message }) => {
    loading.value = false;
    console.error('渲染错误:', message);
  });
});

onBeforeUnmount(() => {
  if (renderer) {
    renderer.destroy();
    renderer = null;
  }
});

// 文件上传
function onFileUpload(e) {
  const file = e.target.files?.[0];
  if (!file || !renderer) return;
  renderer.loadFromFile(file).catch(console.error);
}

// 测试数据
function loadSample() {
  if (!renderer) return;
  const count = 100000;
  const points = [];
  for (let i = 0; i < count; i++) {
    const t = Math.random() * Math.PI * 2;
    const r = Math.random() * 10;
    points.push([
      r * Math.cos(t),
      r * Math.sin(t),
      Math.sin(r * 0.5) * Math.cos(r * 0.3) * 2 + (Math.random() - 0.5) * 0.3,
    ]);
  }
  renderer.loadPoints(points).catch(console.error);
}

// 切换模式
function onModeChange() {
  if (renderer) renderer.setMode(viewMode.value);
}

// 点大小
function onSizeChange() {
  if (renderer) renderer.setPointSize(pointSize.value);
}

// 导出
function exportImage() {
  if (!renderer) return;
  const url = renderer.getDataURL({ pixelRatio: 2 });
  const a = document.createElement('a');
  a.download = `pointcloud_${Date.now()}.png`;
  a.href = url;
  a.click();
}
</script>

<style scoped>
.point-cloud-viewer {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #1a1b2e;
  color: #e0e0f0;
}
.toolbar {
  padding: 10px 16px;
  background: #232540;
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  border-bottom: 1px solid #3a3d5c;
}
.toolbar button,
.toolbar select,
.toolbar input[type="file"]::file-selector-button {
  background: #2a2d4a;
  border: 1px solid #3a3d5c;
  color: #e0e0f0;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}
.toolbar button:hover { background: #6c5ce7; }
.toolbar label { color: #8888aa; font-size: 12px; }
.toolbar .stats {
  color: #8888aa;
  font-size: 12px;
  margin-left: auto;
}
.progress-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 16px;
  background: #232540;
  border-top: 1px solid #3a3d5c;
}
.progress-text {
  color: #8888aa;
  font-size: 12px;
  white-space: nowrap;
}
.progress-track {
  flex: 1;
  height: 4px;
  background: #2a2d4a;
  border-radius: 2px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6c5ce7, #00cec9);
  transition: width .15s;
}
.chart-container {
  flex: 1;
  min-height: 0;
}
</style>
```

### 安装

```bash
npm install echarts echarts-gl
```

在 `main.js` 或组件中导入 ECharts：

```javascript
// main.js 中
import 'echarts';
import 'echarts-gl';
```

然后将 `PointCloudRenderer.js` 放入 `src/utils/` 目录即可使用。

### Nuxt 3 注意事项

如果使用 Nuxt 3，需要确保 PointCloudRenderer 只在客户端运行：

```vue
<template>
  <ClientOnly>
    <PointCloudViewer />
  </ClientOnly>
</template>
```

或者在组件中使用：

```javascript
onMounted(async () => {
  // 仅在客户端加载 ECharts
  await import('echarts');
  await import('echarts-gl');
  const { PointCloudRenderer } = await import('../utils/PointCloudRenderer');
  // ...
});
```
