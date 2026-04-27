<template>
  <div
    ref="chartRef"
    class="chart-container"
    @mousedown="onMouseDown"
    @mouseup="onMouseUp"
  >
    <div
      v-if="selecting && is3D"
      class="selection-rect"
      :style="selectionRectStyle"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, shallowRef, computed } from 'vue'
import * as echarts from 'echarts'
import 'echarts-gl'
import type { Point3D } from '@/stores/points'

const props = defineProps<{
  points: Point3D[]
  is3D: boolean
  symbolSize: number
  opacity: number
}>()

const emit = defineEmits<{
  (e: 'point-click', payload: { index: number; x: number; y: number; z: number }): void
  (e: 'points-selected', payload: { indices: number[] }): void
}>()

const chartRef = ref<HTMLDivElement>()
const chartInstance = shallowRef<echarts.ECharts | null>(null)

const selecting = ref(false)
const selectionRect = ref({ left: 0, top: 0, width: 0, height: 0 })
let dragStart = { x: 0, y: 0 }

const selectionRectStyle = computed(() => ({
  left: `${selectionRect.value.left}px`,
  top: `${selectionRect.value.top}px`,
  width: `${selectionRect.value.width}px`,
  height: `${selectionRect.value.height}px`,
}))

function build2DOption(): echarts.EChartsOption {
  const data = props.points.map((p) => [p.x, p.y])

  return {
    backgroundColor: '#0f0f23',
    tooltip: {},
    toolbox: {
      feature: {
        brush: { type: ['rect', 'clear'] },
      },
      right: 10,
      top: 10,
    },
    brush: {
      toolbox: ['rect', 'clear'],
      brushLink: 'all',
      throttleType: 'debounce',
      throttleDelay: 300,
      brushStyle: {
        borderWidth: 1,
        color: 'rgba(64,158,255,0.2)',
        borderColor: '#409EFF',
      },
    },
    xAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#555' } },
      axisLabel: { color: '#888' },
      splitLine: { lineStyle: { color: '#222' } },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#555' } },
      axisLabel: { color: '#888' },
      splitLine: { lineStyle: { color: '#222' } },
    },
    series: [
      {
        type: 'scatter',
        data,
        symbolSize: props.symbolSize,
        large: true,
        largeThreshold: 2000,
        itemStyle: {
          color: '#409EFF',
          opacity: props.opacity,
          borderWidth: 0,
        },
        emphasis: {
          itemStyle: {
            borderColor: '#fff',
            borderWidth: 1,
          },
        },
      },
    ],
  } as echarts.EChartsOption
}

function build3DOption(): echarts.EChartsOption {
  const data = props.points.map((p) => [p.x, p.y, p.z])

  return {
    backgroundColor: '#0f0f23',
    tooltip: {},
    grid3D: {
      viewControl: {
        autoRotate: false,
        projection: 'perspective',
        distance: 200,
        alpha: 25,
        beta: 45,
      },
      boxWidth: 100,
      boxHeight: 100,
      boxDepth: 100,
      light: {
        main: { intensity: 1.5, shadow: true },
        ambient: { intensity: 0.5 },
      },
    },
    xAxis3D: {
      type: 'value',
      axisLine: { lineStyle: { color: '#555' } },
      axisLabel: { color: '#888' },
      splitLine: { lineStyle: { color: '#222' } },
    },
    yAxis3D: {
      type: 'value',
      axisLine: { lineStyle: { color: '#555' } },
      axisLabel: { color: '#888' },
      splitLine: { lineStyle: { color: '#222' } },
    },
    zAxis3D: {
      type: 'value',
      axisLine: { lineStyle: { color: '#555' } },
      axisLabel: { color: '#888' },
      splitLine: { lineStyle: { color: '#222' } },
    },
    series: [
      {
        type: 'scatter3D',
        data,
        symbolSize: props.symbolSize,
        itemStyle: {
          opacity: props.opacity,
          borderWidth: 0,
        },
        emphasis: {
          itemStyle: {
            borderColor: '#fff',
            borderWidth: 1,
          },
        },
      },
    ],
  } as echarts.EChartsOption
}

function initChart() {
  if (!chartRef.value) return

  const renderer = props.is3D ? 'webgl' : 'canvas'

  if (chartInstance.value) {
    chartInstance.value.off('click')
    chartInstance.value.off('brushSelected')
    chartInstance.value.dispose()
    chartInstance.value = null
  }

  chartInstance.value = echarts.init(chartRef.value, undefined, { renderer })

  chartInstance.value.on('click', (params: { seriesType?: string; dataIndex?: number; value?: number[] }) => {
    if (params.seriesType === 'scatter3D' || params.seriesType === 'scatter') {
      if (params.dataIndex != null && params.value) {
        const [x, y, z] = params.value
        emit('point-click', {
          index: params.dataIndex,
          x,
          y,
          z: z ?? 0,
        })
      }
    }
  })

  chartInstance.value.on('brushSelected', (params: { batch?: { selected?: { dataIndex?: number[] }[] }[] }) => {
    const indices: number[] = []
    if (params.batch) {
      for (const batch of params.batch) {
        if (batch.selected) {
          for (const sel of batch.selected) {
            if (sel.dataIndex) {
              indices.push(...sel.dataIndex)
            }
          }
        }
      }
    }
    if (indices.length > 0) {
      emit('points-selected', { indices })
    }
  })

  const option = props.is3D ? build3DOption() : build2DOption()
  chartInstance.value.setOption(option, true)
}

function resizeChart() {
  chartInstance.value?.resize()
}

// --- Custom 3D box selection ---
function onMouseDown(e: MouseEvent) {
  if (!props.is3D) return
  if (e.button !== 0) return
  if (!chartRef.value) return
  const rect = chartRef.value.getBoundingClientRect()
  dragStart = { x: e.clientX - rect.left, y: e.clientY - rect.top }
  selecting.value = true
  selectionRect.value = { left: dragStart.x, top: dragStart.y, width: 0, height: 0 }

  const onMove = (ev: MouseEvent) => {
    if (!selecting.value) return
    const x = ev.clientX - rect.left
    const y = ev.clientY - rect.top
    selectionRect.value = {
      left: Math.min(dragStart.x, x),
      top: Math.min(dragStart.y, y),
      width: Math.abs(x - dragStart.x),
      height: Math.abs(y - dragStart.y),
    }
  }

  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    if (!selecting.value) return
    selecting.value = false

    const { left, top, width, height } = selectionRect.value
    if (width < 5 || height < 5) {
      selectionRect.value = { left: 0, top: 0, width: 0, height: 0 }
      return
    }

    const chart = chartInstance.value
    if (!chart) return

    const indices = findPointsInRect(left, top, left + width, top + height)
    if (indices.length > 0) {
      emit('points-selected', { indices })
    }

    selectionRect.value = { left: 0, top: 0, width: 0, height: 0 }
  }

  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

function onMouseUp() {
  // handled by document listener
}

function findPointsInRect(x1: number, y1: number, x2: number, y2: number): number[] {
  const chart = chartInstance.value
  if (!chart) return []

  const pts = props.points
  const indices: number[] = []
  const batchSize = 10000

  for (let i = 0; i < pts.length; i += batchSize) {
    const end = Math.min(i + batchSize, pts.length)
    for (let j = i; j < end; j++) {
      const pxl = chart.convertToPixel({ seriesIndex: 0 }, [pts[j].x, pts[j].y, pts[j].z])
      if (pxl && isFinite(pxl[0]) && isFinite(pxl[1]) && pxl[0] >= x1 && pxl[0] <= x2 && pxl[1] >= y1 && pxl[1] <= y2) {
        indices.push(j)
      }
    }
  }

  return indices
}

let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  initChart()

  if (chartRef.value) {
    resizeObserver = new ResizeObserver(() => {
      resizeChart()
    })
    resizeObserver.observe(chartRef.value)
  }

  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('resize', resizeChart)
  chartInstance.value?.dispose()
})

watch(
  () => [props.points, props.is3D, props.symbolSize, props.opacity] as const,
  () => {
    initChart()
  },
)
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: 100%;
  position: relative;
}

.selection-rect {
  position: absolute;
  pointer-events: none;
  border: 2px dashed #409EFF;
  background: rgba(64, 158, 255, 0.12);
  z-index: 10;
}
</style>
