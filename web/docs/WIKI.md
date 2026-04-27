# 点云3D渲染 Web 管理端

基于 pnpm workspace 的 monorepo 项目，使用 Vue3 + ECharts GL 实现大规模点云数据的 3D/2D 渲染与交互。

---

## 项目概述

本项目是一个 Web 前端应用，核心功能是读取包含三维坐标点（X Y Z）的纯文本文件，生成高质量 3D 散点云图进行可视化渲染。当文件中所有点的 Z 坐标均为 0 时，自动回退为 2D 散点图。支持高达 50 万量级的数据点，提供流畅的交互体验。

### 核心亮点

- **50 万点流畅渲染** — Web Worker 后台解析 + 采样控制 + 2D large 模式
- **3D/2D 自动切换** — 根据数据自动选择 scatter3D 或 scatter，无需手动配置
- **实时进度反馈** — 文件读取流式追踪 + 解析分阶段进度报告
- **点级交互** — 单击查看坐标，框选批量选中，选中列表导出

---

## 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| 前端框架 | Vue 3 | ^3.5 |
| 语言 | TypeScript | ^5.7 |
| 构建工具 | Vite | ^6.0 |
| 包管理 | pnpm (workspace) | >=8 |
| 路由 | Vue Router | ^4.5 |
| 状态管理 | Pinia | ^2.3 |
| UI 组件库 | Element Plus | ^2.9 |
| 2D 图表 | ECharts | ^5.5 |
| 3D 图表 | ECharts GL | ^2.0 |
| HTTP 客户端 | Axios | ^1.7 |
| 代码规范 | ESLint + Prettier | - |

---

## 项目结构

```
web/
├── pnpm-workspace.yaml              # monorepo 声明
├── package.json                     # 根配置 (dev / build / lint 脚本)
├── .npmrc                           # shamefully-hoist=true
├── docs/
│   └── WIKI.md                      # 项目文档
└── packages/
    └── web-admin/                   # 主应用包
        ├── package.json             # 依赖与脚本
        ├── vite.config.ts           # Vite 构建配置
        ├── tsconfig.json            # TypeScript 配置
        ├── index.html               # SPA 入口 HTML
        ├── public/
        │   ├── points_50w.txt       # 默认点集测试数据
        │   └── sphere_50w.txt       # 球体点集测试数据
        └── src/
            ├── main.ts              # 应用启动入口
            ├── App.vue              # 根布局组件
            ├── env.d.ts             # 类型声明
            ├── router/
            │   └── index.ts         # 路由配置
            ├── stores/
            │   └── points.ts        # Pinia 状态管理
            ├── workers/
            │   └── parsePoints.ts   # Web Worker 数据解析
            ├── views/
            │   └── PointCloud.vue   # 主页面 (控制面板 + 渲染区)
            ├── components/
            │   └── PointCloudRenderer.vue  # 渲染核心组件
            └── styles/
                └── index.css        # 全局样式
```

---

## 快速开始

### 环境要求

- Node.js >= 18
- pnpm >= 8

### 安装与运行

```bash
# 安装 pnpm（如未安装）
npm install -g pnpm

# 进入项目根目录
cd web

# 安装所有依赖
pnpm install

# 启动开发服务器
pnpm dev

# 构建生产版本
pnpm build

# 预览构建产物
pnpm preview
```

启动后在浏览器访问 `http://localhost:5173`。

### 加载数据

- **路径模式**: 将 `.txt` 文件放入 `public/` 目录，在页面输入框输入 `/文件名.txt`，点击"加载"
- **上传模式**: 切换到"上传文件"，点击选择本地 `.txt` 文件

### 数据格式

每行一个点，X Y Z 坐标以空格分隔：

```
11.453 78.795 85.285
32.688 64.608 92.904
25.393 16.959 38.854
```

- 至少需要 2 列（X Y），第 3 列为可选（Z，默认为 0）
- 当所有点 Z = 0 时，自动切换 2D 渲染模式
- 存在任意非零 Z 值时，使用 3D 渲染

---

## 核心功能

### 1. 数据加载管道

```
用户操作 → 文件读取 (流式) → Web Worker 解析 → Pinia Store → 渲染组件
              ↓                    ↓
         进度百分比            进度百分比
```

- **流式读取**: 利用 `ReadableStream` API 逐块读取文件，实时计算下载进度
- **Web Worker 解析**: 将文本解析放入独立线程，每 20,000 行回报一次进度，主线程零阻塞
- **错误容错**: 自动跳过空行和格式异常的行

### 2. 渲染引擎

| 模式 | ECharts 系列 | 渲染器 | 优化策略 |
|------|-------------|--------|---------|
| 3D | `scatter3D` | WebGL | 透视投影、光照阴影、可旋转视角 |
| 2D | `scatter` | Canvas | `large: true` + `largeThreshold: 2000` |

- `grid3D.viewControl` 配置初始视角 (alpha: 25°, beta: 45°)
- 支持鼠标旋转（3D）、缩放、平移

### 3. 渲染参数调节

| 参数 | 范围 | 说明 |
|------|------|------|
| 点大小 | 1 - 10 | 控制每个散点的像素尺寸 |
| 透明度 | 0.1 - 1.0 | 散点透明度，低透明度可查看密度分布 |
| 采样率 | 1% - 100% | 等间隔下采样，低配机器可降低采样提升流畅度 |

### 4. 交互功能

#### 单击查询

在图表上单击任意散点，左侧面板实时显示该点的索引和 X / Y / Z 精确坐标（4 位小数）。

- 实现方式：监听 ECharts `click` 事件，解析 `dataIndex` 和 `value`
- 同时支持 2D scatter 和 3D scatter3D

#### 框选

| 模式 | 触发方式 | 技术实现 |
|------|---------|---------|
| 2D | 点击右上角笔刷图标，拖拽矩形 | ECharts `brush` 组件 + `toolbox.feature.brush` |
| 3D | 直接在图表区域拖拽鼠标 | 自定义 HTML overlay + `convertToPixel` 投影检测 |

框选完成后：
- 左侧"框选结果"面板显示选中点总数
- 列表展示前 50 个点的索引和坐标
- 点击"清除"按钮重置选择

---

## 架构设计

### 组件树

```
App.vue
└── el-container
    ├── el-header (标题栏)
    └── el-main
        └── router-view
            └── PointCloud.vue (主页面)
                ├── el-aside (控制面板)
                │   ├── 数据源配置
                │   ├── 渲染设置
                │   ├── 数据统计
                │   ├── 单击点信息
                │   └── 框选结果
                └── main (渲染区域)
                    ├── 空状态占位
                    ├── 加载进度 overlay
                    ├── 错误状态 overlay
                    └── PointCloudRenderer.vue
```

### 数据流

```
points.txt  ──fetch/upload──▶  loadFile()  ──text──▶  Web Worker  ──ParseMessage──▶  Pinia Store
                                                                                           │
                                                                                    points / is3D
                                                                                           │
                                                                                    sampledPoints (computed)
                                                                                           │
                                                                              PointCloudRenderer.vue
                                                                                      │
                                                                              ECharts GL scatter3D
```

### 状态管理 (Pinia Store)

```typescript
// 核心状态
points: Point3D[]        // 解析后的所有点
status: 'idle' | 'loading' | 'parsing' | 'ready' | 'error'
progress: number         // 加载/解析进度 (0-100)
is3D: boolean            // 自动检测：是否有非零 Z 值

// 交互状态
clickedPoint: Point3D | null    // 最近单击的点
clickedIndex: number            // 最近单击点的索引
selectedIndices: Set<number>    // 框选选中的点索引集合
selectedPoints: computed        // 选中点的详情列表
```

---

## 关键实现细节

### Web Worker 解析 (`parsePoints.ts`)

```
主线程                           Worker 线程
   │                                │
   ├─ new Worker() ─────────────────┤
   ├─ postMessage({ text }) ───────▶│
   │                                ├─ split('\n')
   │                                ├─ for i in lines:
   │                                │    parseFloat × 3
   │                                │    检测 hasZ
   │                                │    if i % 20000 === 0:
   │  ◀── { type: 'progress',       │       postMessage(progress)
   │        progress: N% } ─────────┤
   │                                ├─ postMessage({ type: 'result',
   │  ◀── { type: 'result',         │     points, is3D })
   │        points, is3D } ─────────┤
   ├─ store.setPoints()             │
   └─ worker.terminate()            └─ (结束)
```

### 3D 框选投影算法 (`findPointsInRect`)

```typescript
function findPointsInRect(x1, y1, x2, y2) {
  const pts = props.points
  const indices = []

  for (let i = 0; i < pts.length; i += 10000) {
    for (let j = i; j < Math.min(i + 10000, pts.length); j++) {
      // 将 3D 数据坐标投影到屏幕像素坐标
      const pxl = chart.convertToPixel(
        { seriesIndex: 0 },
        [pts[j].x, pts[j].y, pts[j].z]
      )
      // 判断是否在矩形区域内
      if (pxl[0] >= x1 && pxl[0] <= x2 && pxl[1] >= y1 && pxl[1] <= y2) {
        indices.push(j)
      }
    }
  }
  return indices
}
```

- 利用 ECharts 的 `convertToPixel` API 将 3D 世界坐标转换为屏幕像素坐标
- 批量处理（每批 10,000 点），对 NaN 结果做防御性检查
- 适用于 scatter3D 的透视投影

### 2D/3D 自动检测

在 Worker 解析阶段即完成检测：

```typescript
let hasZ = false
for (const line of lines) {
  // ... 解析 x, y, z ...
  if (z !== 0) hasZ = true   // 任意非零 Z 即判定为 3D
}
// 结果回传: { is3D: hasZ }
```

### 渲染器切换

当 `is3D` 属性变化时（例如加载不同数据集），渲染器会完全重建：

```typescript
function initChart() {
  const renderer = props.is3D ? 'webgl' : 'canvas'
  chartInstance.value?.dispose()              // 销毁旧实例
  chartInstance.value = echarts.init(el, undefined, { renderer })
  // 重新绑定事件并设置新 option
}
```

- 3D 强制使用 WebGL 渲染器
- 2D 使用 Canvas 渲染器（配合 `large: true` 实现高性能大数据量渲染）
- 切换时完整重建 ECharts 实例，避免渲染器冲突

---

## 数据文件说明

### 原始点集 (`points_50w.txt`)

- 500,000 个点，约 11 MB
- 通用测试数据，包含非零 Z 值，3D 渲染

### 球体点集 (`sphere_50w.txt`)

- 500,000 个点，实心球体（半径 50）
- 生成算法：球体内均匀分布 `r = R · rand^(1/3)`
- 用于验证 3D 渲染效果和交互功能

---

## 开发指南

### 添加新路由

在 `src/router/index.ts` 中注册：

```typescript
const routes: RouteRecordRaw[] = [
  { path: '/', name: 'PointCloud', component: () => import('@/views/PointCloud.vue') },
  { path: '/new-page', name: 'NewPage', component: () => import('@/views/NewPage.vue') },
]
```

### 添加新 Store

在 `src/stores/` 下创建新的 store 文件，使用 Pinia 的 Setup Store 语法：

```typescript
export const useMyStore = defineStore('myStore', () => {
  const data = ref<MyType[]>([])
  const doubled = computed(() => data.value.length * 2)
  function reset() { data.value = [] }
  return { data, doubled, reset }
})
```

### 修改 ECharts 渲染配置

编辑 `src/components/PointCloudRenderer.vue` 中的 `build2DOption()` 或 `build3DOption()` 函数，按 [ECharts 配置文档](https://echarts.apache.org/zh/option.html) 调整。

---

## 常见问题

**Q: 3D 模式下框选没有反应？**
A: 确保拖动距离足够大（≥ 5px）。三角面片密集时可能有少数点被遗漏，可适当降低采样率后重试。

**Q: 50 万点渲染卡顿？**
A: 调低采样率至 10%-25%，或减小点大小。3D 模式下 WebGL 性能取决于显卡。

**Q: 如何添加新的测试数据？**
A: 将 `.txt` 文件放入 `public/` 目录，在页面路径输入框输入 `/文件名.txt` 加载。

**Q: 构建报错 `vue-tsc`？**
A: 检查 TypeScript 类型错误，`pnpm lint` 可查看具体问题。



 echart在这里是怎么使用的，如何调用的？                                                                                                                                                                                                                              
                                         
● ECharts 的使用全在 PointCloudRenderer.vue 这一个文件中。我按调用链路来讲。                                                                                                                                                                                          
                                                                                                                                                                                                                                                                    
  1. 导入                                                                                                                                                                                                                                                             
                                                                                                                                                                                                                                                                      
  import * as echarts from 'echarts'   // ECharts 核心                                                                                                                                                                                                                
  import 'echarts-gl'                   // ECharts GL 插件（副作用导入，注册 scatter3D 等 3D 系列）                                                                                                                                                                   
                                                            
  echarts-gl 是副作用导入，它会在 ECharts 上注册 scatter3D、grid3D、xAxis3D 等 3D 组件，之后 echarts.init() 才能识别这些类型。

  2. 实例创建

  在 initChart() 中，每次数据或模式变化时完整重建实例：

  function initChart() {
    // 1. 根据 2D/3D 选不同渲染器
    const renderer = props.is3D ? 'webgl' : 'canvas'

    // 2. 先销毁旧实例（切换 2D↔3D 时必须重建，renderer 不同无法复用）
    if (chartInstance.value) {
      chartInstance.value.off('click')
      chartInstance.value.off('brushSelected')
      chartInstance.value.dispose()
      chartInstance.value = null
    }

    // 3. 创建新实例：绑定到 DOM 容器，指定渲染器
    chartInstance.value = echarts.init(chartRef.value, undefined, { renderer })

    // 4. 绑定事件
    chartInstance.value.on('click', handleClick)
    chartInstance.value.on('brushSelected', handleBrushSelected)

    // 5. 构建配置并设置
    const option = props.is3D ? build3DOption() : build2DOption()
    chartInstance.value.setOption(option, true)  // true = notMerge，全量替换
  }

  关键点：
  - 3D 必须用 webgl 渲染器（scatter3D 依赖 WebGL）
  - 2D 用 canvas 渲染器（配合 large: true 有更好的大数据性能）
  - 切换模式时 dispose() 销毁旧实例再 init() 创建新的，因为 renderer 不能运行时切换

  3. 配置构建 — 2D 散点图

  function build2DOption(): echarts.EChartsOption {
    const data = props.points.map((p) => [p.x, p.y])  // Vue props → 二维数组

    return {
      backgroundColor: '#0f0f23',
      toolbox: { feature: { brush: { type: ['rect', 'clear'] } } },  // 框选工具栏按钮
      brush: {
        toolbox: ['rect', 'clear'],
        brushStyle: { borderColor: '#409EFF', color: 'rgba(64,158,255,0.2)' },
      },
      xAxis: { type: 'value', ... },   // 数值轴
      yAxis: { type: 'value', ... },
      series: [{
        type: 'scatter',               // 2D 散点系列
        data,
        large: true,                   // 大数据优化模式
        largeThreshold: 2000,          // 超过 2000 点自动启用
        symbolSize: props.symbolSize,
        itemStyle: { opacity: props.opacity },
      }],
    }
  }

  - large: true 是性能关键 — ECharts 会跳过逐个绘制，改用批量像素渲染，500k 点也能流畅
  - brush + toolbox 提供框选功能

  4. 配置构建 — 3D 散点图

  function build3DOption(): echarts.EChartsOption {
    const data = props.points.map((p) => [p.x, p.y, p.z])

    return {
      backgroundColor: '#0f0f23',
      grid3D: {                        // 3D 坐标系（来自 echarts-gl）
        viewControl: {                 // 相机控制
          projection: 'perspective',   // 透视投影
          distance: 200,               // 相机距离
          alpha: 25, beta: 45,         // 初始视角角度
        },
        boxWidth: 100, boxHeight: 100, boxDepth: 100,
        light: {
          main: { intensity: 1.5, shadow: true },
          ambient: { intensity: 0.5 },
        },
      },
      xAxis3D: { type: 'value', ... },  // 3D 坐标轴（来自 echarts-gl）
      yAxis3D: { type: 'value', ... },
      zAxis3D: { type: 'value', ... },
      series: [{
        type: 'scatter3D',             // 3D 散点系列（来自 echarts-gl）
        data,
        symbolSize: props.symbolSize,
        itemStyle: { opacity: props.opacity },
      }],
    }
  }

  - grid3D / xAxis3D / scatter3D 都是 echarts-gl 注册的组件
  - viewControl 控制相机，默认提供了旋转/缩放/平移的鼠标交互

  5. 事件绑定

  // 单击 — 查看点坐标
  chartInstance.value.on('click', (params) => {
    if (params.seriesType === 'scatter3D' || params.seriesType === 'scatter') {
      const [x, y, z] = params.value
      emit('point-click', { index: params.dataIndex, x, y, z: z ?? 0 })
    }
  })

  // 框选完成 — 批量选中（仅 2D brush 触发）
  chartInstance.value.on('brushSelected', (params) => {
    const indices = []
    for (const batch of params.batch) {
      for (const sel of batch.selected) {
        indices.push(...sel.dataIndex)
      }
    }
    emit('points-selected', { indices })
  })

  - click 事件在 2D 和 3D 下都生效，params.value 直接给到 [x, y, z] 原始数据
  - brushSelected 仅 2D 的 brush 组件触发，返回被框中的 dataIndex 列表

  6. 3D 自定义框选（绕过 ECharts）

  3D 模式下 ECharts 的 brush 不生效，所以自己画选择框 + 调用 convertToPixel 做投影检测：

  // 鼠标拖拽 → 画一个 HTML 虚线矩形 overlay
  function onMouseDown(e) { /* 记录起点，document 监听 mousemove/mouseup */ }

  // 松开时：遍历所有点，用 convertToPixel 投影到屏幕坐标，判断是否在矩形内
  function findPointsInRect(x1, y1, x2, y2) {
    for (let j = 0; j < pts.length; j++) {
      const pxl = chart.convertToPixel(           // 3D → 2D 屏幕坐标
        { seriesIndex: 0 },
        [pts[j].x, pts[j].y, pts[j].z]
      )
      if (pxl[0] >= x1 && pxl[0] <= x2 && pxl[1] >= y1 && pxl[1] <= y2) {
        indices.push(j)                           // 命中
      }
    }
  }

  convertToPixel 是 ECharts 提供的坐标转换 API，输入数据坐标 [x, y, z]，输出当前视角下的屏幕像素坐标 [screenX, screenY]。

  7. 响应式更新

  Vue watch 监听 props 变化，变化时重建整个图表：

  watch(
    () => [props.points, props.is3D, props.symbolSize, props.opacity],
    () => { initChart() }   // 任何参数变化 → 销毁 + 重建
  )

  完整调用链路图

  PointCloud.vue                     PointCloudRenderer.vue
       │                                    │
       ├─ sampledPoints ──────────────────▶ props.points
       ├─ store.is3D ────────────────────▶ props.is3D
       ├─ symbolSize ────────────────────▶ props.symbolSize
       ├─ opacity ───────────────────────▶ props.opacity
       │                                    │
       │                              watch 触发
       │                                    │
       │                              initChart()
       │                              ├── echarts.init(div, null, { renderer })
       │                              ├── .on('click', ...)
       │                              ├── .on('brushSelected', ...)
       │                              ├── build3DOption() / build2DOption()
       │                              └── .setOption(option, true)
       │                                    │
       ◀── @point-click ─────────────── emit (单击点坐标)
       ◀── @points-selected ─────────── emit (框选索引列表)

  简单说就是：Vue 传 props → watch 触发 → initChart 销毁旧实例 + 创建新实例 + setOption → ECharts 接管渲染 → 事件 emit 回 Vue。
