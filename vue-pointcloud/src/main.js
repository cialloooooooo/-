import { createApp } from 'vue';
import App from './App.vue';

// echarts / echarts-gl 挂载到全局，供 point-renderer.js 内部调用
import * as echarts from 'echarts';
import 'echarts-gl';
window.echarts = echarts;

createApp(App).mount('#app');
