<template>
  <div ref="chartContainer" class="pointcloud-chart"></div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import PointRenderer from '../utils/point-renderer.js';

const props = defineProps({
  /** 文件原始文本（变化时自动解析+渲染） */
  dataText: { type: String, default: '' },
  /** PointRenderer 配置项 */
  options: { type: Object, default: () => ({}) },
});

const emit = defineEmits([
  'progress',   // (percent: number) 解析进度 0-100
  'clickPoint', // ({ x, y, z }) 点击选中点
  'rendered',   // (stats: object) 渲染完成
  'error',      // (message: string) 错误
]);

const chartContainer = ref(null);
let renderer = null;

// 暴露给父组件的方法
defineExpose({
  getChart: () => renderer?.getChart(),
  getStats: () => renderer?.getStats(),
  getMode: () => renderer?.getMode(),
  resize: () => renderer?.resize(),
  /** 以编程方式设置结构化数据并渲染 */
  setData: (mode, data) => {
    renderer?.setData(mode, data);
    renderer?.render();
    emit('rendered', renderer.getStats());
  },
});

onMounted(() => {
  renderer = new PointRenderer(chartContainer.value, props.options);
  renderer.onClick((coord) => emit('clickPoint', coord));

  // 监听容器大小变化（简易 ResizeObserver）
  if (window.ResizeObserver) {
    new ResizeObserver(() => renderer?.resize()).observe(chartContainer.value);
  }

  // 如果挂载时已有数据，立即渲染
  if (props.dataText) doRender(props.dataText);
});

onBeforeUnmount(() => {
  renderer?.dispose();
  renderer = null;
});

// 监听 dataText 变化
watch(() => props.dataText, (val) => {
  if (val) doRender(val);
});

function doRender(text) {
  if (!renderer) return;
  nextTick(() => {
    try {
      const result = renderer.parseAndRender(text, (pct) => {
        emit('progress', pct);
      });
      emit('rendered', renderer.getStats());
    } catch (e) {
      emit('error', e.message);
    }
  });
}
</script>

<style scoped>
.pointcloud-chart {
  width: 100%;
  height: 100%;
}
</style>
