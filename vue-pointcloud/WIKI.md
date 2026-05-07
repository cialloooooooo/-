# PointRenderer 移植到 Vue 3 框架实践

## 背景

`PointRenderer` 是一个基于 ECharts 的点云渲染引擎，支持 3D 散点图（50万+点）和 2D 多边形两种模式。原始实现是一个纯 JS 类，封装在一个 HTML 文件里。

移植目标：将其做成 Vue 3 组件，保持核心引擎零框架依赖，同时充分利用 Vue 的响应式特性。

## 整体思路：薄封装，不重写

核心引擎 `point-renderer.js` 保持独立，不引入任何 Vue 代码。Vue 层只做一件事——把 Props/Events 和引擎实例桥接起来。

```
App.vue  (数据来源、UI 状态)
   ↓ props / ↑ emits
PointCloud.vue  (Vue ↔ 引擎 桥接层)
   ↓ 方法调用 / ↑ 回调
point-renderer.js  (纯 JS 引擎，零框架依赖)
```

这样做的好处：

- **引擎可复用**：同一个 `point-renderer.js` 可以给 React/Angular/Svelte 项目用，也可以直接在 `<script>` 标签里用
- **升级独立**：引擎 bug 修复或功能增强，Vue 组件不需要改
- **测试方便**：引擎可以脱离 Vue 单独测试

## 第一步：引擎改造（UMD → 双模导出）

原始引擎是 IIFE 模式（立即执行函数），通过 UMD 包装输出全局变量。在浏览器 `<script>` 场景下工作良好，但遇到 Vite/Rollup 的 ESM 模块分析时出现问题——打包器无法静态识别 `module.exports` 赋值，报 `"default" is not exported`。

最终采用双模导出：

```js
// UMD 部分（兼容 <script>、AMD、CommonJS）
(function(root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.PointRenderer = factory();
  }
}(this, function() {
  // ... 核心逻辑 ...
  return PointRenderer;
}));

// ESM 部分（供 Vite/Webpack 打包器识别）
export default PointRenderer;
```

UMD 和 ESM 两种导出同时存在，覆盖所有使用场景。

## 第二步：Vue 组件设计

`PointCloud.vue` 的设计遵循"最小表面积"原则——Props 进，Events 出，尽量少的 API。

### Props（数据入口）

| Prop | 类型 | 说明 |
|------|------|------|
| `dataText` | String | 文件原始文本，变化即自动解析渲染 |
| `options` | Object | 引擎配置项，透传给 PointRenderer 构造函数 |

`dataText` 是核心驱动：父组件设置它（比如从 FileReader 读取文件、fetch 拉取远程数据），组件内部 watch 到变化后自动触发解析和渲染。父组件不需要关心时机。

### Events（数据出口）

| Event | 载荷 | 说明 |
|-------|------|------|
| `progress` | `(pct: number)` | 解析进度 0-100 |
| `click-point` | `({x, y, z})` | 用户点击了某个点 |
| `rendered` | `(stats)` | 渲染完成，带数据统计 |
| `error` | `(msg: string)` | 解析或渲染出错 |

全部通过 `defineEmits` 声明，父组件用 `@progress`、`@click-point` 等语法监听。

### Expose（命令式出口）

```js
defineExpose({
  getChart,    // 获取 echarts 实例，做自定义操作
  getStats,    // 获取数据统计
  getMode,     // 获取当前渲染模式
  resize,      // 手动触发重绘
  setData,     // 跳过文本解析，直接给结构化数据
});
```

用 `defineExpose` 暴露给父组件通过 `ref` 调用，覆盖 Props/Events 无法处理的场景（比如需要拿到 echarts 实例做定制）。

### 生命周期管理

```
onMounted        → new PointRenderer(container, options)
                 → register ResizeObserver
                 → if dataText 已有值，立即渲染

watch(dataText)  → doRender() → nextTick → parseAndRender

onBeforeUnmount  → renderer.dispose()
```

关键细节：

- 渲染放在 `nextTick` 里，确保 DOM 容器已就位
- `ResizeObserver` 监听容器尺寸变化自动 `resize()`，省去手动监听 window resize 的麻烦
- `onBeforeUnmount` 调用 `dispose()` 避免内存泄漏

## 第三步：全局依赖处理

`point-renderer.js` 内部直接引用全局变量 `echarts`。在 HTML `<script>` 场景下 CDN 自动挂到 `window.echarts`，但在 Vite/Webpack 构建环境下不会。

解决方案在 `main.js` 启动时显式挂载：

```js
import * as echarts from 'echarts';
import 'echarts-gl';      // 副作用导入，注册 scatter3D 类型
window.echarts = echarts; // 挂全局，供 point-renderer.js 内部使用
```

> `echarts-gl` 是 `import 'echarts-gl'` 而非 `import * from`，因为它只需要副作用——把 3D 图表类型注册到 echarts 上。

## 踩坑记录

### 坑 1：`render()` 自毁数据

从原始内联代码抽取成独立文件时，把清理旧图表的逻辑抽象成了 `dispose()` 方法。`dispose()` 除了销毁图表实例外，还清空了 `this.data` 和 `this.mode`。而 `render()` 在调用 `dispose()` 后立即使用 `this.mode` 判断走 3D 还是 2D 分支——此时已被清空为 `null`，永远掉进 else 分支。

**教训**：抽方法时需区分"内部清理"和"对外销毁"两个语义。对外 API `dispose()` 做全量清理没问题，但内部复用时应只做图表实例替换，不动数据。

### 坑 2：UMD 在打包器中的导出识别

Rollup（Vite 底层）无法静态分析 IIFE 内 `module.exports` 的赋值，导致 `import PointRenderer from '...'` 失败。这是因为 UMD 的导出语句在函数执行路径里，打包器不做运行时分析。

**解决方案**：在 UMD IIFE 之外追加 `export default PointRenderer`，让打包器能静态发现导出。同时 UMD 的 `module.exports` 分支在 Node/非模块环境下仍然有效。

## 目录结构总览

```
vue-pointcloud/
├── index.html                  # Vite 入口
├── package.json                # vue3 + echarts + echarts-gl + vite
├── vite.config.js
├── public/
│   ├── sample-3d.txt           # 3D 示例数据
│   └── sample-2d.txt           # 2D 示例数据
└── src/
    ├── main.js                 # 启动：注册 echarts 全局 + mount Vue
    ├── App.vue                 # 页面：工具栏、进度条、信息面板
    ├── components/
    │   └── PointCloud.vue      # 核心组件：PointRenderer 的 Vue 封装
    └── utils/
        └── point-renderer.js   # 渲染引擎（纯 JS，可独立移植）
```

## 移植到其他项目的检查清单

1. 复制 `src/utils/point-renderer.js` 到目标项目
2. 复制 `src/components/PointCloud.vue` 到目标项目
3. 确保 `echarts` 和 `echarts-gl` 已安装并挂到全局（或改为 import 传参方式）
4. 在父组件中：

```vue
<template>
  <PointCloud
    :data-text="myFileContent"
    @progress="onProgress"
    @click-point="onClick"
    @error="onError"
  />
</template>
```

完成。单个组件、单个引擎文件，无需额外配置。
