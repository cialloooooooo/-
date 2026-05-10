<template>
  <div ref="chartContainer" class="pointcloud-chart"></div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import PointRenderer from '../utils/point-renderer.js';

const props = defineProps({
  /** 从后端下载的结构化数据 { mode: '3d'|'2d', data: Array } */
  serverData: { type: Object, default: null },
  /** PointRenderer 配置项 */
  options: { type: Object, default: () => ({}) },
});

const emit = defineEmits([
  'progress',
  'clickPoint',
  'rendered',
  'error',
]);

const chartContainer = ref(null);
let renderer = null;

defineExpose({
  getChart: () => renderer?.getChart(),
  getStats: () => renderer?.getStats(),
  getMode: () => renderer?.getMode(),
  resize: () => renderer?.resize(),
  setData: (mode, data) => {
    renderer?.setData(mode, data);
    renderer?.render();
    emit('rendered', renderer.getStats());
  },
});

onMounted(() => {
  renderer = new PointRenderer(chartContainer.value, props.options);
  renderer.onClick((coord) => emit('clickPoint', coord));

  if (window.ResizeObserver) {
    new ResizeObserver(() => renderer?.resize()).observe(chartContainer.value);
  }

  if (props.serverData) doRender(props.serverData);
});

onBeforeUnmount(() => {
  renderer?.dispose();
  renderer = null;
});

watch(() => props.serverData, (val) => {
  if (val) doRender(val);
});

function doRender({ mode, data }) {
  if (!renderer) return;
  nextTick(() => {
    try {
      renderer.setData(mode, data);
      renderer.render();
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
