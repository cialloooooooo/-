# PointCloudRenderer — 点云渲染库 Wiki

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [核心模块详解](#3-核心模块详解)
   - [3.1 渲染引擎基类 — PointCloudRenderer](#31-渲染引擎基类--pointcloudrenderer)
   - [3.2 3D 渲染器 — PointCloud3DRenderer](#32-3d-渲染器--pointcloud3drenderer)
   - [3.3 2D 渲染器 — PointCloud2DRenderer](#33-2d-渲染器--pointcloud2drenderer)
   - [3.4 文件解析器 — TxtPointParser](#34-文件解析器--txtpointparser)
   - [3.5 统一管理器 — PointCloudManager](#35-统一管理器--pointcloudmanager)
   - [3.6 入口导出 — index.js](#36-入口导出--indexjs)
4. [数据流与渲染流程](#4-数据流与渲染流程)
5. [调用方式](#5-调用方式)
   - [5.1 方式一：使用统一管理器（推荐）](#51-方式一使用统一管理器推荐)
   - [5.2 方式二：直接使用渲染器](#52-方式二直接使用渲染器)
   - [5.3 方式三：浏览器文件上传](#53-方式三浏览器文件上传)
   - [5.4 方式四：从 URL 加载](#54-方式四从-url-加载)
6. [TXT 文件格式规范](#6-txt-文件格式规范)
7. [配置项参考](#7-配置项参考)
8. [性能优化策略](#8-性能优化策略)
9. [交互功能](#9-交互功能)
10. [常见问题](#10-常见问题)

---

## 1. 项目概述

**PointCloudRenderer** 是一个基于 **ECharts + ECharts GL** 的高性能点云渲染库，支持 **3D** 和 **2D** 两种渲染模式。它能够流畅渲染 **50 万级别**的点云数据，适用于地理信息可视化、激光雷达(LiDAR)数据显示、科学计算可视化等场景。

### 核心特性

| 特性 | 说明 |
|------|------|
| 🚀 **高性能** | 基于 WebGL 硬件加速，支持渐进渲染，50 万点流畅交互 |
| 🎨 **双模式** | 支持 3D 散点图和 2D 散点图，可动态切换 |
| 🎯 **点选交互** | 支持点击选中点，高亮显示坐标信息 |
| 📂 **多数据源** | 支持文件内容、File 对象、URL 三种数据加载方式 |
| 🔌 **可扩展** | 采用模板方法模式，易于扩展新的渲染器或解析器 |
| 📦 **按需加载** | 模块化导出，支持按需引入 |

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     index.js (入口导出)                       │
│  导出: PointCloudRenderer, PointCloud3DRenderer,             │
│        PointCloud2DRenderer, TxtPointParser,                 │
│        PointCloudManager (默认导出)                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌──────────────────┐    ┌──────────────────────┐
│ PointCloudManager │    │    TxtPointParser     │
│   (统一管理器)     │    │     (文件解析器)       │
│                   │    │                      │
│  - loadFromContent│    │  - parse(content)     │
│  - loadFromFile   │    │  - parseFile(file)    │
│  - loadFromUrl    │    │  - parseFromUrl(url)  │
│  - switchMode()   │    │  - serialize()        │
│  - update()       │    └──────────────────────┘
│  - dispose()      │
└────────┬──────────┘
         │ 创建并管理
         ▼
┌──────────────────────────────────────────────────┐
│            PointCloudRenderer (基类)               │
│  - init() / render() / dispose() / update()       │
│  - setData() / _calcDataRange()                   │
│  - _getColor() / defaultColorMapper()             │
│  - 模板方法模式：子类实现 render() 和 dispose()    │
└──────────────────────┬───────────────────────────┘
                       │ 继承
          ┌────────────┴────────────┐
          ▼                         ▼
┌──────────────────┐    ┌──────────────────────┐
│PointCloud3D      │    │PointCloud2D          │
│Renderer          │    │Renderer              │
│                  │    │                      │
│ - scatter3D 渲染  │    │ - scatter 渲染       │
│ - 点击选中/高亮    │    │ - visualMap 颜色映射  │
│ - 自动旋转        │    │ - 网格控制           │
│ - 相机距离自适应   │    │ - 数据采样           │
└──────────────────┘    └──────────────────────┘
```

### 设计模式

- **模板方法模式**：基类 `PointCloudRenderer` 定义了渲染生命周期（`init → setData → render → dispose`），子类只需实现 `render()` 和 `dispose()` 即可。
- **策略模式**：颜色映射策略可插拔，支持自定义 `colorMapper` 函数。
- **外观模式**：`PointCloudManager` 对外提供统一的高层接口，屏蔽了解析器、渲染器的内部细节。

---

## 3. 核心模块详解

### 3.1 渲染引擎基类 — `PointCloudRenderer`

**文件**: `src/core/PointCloudRenderer.js`

这是所有渲染器的基类，定义了渲染引擎的完整生命周期和公共能力。

#### 生命周期

```
init() → setData(points) → render() → dispose()
```

#### 核心职责

| 方法 | 说明 |
|------|------|
| `init()` | 初始化 ECharts 实例，绑定窗口 resize 事件 |
| `setData(points)` | 设置点云数据，自动计算数据范围（min/max X/Y/Z） |
| `render()` | **抽象方法**，子类必须实现，执行实际渲染 |
| `update(points)` | 更新数据并重新渲染（`setData` + `render` 的快捷组合） |
| `dispose()` | 销毁实例，释放 ECharts 资源，解绑事件 |
| `getChart()` | 获取当前 ECharts 实例 |
| `getDataRange()` | 获取数据范围（深拷贝副本） |

#### 颜色映射

基类提供了默认的 **Z 值 → 颜色** 映射函数 `defaultColorMapper`：

```
蓝 → 青 → 绿 → 黄 → 红 渐变
```

- 支持通过 `options.colorMapper` 传入自定义映射函数
- 自定义函数签名：`(zValue, minZ, maxZ) => string`（返回 CSS 颜色字符串）

#### 关键设计细节

```javascript
// 抽象类保护：防止直接实例化
if (new.target === PointCloudRenderer) {
    throw new Error('PointCloudRenderer 是抽象类，不能直接实例化');
}

// DOM 容器兼容：支持传入元素 ID 或 DOM 对象
this.dom = typeof dom === 'string' ? document.getElementById(dom) : dom;

// 数据范围计算：一次遍历完成所有维度的 min/max 统计
_calcDataRange() { /* O(n) 遍历 */ }
```

---

### 3.2 3D 渲染器 — `PointCloud3DRenderer`

**文件**: `src/renderers/PointCloud3DRenderer.js`

基于 **ECharts GL** 的 `scatter3D` 系列实现 3D 点云渲染。

#### 特有配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `pointSize` | `1` | 3D 点的大小 |
| `autoRotate` | `false` | 是否自动旋转场景 |
| `autoRotateSpeed` | `10` | 自动旋转速度 |
| `progressive` | `5000` | 渐进渲染阈值（超过此点数启用渐进渲染） |
| `progressiveThreshold` | `30000` | 渐进渲染步长 |
| `grid3D` | `{}` | 3D 坐标系自定义配置，会与默认配置合并 |
| `enableClick` | `true` | 是否启用点击选中功能 |
| `onPointClick` | `null` | 点击点回调 `(point) => void` |

#### 交互功能

- **点击选中**：点击点云中的点会高亮显示（放大 + 显示坐标标签）
- **取消选中**：点击空白区域取消选中
- **坐标面板**：通过 `onPointClick` 回调获取选中点的 X/Y/Z 坐标和索引

#### 相机距离自适应

```javascript
_calcCameraDistance() {
    const maxRange = Math.max(rangeX, rangeY, rangeZ);
    return Math.max(maxRange * 2.5, 100);
}
```

根据数据范围自动计算合适的相机距离，确保所有点都在视野内。

#### 性能优化

- 关闭动画（`animation: false`）
- 使用 `progressive` 渐进渲染
- 关闭后处理特效（`postEffect.enable: false`）
- 使用 `symbolSize` 控制点大小而非复杂图形

---

### 3.3 2D 渲染器 — `PointCloud2DRenderer`

**文件**: `src/renderers/PointCloud2DRenderer.js`

基于 ECharts 标准 `scatter` 系列实现 2D 点云渲染。

#### 特有配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `pointSize` | `2` | 2D 点的大小 |
| `symbol` | `'circle'` | 点的形状：`circle`、`rect`、`diamond`、`triangle` |
| `showGrid` | `true` | 是否显示网格 |
| `sampling` | `false` | 是否启用数据采样（大量点时提升性能） |
| `progressive` | `5000` | 渐进渲染阈值 |
| `progressiveThreshold` | `30000` | 渐进渲染步长 |

#### 特有方法

| 方法 | 说明 |
|------|------|
| `setPointSize(size)` | 设置点的大小并重新渲染 |
| `setSymbol(symbol)` | 设置点的形状并重新渲染 |
| `toggleGrid(show)` | 切换网格显示 |

#### 视觉增强

2D 渲染器额外使用了 ECharts 的 `visualMap` 组件，在图表右侧显示 Z 值的颜色映射图例，方便观察数据的高度分布。

---

### 3.4 文件解析器 — `TxtPointParser`

**文件**: `src/parsers/TxtPointParser.js`

负责解析 TXT 格式的点云文件。

#### 解析方法

| 方法 | 说明 |
|------|------|
| `parse(content)` | 解析字符串内容（同步） |
| `parseFile(file)` | 解析浏览器 File 对象（异步，使用 FileReader） |
| `parseFromUrl(url)` | 从 URL 获取并解析（异步，使用 fetch） |
| `serialize(mode, points)` | **静态方法**，将点数据序列化为 TXT 格式字符串 |

#### 解析流程

```
TXT 内容
  │
  ├─ 第 1 行 → 解析渲染模式 ("3d" 或 "2d")
  │
  └─ 第 2+ 行 → 逐行解析坐标 (x y z)
       │
       ├─ 跳过空行
       ├─ 校验数据合法性（可选）
       ├─ 检查点数上限（默认 100 万）
       └─ 进度回调（每 1% 报告一次）
```

#### 配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `validate` | `true` | 是否校验数据合法性（NaN、Infinity、格式错误） |
| `maxPoints` | `1000000` | 最大解析点数限制 |
| `onProgress` | `null` | 解析进度回调 `(progress: 0-1) => void` |

---

### 3.5 统一管理器 — `PointCloudManager`

**文件**: `src/PointCloudManager.js`

这是对外暴露的**核心入口**，封装了完整的"解析 → 初始化 → 渲染"流程。

#### 设计目标

- **简化调用**：调用方只需传入 DOM 容器和数据源，无需关心内部细节
- **自动适配**：根据文件第一行的渲染模式自动选择 3D/2D 渲染器
- **统一管理**：提供数据更新、模式切换、资源释放等统一接口

#### 数据加载方式

| 方法 | 数据来源 | 使用场景 |
|------|----------|----------|
| `loadFromContent(content)` | 字符串内容 | 已有文件内容在内存中 |
| `loadFromFile(file)` | 浏览器 File 对象 | 文件上传 `<input type="file">` |
| `loadFromUrl(url)` | URL 地址 | 从服务器加载点云文件 |

#### 内部流程（以 `loadFromContent` 为例）

```
loadFromContent(content)
  │
  ├─ 1. 创建 TxtPointParser 实例
  │
  ├─ 2. 调用 parser.parse(content)
  │     ├─ 解析第一行 → 获取渲染模式 (mode)
  │     └─ 解析后续行 → 获取点坐标数组 (points)
  │
  ├─ 3. 调用 this.init(mode)
  │     ├─ 根据 mode 创建 PointCloud3DRenderer 或 PointCloud2DRenderer
  │     └─ 调用 renderer.init() 初始化 ECharts 实例
  │
  ├─ 4. 调用 this.setData(points)
  │     └─ 调用 renderer.setData(points) 设置数据并计算范围
  │
  └─ 5. 调用 this.render()
        └─ 调用 renderer.render() 执行实际渲染
```

#### 其他能力

| 方法 | 说明 |
|------|------|
| `switchMode(mode)` | 切换渲染模式（保留当前数据） |
| `update(points)` | 更新数据并重新渲染 |
| `getRenderer()` | 获取当前渲染器实例 |
| `getMode()` | 获取当前渲染模式 |
| `dispose()` | 销毁实例，释放所有资源 |

---

### 3.6 入口导出 — `index.js`

**文件**: `src/index.js`

```javascript
// 核心基类
export { default as PointCloudRenderer } from './core/PointCloudRenderer.js';

// 渲染器
export { default as PointCloud3DRenderer } from './renderers/PointCloud3DRenderer.js';
export { default as PointCloud2DRenderer } from './renderers/PointCloud2DRenderer.js';

// 解析器
export { default as TxtPointParser } from './parsers/TxtPointParser.js';

// 统一管理器（默认导出）
export { default } from './PointCloudManager.js';
```

- **默认导出**：`PointCloudManager`（推荐使用）
- **命名导出**：所有模块均可按需引入

---

## 4. 数据流与渲染流程

### 完整数据流

```
用户输入 (TXT 文件 / 字符串 / URL)
        │
        ▼
┌─────────────────┐
│  TxtPointParser  │  ← 解析文件格式
│  parse(content)  │
└────────┬────────┘
         │ 返回 { mode, points }
         ▼
┌─────────────────┐
│ PointCloudManager│  ← 自动选择渲染器
│ init(mode)       │
└────────┬────────┘
         │ 创建渲染器实例
         ▼
┌─────────────────┐
│ PointCloudRenderer│  ← 基类处理公共逻辑
│ setData(points)  │
│ _calcDataRange() │
└────────┬────────┘
         │ 计算数据范围
         ▼
┌─────────────────┐
│ 3DRenderer       │  ← 子类执行实际渲染
│ 或 2DRenderer    │
│ render()         │
└────────┬────────┘
         │ 构建 ECharts option
         ▼
┌─────────────────┐
│   ECharts 实例    │  ← WebGL / Canvas 渲染
│ chart.setOption()│
└─────────────────┘
```

### 渲染流程时序

```
Manager.loadFromContent(content)
  │
  ├── [解析阶段] ──→ parser.parse(content)
  │                    ├── 按行分割
  │                    ├── 解析模式标识
  │                    └── 逐行解析坐标
  │
  ├── [初始化阶段] ──→ manager.init(mode)
  │                    ├── 创建渲染器
  │                    └── renderer.init()
  │                         ├── echarts.init(dom)
  │                         └── 绑定 resize 事件
  │
  ├── [数据阶段] ──→ manager.setData(points)
  │                    └── renderer.setData(points)
  │                         └── _calcDataRange()
  │
  └── [渲染阶段] ──→ manager.render()
                       └── renderer.render()
                            ├── 构建数据数组 [x, y, z, color]
                            ├── 构建 ECharts option
                            └── chart.setOption(option)
```

---

## 5. 调用方式

### 5.1 方式一：使用统一管理器（推荐）

这是最简洁的调用方式，适合大多数场景。

#### 从文件内容加载

```javascript
import PointCloudManager from 'point-cloud-renderer';

const manager = new PointCloudManager('chart-container', {
    onProgress: (p) => console.log(`解析进度: ${Math.round(p * 100)}%`),
    onReady: (renderer) => console.log('渲染完成'),
    onError: (err) => console.error('出错了:', err),
});

// 传入 TXT 格式的字符串内容
await manager.loadFromContent(txtContent);
```

#### 从 File 对象加载（浏览器文件上传）

```javascript
// HTML: <input type="file" id="fileInput" accept=".txt">
document.getElementById('fileInput').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const manager = new PointCloudManager('chart-container', {
        onProgress: (p) => updateProgressBar(p),
        onReady: (r) => hideLoading(),
        onError: (e) => showError(e.message),
    });

    await manager.loadFromFile(file);
});
```

#### 从 URL 加载

```javascript
const manager = new PointCloudManager('chart-container');
await manager.loadFromUrl('/data/points.txt');
```

### 5.2 方式二：直接使用渲染器

适合需要精细控制渲染过程的场景。

```javascript
import { PointCloud3DRenderer, TxtPointParser } from 'point-cloud-renderer';

// 1. 解析数据
const parser = new TxtPointParser();
const { mode, points } = parser.parse(txtContent);

// 2. 创建渲染器
const renderer = new PointCloud3DRenderer('chart-container', {
    pointSize: 1.5,
    autoRotate: true,
    autoRotateSpeed: 5,
    enableClick: true,
    onPointClick: (point) => {
        console.log(`选中点: (${point.x}, ${point.y}, ${point.z})`);
    },
});

// 3. 初始化
renderer.init();

// 4. 设置数据
renderer.setData(points);

// 5. 渲染
renderer.render();

// 6. 后续操作
renderer.setAutoRotate(false);     // 关闭自动旋转
renderer.setPointSize(2);          // 调整点大小
renderer.update(newPoints);        // 更新数据并重新渲染

// 7. 销毁
renderer.dispose();
```

### 5.3 方式三：浏览器文件上传

完整示例（纯 HTML + JS，无需构建工具）：

```html
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/echarts-gl@2.0.9/dist/echarts-gl.min.js"></script>
</head>
<body>
    <div id="container" style="width:100vw;height:100vh"></div>
    <input type="file" id="fileInput" accept=".txt">

    <script type="module">
        import PointCloudManager from './src/index.js';

        const manager = new PointCloudManager('container', {
            onProgress: (p) => console.log(`${Math.round(p * 100)}%`),
            onReady: (r) => console.log(`渲染完成，共 ${r.points.length} 个点`),
            onError: (e) => alert(e.message),
        });

        document.getElementById('fileInput').addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (file) await manager.loadFromFile(file);
        });
    </script>
</body>
</html>
```

### 5.4 方式四：从 URL 加载

```javascript
const manager = new PointCloudManager('container', {
    rendererOptions: {
        pointSize: 2,
        autoRotate: true,
    },
    onReady: (renderer) => {
        console.log(`渲染模式: ${renderer.options.renderMode}`);
        console.log(`数据范围:`, renderer.getDataRange());
    },
});

try {
    await manager.loadFromUrl('https://example.com/data/point-cloud.txt');
} catch (err) {
    console.error('加载失败:', err);
}
```

---

## 6. TXT 文件格式规范

### 文件格式

```
第一行: 渲染模式标识 ("3d" 或 "2d")
后续行: x y z (三个数值，空格分隔)
```

### 示例

```
3d
1.0 2.0 3.0
4.0 5.0 6.0
7.0 8.0 9.0
```

### 规范说明

| 规则 | 说明 |
|------|------|
| 第一行 | 必须为 `3d` 或 `2d`（大小写不敏感） |
| 坐标行 | 每行至少 3 个数值，空格分隔（支持多个空格） |
| 空行 | 自动跳过 |
| 额外列 | 每行超过 3 个数值时，只取前 3 个（x, y, z） |
| 编码 | 支持 UTF-8 |
| 换行符 | 兼容 `\n`、`\r\n` |

### 生成测试数据

项目提供了测试数据生成脚本：

```bash
# 生成 1000 个点
npm run generate-1k

# 生成 10000 个点
npm run generate-10k

# 生成 100000 个点
npm run generate-100k

# 生成 500000 个点
npm run generate-500k
```

---

## 7. 配置项参考

### PointCloudManager 配置

```javascript
const manager = new PointCloudManager(dom, {
    // 默认渲染模式（当文件第一行未指定时使用）
    renderMode: '3d',           // '3d' | '2d'

    // 传递给渲染器的额外选项
    rendererOptions: {},

    // 传递给解析器的选项
    parserOptions: {},

    // 解析进度回调 (progress: 0-1) => void
    onProgress: null,

    // 渲染完成回调 (renderer) => void
    onReady: null,

    // 错误回调 (error) => void
    onError: null,
});
```

### PointCloud3DRenderer 完整配置

```javascript
const renderer = new PointCloud3DRenderer(dom, {
    // 点的大小
    pointSize: 1,

    // 自动旋转
    autoRotate: false,
    autoRotateSpeed: 10,

    // 渐进渲染（大量点时的性能优化）
    progressive: 5000,           // 超过此点数启用渐进渲染
    progressiveThreshold: 30000, // 渐进渲染步长

    // 3D 坐标系自定义配置
    grid3D: {},

    // 自定义颜色映射函数
    colorMapper: (z, minZ, maxZ) => `rgb(...)`,

    // 点击交互
    enableClick: true,
    onPointClick: (point) => {},

    // 额外 ECharts 配置（会与默认配置合并）
    chartOptions: {},

    // 自动监听窗口 resize
    autoResize: true,
});
```

### PointCloud2DRenderer 完整配置

```javascript
const renderer = new PointCloud2DRenderer(dom, {
    // 点的大小和形状
    pointSize: 2,
    symbol: 'circle',            // 'circle' | 'rect' | 'diamond' | 'triangle'

    // 网格
    showGrid: true,

    // 数据采样（大量点时启用可提升性能）
    sampling: false,

    // 渐进渲染
    progressive: 5000,
    progressiveThreshold: 30000,

    // 自定义颜色映射
    colorMapper: null,

    // 额外 ECharts 配置
    chartOptions: {},

    // 自动监听窗口 resize
    autoResize: true,
});
```

---

## 8. 性能优化策略

### 渲染层优化

| 策略 | 说明 |
|------|------|
| **WebGL 硬件加速** | 3D 模式使用 ECharts GL 的 scatter3D，利用 GPU 渲染 |
| **渐进渲染 (Progressive)** | 超过 5000 个点时，分块渲染，避免主线程阻塞 |
| **关闭动画** | `animation: false`，避免大量点的动画帧率下降 |
| **关闭后处理** | 3D 模式关闭 postEffect，减少 GPU 开销 |
| **简化交互** | 关闭不必要的 emphasis 效果（2D 模式） |
| **数据采样** | 2D 模式支持 LTTB 采样算法，减少渲染点数 |

### 解析层优化

| 策略 | 说明 |
|------|------|
| **单次遍历** | 解析坐标的同时完成数据范围统计 |
| **预分配数组** | 使用 `new Array(length)` 预分配，避免动态扩容 |
| **进度回调节流** | 每 1% 报告一次进度，避免频繁回调 |
| **点数上限** | 默认 100 万点上限，防止内存溢出 |

### 内存管理

```javascript
// 及时释放资源
manager.dispose();

// 或直接操作渲染器
renderer.dispose();
```

---

## 9. 交互功能

### 3D 模式交互

| 交互 | 操作 | 说明 |
|------|------|------|
| **旋转** | 鼠标拖拽 | 任意角度观察点云 |
| **缩放** | 鼠标滚轮 | 拉近/拉远视角 |
| **平移** | 右键拖拽 | 平移场景 |
| **选中点** | 左键点击 | 高亮显示，触发 `onPointClick` 回调 |
| **取消选中** | 点击空白区域 | 取消高亮 |
| **自动旋转** | 配置开启 | 场景自动缓慢旋转，便于多角度观察 |

### 选中点回调

```javascript
const renderer = new PointCloud3DRenderer('container', {
    onPointClick: (point) => {
        if (point) {
            // 选中了点
            console.log(`X: ${point.x}, Y: ${point.y}, Z: ${point.z}, 索引: ${point.index}`);
        } else {
            // 取消了选中
            console.log('已取消选中');
        }
    },
});
```

### 编程式交互

```javascript
// 获取选中的点
const selected = renderer.getSelectedPoint();

// 清除选中状态
renderer.clearSelection();

// 切换自动旋转
renderer.setAutoRotate(true, 5);  // 开启，速度 5

// 调整点大小
renderer.setPointSize(2);
```

---

## 10. 常见问题

### Q: 为什么渲染后看不到点？

- 检查数据范围是否正常（`renderer.getDataRange()`）
- 检查 ECharts 和 ECharts GL 是否正确引入
- 检查容器是否有明确的宽高

### Q: 大量点（>10万）渲染卡顿怎么办？

- 确保 `animation: false`
- 调整 `progressive` 和 `progressiveThreshold` 参数
- 2D 模式下启用 `sampling: true`
- 减小 `pointSize`

### Q: 如何自定义点的颜色？

```javascript
const renderer = new PointCloud3DRenderer('container', {
    colorMapper: (z, minZ, maxZ) => {
        // 根据 z 值返回任意 CSS 颜色
        if (z > 0) return '#ff0000';  // 正值为红色
        return '#0000ff';              // 负值为蓝色
    },
});
```

### Q: 如何切换 3D/2D 模式？

```javascript
// 方式一：通过 Manager 切换
manager.switchMode('2d');  // 切换到 2D
manager.switchMode('3d');  // 切换到 3D

// 方式二：重新创建渲染器
const renderer = new PointCloud2DRenderer('container');
renderer.init();
renderer.setData(points);
renderer.render();
```

### Q: 如何获取 ECharts 实例做更多定制？

```javascript
const chart = renderer.getChart();
// 现在可以使用所有 ECharts API
chart.dispatchAction({ type: 'dataZoom', ... });
```

### Q: 支持哪些浏览器？

- Chrome 60+
- Firefox 55+
- Safari 11+
- Edge 80+

需要浏览器支持 WebGL（ECharts GL 依赖）。

---

> **提示**：完整的演示代码请参考 `demo/index.html`，其中包含了工具栏、文件上传、进度显示、坐标面板等完整的交互实现。
