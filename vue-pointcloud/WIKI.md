# Vue PointCloud 前后端调用架构详解

## 1. 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│  浏览器 (Frontend)                                           │
│  ┌─────────┐    ┌──────────────┐    ┌──────────────────────┐ │
│  │ App.vue │───▶│ PointCloud   │───▶│ PointRenderer        │ │
│  │ (主页面) │    │ .vue (组件)   │    │ (ECharts 渲染引擎)    │ │
│  └────┬────┘    └──────────────┘    └──────────────────────┘ │
│       │                                                       │
│       │ 上传文件 / 轮询 / 下载数据                              │
│       ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  API 调用层 (fetch)                                      │ │
│  │  - POST /api/upload     上传 txt 文件                    │ │
│  │  - GET  /api/data/status 轮询版本号                       │ │
│  │  - GET  /api/data        下载结构化数据                   │ │
│  │  - GET  /api/logs        在浏览器查看后端日志              │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
        │  HTTP (localhost:3001)
        ▼
┌──────────────────────────────────────────────────────────────┐
│  Node.js 后端 (server.js)                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ multer       │  │ parseFile()  │  │ 内存存储            │ │
│  │ 接收文件上传  │──▶│ 解析 txt 文本 │──▶│ currentData        │ │
│  │              │  │              │  │ dataVersion        │ │
│  └──────────────┘  └──────────────┘  └────────────────────┘ │
│                                                              │
│  日志系统: 终端 console + 内存 logLines + 文件 server.log     │
└──────────────────────────────────────────────────────────────┘
```

## 2. 数据流详解

### 2.1 完整时序图

```
用户点击"选择文件"
    │
    ▼
① App.vue: handleFile()
    │  new FormData() 封装文件
    │  POST /api/upload
    ▼
② server.js: 接收文件
    │  multer 解析 multipart/form-data
    │  parseFile() 解析文本内容
    │  currentData = { mode, data }
    │  dataVersion++
    │  返回 { success, version, stats }
    ▼
③ App.vue: 收到上传成功
    │  downloadData()
    │  GET /api/data → 拿到结构化数据
    │  serverData = { mode, data }
    ▼
④ App.vue: 启动轮询
    │  setInterval 每秒执行
    │  GET /api/data/status
    │  比较 version 是否变化
    ▼
⑤ App.vue → PointCloud.vue
    │  :server-data="serverData"  (prop 传递)
    ▼
⑥ PointCloud.vue: watch(serverData)
    │  renderer.setData(mode, data)
    │  renderer.render()
    ▼
⑦ PointRenderer: 渲染到 ECharts
```

### 2.2 核心设计：为什么不直接把 txt 传给渲染器

| | 旧逻辑 | 新逻辑 |
|---|---|---|
| 文件读取 | FileReader 本地读取 | FormData 上传到后端 |
| 解析位置 | 前端 `renderer.parseAndRender(text)` | 后端 `parseFile(text)` |
| 传给渲染器 | 原始文本字符串 | 结构化 `{ mode, data }` |
| 触发方式 | prop `dataText` 变化 | prop `serverData` 变化 |

新逻辑的优势：
- **前后端分离**: 解析逻辑集中在服务端，便于复用和统一管理
- **版本号机制**: 一个客户端上传，其他客户端轮询到版本变化后自动更新
- **数据校验**: 后端可以做格式校验、数据清洗后再下发
- **可扩展**: 后端可以接入数据库、缓存、消息队列等

## 3. 前端实现详解

### 3.1 App.vue — 主控逻辑

文件位置: `src/App.vue`

#### 文件上传 (替代原来的 FileReader)

```js
const API_BASE = 'http://localhost:3001';

async function handleFile(e) {
  const file = e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/api/upload`, {
    method: 'POST',
    body: formData,   // 浏览器自动设置 Content-Type: multipart/form-data
  });
  const result = await res.json();
  // result = { success: true, version: 1, stats: { mode, pointCount } }

  knownVersion = result.version;
  await downloadData();
  startPolling();
}
```

关键点:
- 用 `FormData` 封装文件，**不需要手动设置 `Content-Type`**，浏览器自动处理 boundary
- 上传成功后记录版本号，立即下载数据并启动轮询

#### 轮询监听 (核心机制)

```js
let pollTimer = null;
let knownVersion = 0;

function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/data/status`);
      const status = await res.json();
      // status = { version: 1, hasData: true, stats: {...} }
      if (status.version > knownVersion && status.hasData) {
        knownVersion = status.version;
        await downloadData();
      }
    } catch {
      // 后端未就绪时静默忽略
    }
  }, 1000);  // 每秒轮询一次
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

onBeforeUnmount(() => stopPolling());  // 组件销毁时清理
```

设计要点:
- `knownVersion` 记录已下载的版本号，避免重复下载
- 每秒请求 `/api/data/status` — 这个接口只返回版本号和统计（几十字节），非常轻量
- 仅在 `version > knownVersion` 时才调用 `downloadData()` 下载完整数据
- `onBeforeUnmount` 中清理定时器，防止内存泄漏

#### 下载数据

```js
async function downloadData() {
  const res = await fetch(`${API_BASE}/api/data`);
  const result = await res.json();
  // result = { version, mode: '3d'|'2d', data: [...] }
  serverData.value = { mode: result.mode, data: result.data };
}
```

`serverData` 是响应式 ref，变化后自动触发 PointCloud 组件的 watch。

### 3.2 PointCloud.vue — 渲染组件

文件位置: `src/components/PointCloud.vue`

```js
const props = defineProps({
  serverData: { type: Object, default: null },  // 结构化的 { mode, data }
  options: { type: Object, default: () => ({}) },
});

watch(() => props.serverData, (val) => {
  if (val) doRender(val);
});

function doRender({ mode, data }) {
  if (!renderer) return;
  nextTick(() => {
    renderer.setData(mode, data);   // 跳过解析，直接设置数据
    renderer.render();               // 渲染
    emit('rendered', renderer.getStats());
  });
}
```

**旧 vs 新:**

```
旧: watch(dataText) → renderer.parseAndRender(text)
                         ↓
                    parse() + render() 一步完成

新: watch(serverData) → renderer.setData(mode, data)
                         renderer.render()
                         ↓
                   数据已由后端解析好，直接渲染
```

### 3.3 PointRenderer — 渲染引擎

文件位置: `src/utils/point-renderer.js`

核心 API:

| 方法 | 用途 |
|------|------|
| `new PointRenderer(container, options)` | 构造器，传入 DOM 容器 |
| `.parse(text, onProgress)` | 解析文本，返回 `{mode, data}` |
| `.render()` | 渲染已设置的数据 |
| `.setData(mode, data)` | 直接设置结构化数据（跳过解析） |
| `.parseAndRender(text, onProgress)` | 一步完成解析+渲染（旧逻辑用） |
| `.onClick(fn)` | 点击回调 |
| `.dispose()` | 销毁实例 |
| `.getStats()` | 获取统计信息 |
| `.resize()` | 窗口缩放时调用 |

数据格式:

```
3D 模式: data = [[x,y,z], [x,y,z], ...]
2D 模式: data = [
           [[x,y,z], [x,y,z], ...],  // 多边形1的顶点
           [[x,y,z], [x,y,z], ...],  // 多边形2的顶点
         ]
```

## 4. 后端实现详解

文件位置: `server.js`

### 4.1 依赖

```
express  — Web 框架
multer   — 文件上传中间件 (解析 multipart/form-data)
cors     — 跨域支持
```

### 4.2 核心状态

```js
let currentData = null;   // { mode: '3d'|'2d', data: Array }
let dataVersion = 0;      // 每次上传成功 +1，前端通过它检测变化
```

使用内存存储，重启后数据丢失。需要持久化可改为写文件或数据库。

### 4.3 API 接口一览

| 方法 | 路径 | 说明 | 请求 | 响应 |
|------|------|------|------|------|
| POST | `/api/upload` | 上传 txt 文件 | FormData (file 字段) | `{success, version, stats}` |
| GET | `/api/data/status` | 查询数据状态 | — | `{version, hasData, stats}` |
| GET | `/api/data` | 下载结构化数据 | — | `{version, mode, data}` |
| GET | `/api/logs` | 查看日志 | `?lines=50` | 纯文本 |
| GET | `/` | 服务状态 | — | `{status, message, version}` |

### 4.4 文件解析逻辑

```js
function parseFile(text, onProgress) {
  // 第一行决定模式: "3D" 或 "2D"
  const modeLine = lines[0].trim().toUpperCase();
  const mode = modeLine === '3D' ? '3d' : '2d';

  // 3D: 空格分隔坐标，每行一个点
  //   格式: x y z
  // 2D: 逗号分隔坐标，每行一串顶点  
  //   格式: x,y,z,x2,y2,z2,...
}
```

支持的 txt 文件格式:

**3D 点云** (`sample-3d.txt`):
```
3D
0.5 1.2 0.3
1 2.1 0.8
1.5 0.9 1.2
```

**2D 多边形** (`sample-2d.txt`):
```
2D
-1.5,-1,0,1.5,-1,0,0,1.5,0,-1.5,-1,0
-0.5,-0.5,0,0.5,-0.5,0,0,0.5,0,-0.5,-0.5,0
```

### 4.5 日志系统

日志同时输出到三个通道:

| 通道 | 实现 | 用途 |
|------|------|------|
| 终端 stdout | `console.log` | 开发者本地调试 |
| 内存数组 | `logLines[]` 最近500条 | 通过 `/api/logs` 浏览器查看 |
| 文件 | `server.log` 追加写入 | 持久化，重启后保留 |

```js
function log(...args) {
  const line = args.map(a =>
    typeof a === 'object' ? JSON.stringify(a) : String(a)
  ).join(' ');
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  const full = `[${time}] ${line}`;

  console.log(line);                          // → 终端
  logLines.push(full);                        // → 内存
  if (logLines.length > 500) logLines.shift();
  fs.appendFile(LOG_FILE, full + '\n', () => {}); // → 文件
}
```

在浏览器访问 `http://localhost:3001/api/logs` 即可看到:
```
[14:32:05] → POST /api/upload
[14:32:05] [upload] 收到文件: large-3d-500000.txt
[14:32:05] [upload] 文件大小: 11652.80 KB
[14:32:06] [parse] 进度: 20%
[14:32:07] [parse] 进度: 40%
[14:32:08] [parse] 进度: 60%
[14:32:09] [parse] 进度: 80%
[14:32:10] [parse] 进度: 100%
[14:32:10] [upload] 解析完成:
[14:32:10]   模式: 3D 散点
[14:32:10]   版本号: 1
[14:32:10]   点数: 500000
[14:32:10]   前5个点: [[0.5,1.2,0.3],[1,2.1,0.8],...]
[14:32:10] ← POST /api/upload [200] 5234ms
[14:32:10] → GET /api/data
[14:32:10] [data] 返回数据 version=1 大小=11800.50KB
[14:32:10] ← GET /api/data [200] 89ms
```

## 5. 移植指南

### 5.1 最小移植 (只换渲染引擎)

如果你的项目有不同渲染引擎，只需要复用后端和轮询逻辑:

```
你的前端                           Node.js 后端 (复用 server.js)
┌──────────┐                      ┌──────────────────────┐
│ 你的渲染器 │◀─── GET /api/data ────│ POST /api/upload     │
│          │    GET /api/status   │ 文件解析 → 结构化数据   │
└──────────┘                      └──────────────────────┘
```

**步骤:**

1. 复制 `server.js` 到你的项目
2. 安装依赖: `npm install express multer cors`
3. 在你前端中加这段代码:

```js
const API = 'http://localhost:3001';

// 上传文件
async function uploadFile(file) {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(`${API}/api/upload`, { method: 'POST', body: fd });
  return res.json();  // { success, version, stats }
}

// 下载数据
async function fetchData() {
  const res = await fetch(`${API}/api/data`);
  return res.json();  // { version, mode, data }
}

// 轮询监听
let version = 0;
setInterval(async () => {
  try {
    const status = await (await fetch(`${API}/api/data/status`)).json();
    if (status.version > version) {
      version = status.version;
      const result = await fetchData();
      // → 把 result.mode 和 result.data 交给你的渲染器
      yourRenderer.setData(result.mode, result.data);
      yourRenderer.render();
    }
  } catch {}
}, 1000);
```

### 5.2 更换数据格式

如果你的数据不是点云 txt，而是 JSON / CSV / 自定义格式:

1. 修改 `server.js` 中的 `parseFile()` 函数
2. 调整 `currentData` 的结构定义
3. 前端 `downloadData()` 后的处理对应修改

```js
// 示例: 支持 JSON 格式
function parseFile(text) {
  const json = JSON.parse(text);
  return { mode: json.type, data: json.items };
}
```

### 5.3 从轮询升级为 WebSocket (实时性要求高时)

后端 (`server.js`):
```js
const { WebSocketServer } = require('ws');
const wss = new WebSocketServer({ port: 3002 });

// 上传成功后广播通知所有客户端
wss.clients.forEach(client => {
  client.send(JSON.stringify({ type: 'data-changed', version: dataVersion }));
});
```

前端:
```js
const ws = new WebSocket('ws://localhost:3002');
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'data-changed') downloadData();
};
```

### 5.4 内存存储替换为文件持久化

```js
const DATA_FILE = path.join(__dirname, 'data.json');

function saveData(data) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(data));
}

function loadData() {
  if (fs.existsSync(DATA_FILE)) {
    currentData = JSON.parse(fs.readFileSync(DATA_FILE, 'utf-8'));
  }
}

// 启动时恢复数据
loadData();
```

### 5.5 目录结构移植

```
你的项目/
├── server.js              ← 复制，端口和解析逻辑可能需要改
├── server.log             ← 自动生成，日志文件
└── src/
    ├── App.vue            ← 参考: handleFile / startPolling / downloadData
    ├── components/
    │   └── YourRenderer.vue ← 参考: watch(serverData) → setData + render
    └── utils/
        └── your-engine.js ← 你的渲染引擎
```

## 6. 启动命令

```bash
# 终端1: 后端 (端口 3001)
cd vue-pointcloud
node server.js

# 终端2: 前端 (端口 5173)
npm run dev
```

- 前端页面: `http://localhost:5173`
- 后端日志: `http://localhost:3001/api/logs`

## 7. 常见问题

**Q: 为什么不直接用 Vite proxy 代理 `/api` 到后端?**
A: 两种方式都可以。当前方案前端直接 fetch `localhost:3001`，后端加 CORS。用 Vite proxy 的话不需要 CORS 且部署时同域更方便，只需在 `vite.config.js` 加:

```js
export default defineConfig({
  server: {
    proxy: { '/api': 'http://localhost:3001' }
  }
});
```

然后把 `API_BASE` 改为空字符串即可。

**Q: 轮询 1 秒会不会压力太大?**
A: `/api/data/status` 只返回几十字节 JSON（版本号+统计），QPS 为 1，几乎零压力。如需更低延迟可改用 WebSocket。

**Q: 大文件（50万+点）传输慢怎么办?**
A: 当前 `/api/data` 返回完整 JSON。可优化方向:
- 分页传输
- ArrayBuffer 二进制减少体积
- gzip 压缩（express 可加 compression 中间件）

**Q: 后端重启后数据丢失?**
A: 当前用内存存储。参考 5.4 节改为文件持久化，或接入数据库。
