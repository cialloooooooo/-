<template>
  <div class="point-cloud-page">
    <aside class="control-panel">
      <div class="panel-section">
        <h3>数据源</h3>
        <el-radio-group v-model="fileMode" size="small">
          <el-radio-button value="path">文件路径</el-radio-button>
          <el-radio-button value="upload">上传文件</el-radio-button>
        </el-radio-group>

        <div v-if="fileMode === 'path'" class="path-input">
          <el-input
            v-model="filePath"
            placeholder="/points_50w.txt"
            size="small"
            clearable
          />
          <el-button
            type="primary"
            size="small"
            :loading="store.status === 'loading' || store.status === 'parsing'"
            @click="loadFromPath"
          >
            加载
          </el-button>
        </div>

        <div v-else class="upload-input">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".txt"
            :on-change="onFileChange"
            :file-list="fileList"
          >
            <el-button size="small" type="primary">选择文件</el-button>
          </el-upload>
        </div>
      </div>

      <div class="panel-section">
        <h3>渲染设置</h3>
        <div class="setting-item">
          <label>点大小</label>
          <el-slider v-model="symbolSize" :min="1" :max="10" :step="0.5" show-input size="small" />
        </div>
        <div class="setting-item">
          <label>透明度</label>
          <el-slider v-model="opacity" :min="0.1" :max="1" :step="0.05" show-input size="small" />
        </div>
        <div class="setting-item">
          <label>采样率</label>
          <el-select v-model="sampleRate" size="small">
            <el-option label="全部 (100%)" :value="1" />
            <el-option label="50%" :value="2" />
            <el-option label="25%" :value="4" />
            <el-option label="10%" :value="10" />
            <el-option label="5%" :value="20" />
            <el-option label="1%" :value="100" />
          </el-select>
        </div>
      </div>

      <div class="panel-section stats" v-if="store.pointCount > 0">
        <h3>数据统计</h3>
        <div class="stat-item">
          <span class="stat-label">总点数</span>
          <span class="stat-value">{{ store.pointCount.toLocaleString() }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">渲染点数</span>
          <span class="stat-value">{{ sampledCount.toLocaleString() }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">渲染模式</span>
          <span class="stat-value">{{ store.is3D ? '3D' : '2D' }}</span>
        </div>
      </div>

      <div class="panel-section inspect" v-if="store.clickedPoint">
        <h3>单击点信息</h3>
        <div class="inspect-row">
          <span class="inspect-label">索引</span>
          <span class="inspect-value">{{ store.clickedIndex.toLocaleString() }}</span>
        </div>
        <div class="inspect-row">
          <span class="inspect-label">X</span>
          <span class="inspect-value x">{{ store.clickedPoint.x.toFixed(4) }}</span>
        </div>
        <div class="inspect-row">
          <span class="inspect-label">Y</span>
          <span class="inspect-value y">{{ store.clickedPoint.y.toFixed(4) }}</span>
        </div>
        <div class="inspect-row" v-if="store.is3D">
          <span class="inspect-label">Z</span>
          <span class="inspect-value z">{{ store.clickedPoint.z.toFixed(4) }}</span>
        </div>
      </div>

      <div class="panel-section selection" v-if="store.selectedPoints.length > 0">
        <h3>
          框选结果
          <el-button
            text
            size="small"
            type="danger"
            @click="store.clearSelection()"
          >
            清除
          </el-button>
        </h3>
        <div class="stat-item">
          <span class="stat-label">选中点数</span>
          <span class="stat-value">{{ store.selectedPoints.length.toLocaleString() }}</span>
        </div>
        <div class="selected-list">
          <div
            v-for="pt in store.selectedPoints.slice(0, 50)"
            :key="pt.index"
            class="selected-row"
          >
            <span class="sel-idx">#{{ pt.index }}</span>
            <span class="sel-coord">({{ pt.x.toFixed(3) }}, {{ pt.y.toFixed(3) }}, {{ pt.z.toFixed(3) }})</span>
          </div>
          <div v-if="store.selectedPoints.length > 50" class="selected-more">
            ... 还有 {{ (store.selectedPoints.length - 50).toLocaleString() }} 个点
          </div>
        </div>
      </div>
    </aside>

    <main class="render-area">
      <div v-if="store.status === 'idle' && !store.pointCount" class="placeholder">
        <div class="placeholder-icon">
          <svg viewBox="0 0 80 80" width="80" height="80">
            <rect x="8" y="20" width="64" height="48" rx="4" fill="none" stroke="#555" stroke-width="2"/>
            <polyline points="20,54 32,40 40,46 52,34 62,50" fill="none" stroke="#409EFF" stroke-width="2.5"/>
            <circle cx="30" cy="32" r="3" fill="#409EFF"/>
            <circle cx="44" cy="42" r="3" fill="#409EFF"/>
            <circle cx="56" cy="30" r="3" fill="#409EFF"/>
          </svg>
        </div>
        <p>选择数据源并加载文件以开始渲染</p>
      </div>

      <div v-else-if="store.status === 'loading'" class="progress-overlay">
        <el-progress
          type="circle"
          :percentage="loadProgress"
          :stroke-width="8"
          :width="160"
        />
        <p class="progress-text">{{ loadStatusText }}</p>
      </div>

      <div v-else-if="store.status === 'error'" class="error-overlay">
        <el-result icon="error" :title="store.errorMessage" sub-title="请检查文件格式或路径后重试">
          <template #extra>
            <el-button type="primary" @click="store.reset()">重试</el-button>
          </template>
        </el-result>
      </div>

      <PointCloudRenderer
        v-else
        :points="sampledPoints"
        :is3-d="store.is3D"
        :symbol-size="symbolSize"
        :opacity="opacity"
        @point-click="onPointClick"
        @points-selected="onPointsSelected"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  ElRadioGroup,
  ElRadioButton,
  ElInput,
  ElButton,
  ElUpload,
  ElSlider,
  ElSelect,
  ElOption,
  ElProgress,
  ElResult,
} from 'element-plus'
import type { UploadFile, UploadInstance } from 'element-plus'
import { usePointsStore } from '@/stores/points'
import type { Point3D, ParseMessage } from '@/workers/parsePoints'
import PointCloudRenderer from '@/components/PointCloudRenderer.vue'

const store = usePointsStore()

const fileMode = ref<'path' | 'upload'>('path')
const filePath = ref('/points_50w.txt')
const fileList = ref<UploadFile[]>([])
const uploadRef = ref<UploadInstance>()

const symbolSize = ref(3)
const opacity = ref(0.8)
const sampleRate = ref(1)
const loadProgress = ref(0)
const loadStatusText = ref('')

let worker: Worker | null = null

const sampledPoints = computed<Point3D[]>(() => {
  const pts = store.points
  if (sampleRate.value <= 1) return pts
  const step = sampleRate.value
  const result: Point3D[] = []
  for (let i = 0; i < pts.length; i += step) {
    result.push(pts[i])
  }
  return result
})

const sampledCount = computed(() => sampledPoints.value.length)

watch(() => store.status, (val) => {
  if (val === 'loading') {
    loadProgress.value = 0
    loadStatusText.value = '正在读取文件...'
  }
})

function terminateWorker() {
  if (worker) {
    worker.terminate()
    worker = null
  }
}

function parseFile(text: string) {
  terminateWorker()
  store.status = 'parsing'
  loadStatusText.value = '正在解析坐标点...'

  worker = new Worker(
    new URL('@/workers/parsePoints.ts', import.meta.url),
    { type: 'module' },
  )

  worker.onmessage = (e: MessageEvent<ParseMessage>) => {
    const msg = e.data
    if (msg.type === 'progress' && msg.progress != null) {
      loadProgress.value = msg.progress
      loadStatusText.value = `正在解析坐标点... ${msg.progress}%`
    } else if (msg.type === 'result') {
      store.setPoints(msg.points!, msg.is3D!)
      terminateWorker()
    } else if (msg.type === 'error') {
      store.setError(msg.message!)
      terminateWorker()
    }
  }

  worker.onerror = (err) => {
    store.setError(err.message || 'Worker 异常')
    terminateWorker()
  }

  worker.postMessage({ text })
}

async function loadFile(file: File | string) {
  store.reset()
  store.status = 'loading'
  loadProgress.value = 0

  try {
    let text: string

    if (typeof file === 'string') {
      const response = await fetch(file)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: 文件加载失败`)
      }
      const contentLength = response.headers.get('content-length')
      const total = contentLength ? parseInt(contentLength, 10) : 0

      if (total && response.body) {
        const reader = response.body.getReader()
        const chunks: Uint8Array[] = []
        let received = 0

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          chunks.push(value)
          received += value.length
          if (total) {
            loadProgress.value = Math.round((received / total) * 100)
            loadStatusText.value = `正在读取文件... ${loadProgress.value}%`
          }
        }

        const decoder = new TextDecoder('utf-8')
        text = decoder.decode(
          chunks.reduce((acc, chunk) => {
            const tmp = new Uint8Array(acc.length + chunk.length)
            tmp.set(acc, 0)
            tmp.set(chunk, acc.length)
            return tmp
          }, new Uint8Array(0)),
        )
      } else {
        text = await response.text()
        loadProgress.value = 100
      }
    } else {
      loadProgress.value = 50
      loadStatusText.value = '正在读取文件...'
      text = await file.text()
      loadProgress.value = 100
    }

    parseFile(text)
  } catch (err) {
    store.setError(err instanceof Error ? err.message : '文件加载失败')
  }
}

function loadFromPath() {
  const path = filePath.value.trim()
  if (!path) {
    store.setError('请输入文件路径')
    return
  }
  loadFile(path)
}

function onFileChange(file: UploadFile) {
  if (file.raw) {
    loadFile(file.raw)
  }
}

function onPointClick(payload: { index: number; x: number; y: number; z: number }) {
  store.setClickedPoint(payload.index, { x: payload.x, y: payload.y, z: payload.z })
}

function onPointsSelected(payload: { indices: number[] }) {
  store.setSelection(payload.indices)
}
</script>

<style scoped>
.point-cloud-page {
  display: flex;
  height: 100%;
}

.control-panel {
  width: 260px;
  min-width: 260px;
  background: #1a1a2e;
  border-right: 1px solid #16213e;
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.panel-section {
  margin-bottom: 4px;
  padding: 12px;
  background: #16213e;
  border-radius: 6px;
}

.panel-section h3 {
  margin: 0 0 10px;
  font-size: 13px;
  color: #a0a0b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.path-input {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}

.upload-input {
  margin-top: 10px;
}

.setting-item {
  margin-bottom: 10px;
}

.setting-item label {
  display: block;
  font-size: 12px;
  color: #808090;
  margin-bottom: 4px;
}

.stats {
  margin-top: 4px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
}

.stat-label {
  color: #808090;
}

.stat-value {
  color: #409EFF;
  font-weight: 600;
}

.inspect,
.selection {
  margin-top: 4px;
}

.inspect-row {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
  font-size: 13px;
}

.inspect-label {
  color: #808090;
  width: 36px;
}

.inspect-value {
  color: #e0e0e0;
  font-weight: 500;
  font-family: 'Consolas', 'Menlo', monospace;
}

.inspect-value.x { color: #f56c6c; }
.inspect-value.y { color: #67c23a; }
.inspect-value.z { color: #409EFF; }

.selection h3 {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.selected-list {
  max-height: 240px;
  overflow-y: auto;
  margin-top: 8px;
}

.selected-row {
  display: flex;
  gap: 8px;
  padding: 2px 0;
  font-size: 11px;
  font-family: 'Consolas', 'Menlo', monospace;
}

.sel-idx {
  color: #808090;
  min-width: 48px;
  flex-shrink: 0;
}

.sel-coord {
  color: #a0b8c0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.selected-more {
  color: #808090;
  font-size: 11px;
  text-align: center;
  padding: 4px 0;
}

.render-area {
  flex: 1;
  position: relative;
  background: #0f0f23;
  overflow: hidden;
}

.placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #555;
  gap: 16px;
}

.placeholder p {
  font-size: 15px;
}

.progress-overlay {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 20px;
}

.progress-text {
  color: #409EFF;
  font-size: 14px;
}

.error-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}
</style>
