const express = require('express');
const multer = require('multer');
const cors = require('cors');
const path = require('path');

const fs = require('fs');

const app = express();
const PORT = 3001;

app.use(cors());
app.use(express.json());

// ─── 日志工具（同时输出到终端 + 内存 + 文件）─────────
const logLines = [];
const LOG_FILE = path.join(__dirname, 'server.log');

function log(...args) {
  const line = args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ');
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  const full = `[${time}] ${line}`;
  console.log(line);
  logLines.push(full);
  if (logLines.length > 500) logLines.shift();
  // 追加写入文件
  fs.appendFile(LOG_FILE, full + '\n', () => {});
}

// ─── 请求日志中间件 ──────────────────────────────────
app.use((req, res, next) => {
  const start = Date.now();
  log(`→ ${req.method} ${req.url}`);
  res.on('finish', () => {
    const ms = Date.now() - start;
    log(`← ${req.method} ${req.url} [${res.statusCode}] ${ms}ms`);
  });
  next();
});

// 用内存存储上传文件
const upload = multer({ storage: multer.memoryStorage() });

// 服务端数据状态
let currentData = null;   // { mode, data }
let dataVersion = 0;      // 递增版本号，前端靠它检测变化

// ─── 文件解析（与 point-renderer.js 逻辑一致）────────────
function parseFile(text, onProgress) {
  const lines = text.split(/\r?\n/).filter(l => l.trim());
  if (lines.length < 2) throw new Error('文件格式错误：至少需要2行');

  const modeLine = lines[0].trim().toUpperCase();
  if (modeLine !== '3D' && modeLine !== '2D') {
    throw new Error('第一行必须是 "3D" 或 "2D"，当前为: ' + modeLine);
  }
  const mode = modeLine === '3D' ? '3d' : '2d';

  const dataLines = lines.slice(1);
  const total = dataLines.length;
  const result = [];
  const batchSize = 5000;

  for (let i = 0; i < total; i++) {
    const raw = dataLines[i].trim();
    if (!raw) continue;

    if (mode === '3d') {
      const parts = raw.split(/\s+/);
      if (parts.length < 3) continue;
      const x = parseFloat(parts[0]);
      const y = parseFloat(parts[1]);
      const z = parseFloat(parts[2]);
      if (isNaN(x) || isNaN(y) || isNaN(z)) continue;
      result.push([x, y, z]);
    } else {
      const parts = raw.split(',');
      if (parts.length < 3) continue;
      const vertices = [];
      for (let j = 0; j + 2 < parts.length; j += 3) {
        const vx = parseFloat(parts[j]);
        const vy = parseFloat(parts[j + 1]);
        const vz = parseFloat(parts[j + 2]);
        if (isNaN(vx) || isNaN(vy) || isNaN(vz)) continue;
        vertices.push([vx, vy, vz]);
      }
      if (vertices.length > 0) result.push(vertices);
    }

    if (onProgress && i % batchSize === 0) {
      onProgress(Math.round((i / total) * 100));
    }
  }
  if (onProgress) onProgress(100);

  return { mode, data: result };
}

// ─── API 路由 ──────────────────────────────────────────

// 查看日志（浏览器直接访问）
app.get('/api/logs', (req, res) => {
  const lines = req.query.lines ? parseInt(req.query.lines) : 100;
  const recent = logLines.slice(-lines);
  res.type('text/plain').send(recent.join('\n'));
});

// 上传 txt 文件
app.post('/api/upload', upload.single('file'), (req, res) => {
  try {
    if (!req.file) {
      log('[upload] 未收到文件');
      return res.status(400).json({ error: '未收到文件' });
    }

    log('[upload] 收到文件: ' + req.file.originalname);
    log('[upload] 文件大小: ' + (req.file.size / 1024).toFixed(2) + ' KB');

    const text = req.file.buffer.toString('utf-8');
    log('[upload] 开始解析...');
    log('[upload] 文件前200字符: ' + text.substring(0, 200).replace(/\n/g, '\\n'));

    const result = parseFile(text, (pct) => {
      if (pct % 20 === 0 || pct === 100) {
        log('[parse] 进度: ' + pct + '%');
      }
    });

    currentData = result;
    dataVersion++;

    const stats =
      result.mode === '3d'
        ? { mode: '3D 散点', pointCount: result.data.length }
        : { mode: '2D 多边形', polygonCount: result.data.length, vertexCount: result.data.reduce((s, p) => s + p.length, 0) };

    log('[upload] 解析完成:');
    log('  模式: ' + stats.mode);
    log('  版本号: ' + dataVersion);
    if (result.mode === '3d') {
      log('  点数: ' + stats.pointCount);
      log('  前5个点: ' + JSON.stringify(result.data.slice(0, 5)));
    } else {
      log('  多边形数: ' + stats.polygonCount);
      log('  总顶点数: ' + stats.vertexCount);
      log('  第一个多边形顶点数: ' + (result.data[0]?.length || 0) + ' 前3个顶点: ' + JSON.stringify(result.data[0]?.slice(0, 3)));
    }

    res.json({ success: true, version: dataVersion, stats });
  } catch (e) {
    log('[upload] 错误: ' + e.message);
    res.status(400).json({ error: e.message });
  }
});

// 查询数据状态（版本号 + 统计信息）
app.get('/api/data/status', (req, res) => {
  if (!currentData) {
    return res.json({ version: 0, hasData: false });
  }
  const stats =
    currentData.mode === '3d'
      ? { mode: '3D 散点', pointCount: currentData.data.length }
      : { mode: '2D 多边形', polygonCount: currentData.data.length, vertexCount: currentData.data.reduce((s, p) => s + p.length, 0) };
  res.json({ version: dataVersion, hasData: true, stats });
});

// 下载已解析的数据
app.get('/api/data', (req, res) => {
  if (!currentData) {
    log('[data] 暂无数据，返回 404');
    return res.status(404).json({ error: '暂无数据' });
  }
  const size = JSON.stringify(currentData).length;
  log('[data] 返回数据 version=' + dataVersion + ' 大小=' + (size / 1024).toFixed(2) + 'KB');
  res.json({ version: dataVersion, mode: currentData.mode, data: currentData.data });
});

// 提供示例文件
app.get('/sample-3d.txt', (req, res) => {
  res.sendFile(path.resolve(__dirname, '..', 'sample-3d.txt'));
});
app.get('/sample-2d.txt', (req, res) => {
  res.sendFile(path.resolve(__dirname, '..', 'sample-2d.txt'));
});

// 根路径
app.get('/', (req, res) => {
  res.json({ status: 'ok', message: 'PointCloud Backend Server', version: dataVersion });
});

app.listen(PORT, () => {
  log('Backend server running at http://localhost:' + PORT);
  log('查看日志: http://localhost:' + PORT + '/api/logs');
});
