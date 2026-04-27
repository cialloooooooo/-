/**
 * PointCloudRenderer — 基于 ECharts 的 XYZ 点云渲染器
 *
 * 使用方式:
 *   import { PointCloudRenderer } from './PointCloudRenderer.js';
 *   const renderer = new PointCloudRenderer(document.getElementById('chart'));
 *   await renderer.loadPoints([[x,y,z], ...]);
 *   renderer.setMode('3d');
 *   renderer.on('progress', ({ percent, text }) => updateProgressBar(percent, text));
 */

const CHUNK_SIZE = 10000;

const COLORS = {
  spectral: ['#5e4fa2','#3288bd','#66c2a5','#abdda4','#e6f598','#fee08b','#fdae61','#f46d43','#d53e4f','#9e0142'],
  cool: ['#0d47a1','#1565c0','#1976d2','#1e88e5','#42a5f5','#64b5f6','#90caf9','#bbdefb','#e3f2fd','#ffffff'],
  warm: ['#4a0e0e','#7b241c','#b03a2e','#e74c3c','#ec7063','#f1948a','#f5b7b1','#fadbd8','#fdedec','#fff5f5'],
  viridis: ['#440154','#482878','#3e4989','#31688e','#26828e','#1f9e89','#35b779','#6ece58','#b5de2b','#fde725'],
  greyscale: ['#000000','#111111','#333333','#555555','#777777','#999999','#bbbbbb','#dddddd','#eeeeee','#ffffff'],
};

function _yield() {
  return new Promise(r => setTimeout(r, 0));
}

function _computeBounds(points) {
  if (!points || points.length === 0) return null;
  let xMin=Infinity,xMax=-Infinity,yMin=Infinity,yMax=-Infinity,zMin=Infinity,zMax=-Infinity;
  for (const p of points) {
    if (p[0]<xMin) xMin=p[0]; if (p[0]>xMax) xMax=p[0];
    if (p[1]<yMin) yMin=p[1]; if (p[1]>yMax) yMax=p[1];
    if (p[2]<zMin) zMin=p[2]; if (p[2]>zMax) zMax=p[2];
  }
  return { xMin, xMax, yMin, yMax, zMin, zMax };
}

function _parseTXTLine(line) {
  const parts = line.trim().split(/[\s,;]+/).filter(Boolean);
  if (parts.length < 3) return null;
  const x = parseFloat(parts[0]), y = parseFloat(parts[1]), z = parseFloat(parts[2]);
  return isFinite(x) && isFinite(y) && isFinite(z) ? [x, y, z] : null;
}

// ============================================================

export class PointCloudRenderer {

  /**
   * @param {HTMLElement} container  DOM 容器
   * @param {object}      [options]
   * @param {string}      [options.theme='dark']       ECharts 主题
   * @param {string}      [options.renderer='canvas']  'canvas' | 'svg'
   * @param {string}      [options.backgroundColor]    背景色，默认使用主题色
   */
  constructor(container, options = {}) {
    if (typeof echarts === 'undefined') {
      throw new Error('[PointCloudRenderer] 需要 ECharts 库，请先加载 echarts 和 echarts-gl');
    }
    if (!container || typeof container.appendChild === 'undefined') {
      throw new Error('[PointCloudRenderer] 需要有效的 DOM 容器');
    }

    this._container = container;
    this._opts = {
      theme: options.theme || 'dark',
      renderer: options.renderer || 'canvas',
      backgroundColor: options.backgroundColor,
    };

    // Internal state
    this._chart = null;
    this._ro = null;
    this._points = [];
    this._mode = '2d';
    this._pointSize = 3;
    this._colorScheme = 'spectral';
    this._sampling = 'lttb';
    this._autoRotate = false;
    this._abort = false;
    this._loaded = false;
    this._bounds = null;

    // Event callbacks
    this._listeners = {};

    // Initialize chart
    this._initChart();
  }

  // ==========================================================
  // Public API — Loading
  // ==========================================================

  /**
   * 加载点云数据（[[x,y,z], ...]），带进度回调
   * @param {Array<[number,number,number]>} points
   * @returns {Promise<void>}
   */
  async loadPoints(points) {
    if (!Array.isArray(points) || points.length === 0) {
      throw new Error('点云数据不能为空');
    }
    this._abort = false;
    this._points = points;
    this._bounds = _computeBounds(points);

    const total = points.length;
    this._emit('loadstart', { total, bounds: this._bounds });

    if (this._mode === '2d') {
      await this._load2D(points, total);
    } else {
      await this._load3D(points, total);
    }

    if (this._abort) return;
    this._loaded = true;
    this._emit('load', { total, bounds: this._bounds });
  }

  /**
   * 解析文本内容并加载
   * @param {string} text    文件文本
   * @param {string} format   'txt' | 'json'
   * @returns {Promise<number>} 解析出的点数
   */
  async loadFromText(text, format) {
    const points = format === 'json'
      ? this._parseJSON(text)
      : this._parseTXT(text);
    if (points.length === 0) throw new Error('未解析到有效数据');
    await this.loadPoints(points);
    return points.length;
  }

  /**
   * 从 File 对象读取并加载
   * @param {File} file  .txt 或 .json 文件
   * @returns {Promise<number>}
   */
  async loadFromFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (ext !== 'txt' && ext !== 'json') {
      throw new Error('仅支持 .txt 和 .json 文件');
    }
    const text = await this._readFile(file);
    return this.loadFromText(text, ext);
  }

  // ==========================================================
  // Public API — Configuration
  // ==========================================================

  /**
   * 切换渲染模式
   * @param {'2d'|'3d'} mode
   * @returns {Promise<void>}
   */
  async setMode(mode) {
    if (mode !== '2d' && mode !== '3d') throw new Error('mode 必须是 "2d" 或 "3d"');
    if (mode === this._mode) return;
    this._mode = mode;

    this._emit('modechange', { mode });
    this._recreateChart();

    if (this._points.length > 0) {
      if (this._mode === '3d' && this._points.length > 100000) {
        this._emit('warn', { message: `3D 模式渲染 ${this._points.length.toLocaleString()} 个点可能较慢` });
      }
      await this.loadPoints(this._points);
    }
  }

  /** @param {number} size  1–10 */
  setPointSize(size) {
    this._pointSize = Math.max(1, Math.min(10, parseFloat(size) || 3));
    if (!this._chart || !this._loaded) return;
    this._chart.setOption({ series: [{ symbolSize: this._pointSize }] });
  }

  /** @param {string} key  'spectral'|'cool'|'warm'|'viridis'|'greyscale' */
  setColorScheme(key) {
    if (!COLORS[key]) return;
    this._colorScheme = key;
    if (!this._chart || !this._loaded) return;
    this._chart.setOption({ visualMap: { inRange: { color: COLORS[key] } } });
  }

  /** @param {boolean} on  3D 自动旋转 */
  setAutoRotate(on) {
    this._autoRotate = !!on;
    if (!this._chart || !this._loaded || this._mode !== '3d') return;
    this._chart.setOption({ grid3D: { viewControl: { autoRotate: this._autoRotate } } });
  }

  /** @param {'none'|'lttb'|'average'} type  2D 采样方式 */
  setSampling(type) {
    if (!['none', 'lttb', 'average'].includes(type)) return;
    this._sampling = type;
    if (!this._chart || !this._loaded || this._mode !== '2d') return;
    this._chart.setOption({ series: [{ sampling: type === 'none' ? undefined : type }] });
  }

  // ==========================================================
  // Public API — Export
  // ==========================================================

  /**
   * 导出为图片 Data URL
   * @param {object} [opts]
   * @param {string} [opts.type='png']     'png' | 'jpeg'
   * @param {number} [opts.pixelRatio=2]
   * @param {string} [opts.backgroundColor]
   * @returns {string}
   */
  getDataURL(opts = {}) {
    if (!this._chart) throw new Error('图表未初始化');
    return this._chart.getDataURL({
      type: opts.type || 'png',
      pixelRatio: opts.pixelRatio || 2,
      backgroundColor: opts.backgroundColor || this._opts.backgroundColor || undefined,
    });
  }

  // ==========================================================
  // Public API — Events
  // ==========================================================

  /**
   * 监听事件
   * @param {'progress'|'load'|'loadstart'|'error'|'modechange'|'warn'} event
   * @param {Function} fn
   */
  on(event, fn) {
    if (!this._listeners[event]) this._listeners[event] = [];
    this._listeners[event].push(fn);
  }

  /** @param {string} event @param {Function} fn */
  off(event, fn) {
    const list = this._listeners[event];
    if (!list) return;
    this._listeners[event] = list.filter(f => f !== fn);
  }

  // ==========================================================
  // Public API — Getters & Lifecycle
  // ==========================================================

  /** @returns {number} */
  getPointCount() { return this._points.length; }

  /** @returns {{xMin,xMax,yMin,yMax,zMin,zMax}|null} */
  getBounds() { return this._bounds; }

  /** @returns {'2d'|'3d'} */
  getCurrentMode() { return this._mode; }

  /** 销毁实例，释放资源 */
  destroy() {
    this._abort = true;
    this._listeners = {};
    this._points = [];
    this._bounds = null;
    this._loaded = false;
    if (this._ro) { this._ro.disconnect(); this._ro = null; }
    if (this._chart) { this._chart.dispose(); this._chart = null; }
  }

  // ==========================================================
  // Internal — Chart lifecycle
  // ==========================================================

  _initChart() {
    this._chart = echarts.init(this._container, this._opts.theme, {
      renderer: this._opts.renderer,
    });
    this._ro = new ResizeObserver(() => {
      if (this._chart) this._chart.resize();
    });
    this._ro.observe(this._container);
  }

  _recreateChart() {
    if (this._ro) this._ro.disconnect();
    if (this._chart) this._chart.dispose();
    this._chart = null;
    this._initChart();
  }

  // ==========================================================
  // Internal — 2D loading
  // ==========================================================

  async _load2D(points, total) {
    const chunkSize = Math.min(CHUNK_SIZE, Math.max(5000, Math.ceil(total / 50)));
    const { zMin, zMax } = this._bounds;
    const zRange = zMax - zMin || 1;

    // Normalize z to 0–100
    const normalized = new Float32Array(total * 3);
    for (let i = 0; i < total; i++) {
      const p = points[i];
      normalized[i * 3] = p[0];
      normalized[i * 3 + 1] = p[1];
      normalized[i * 3 + 2] = ((p[2] - zMin) / zRange) * 100;
    }

    const colors = COLORS[this._colorScheme];
    const bg = this._opts.backgroundColor || undefined;

    this._chart.setOption({
      backgroundColor: bg,
      tooltip: {
        trigger: 'item',
        formatter: (p) => `X: ${p.data[0]}<br/>Y: ${p.data[1]}<br/>Z: ${p.value[2] !== undefined ? (zMin + (p.value[2] / 100) * zRange).toFixed(4) : '—'}`,
      },
      grid: { left: 60, right: 40, top: 40, bottom: 50 },
      xAxis: { type: 'value', name: 'X', splitLine: { lineStyle: { color: '#333' } } },
      yAxis: { type: 'value', name: 'Y', splitLine: { lineStyle: { color: '#333' } } },
      visualMap: {
        min: 0, max: 100, dimension: 2,
        inRange: { color: colors },
        textStyle: { color: '#8888aa' },
        calculable: false, left: 10, bottom: 40, itemWidth: 12, itemHeight: 100,
      },
      series: [{
        type: 'scatter', data: [],
        large: true, largeThreshold: 2000,
        symbolSize: this._pointSize,
        sampling: this._sampling === 'none' ? undefined : this._sampling,
        itemStyle: { opacity: 0.8 },
      }],
    }, true);

    // Append in chunks
    let lastPct = 0;
    for (let i = 0; i < total; i += chunkSize) {
      if (this._abort) return;
      const end = Math.min(i + chunkSize, total);
      const chunk = [];
      for (let j = i; j < end; j++) {
        chunk.push([normalized[j * 3], normalized[j * 3 + 1], normalized[j * 3 + 2]]);
      }
      this._chart.appendData({ seriesIndex: 0, data: chunk });

      const pct = Math.round((end / total) * 100);
      if (pct > lastPct) {
        lastPct = pct;
        this._emit('progress', { percent: pct, text: `加载中 ${pct}% (${end.toLocaleString()}/${total.toLocaleString()})`, loaded: end, total });
        await _yield();
      }
    }
  }

  // ==========================================================
  // Internal — 3D loading
  // ==========================================================

  async _load3D(points, total) {
    const { xMin, xMax, yMin, yMax, zMin, zMax } = this._bounds;
    const zRange = zMax - zMin || 1;
    const range = Math.max(xMax - xMin, yMax - yMin, zMax - zMin) / 2;
    const cx = (xMin + xMax) / 2;
    const cy = (yMin + yMax) / 2;
    const cz = (zMin + zMax) / 2;

    const colors = COLORS[this._colorScheme];
    const bg = this._opts.backgroundColor || undefined;

    // Build data array in chunks (with progress)
    this._emit('progress', { percent: 0, text: '准备 3D 数据...', loaded: 0, total });

    const data3D = [];
    const chunkSize = Math.min(CHUNK_SIZE, Math.max(5000, Math.ceil(total / 50)));
    let lastPct = 0;

    for (let i = 0; i < total; i += chunkSize) {
      if (this._abort) return;
      const end = Math.min(i + chunkSize, total);
      for (let j = i; j < end; j++) {
        const p = points[j];
        data3D.push([p[0], p[1], p[2], (p[2] - zMin) / zRange]);
      }
      const pct = Math.round((end / total) * 70);
      if (pct > lastPct) {
        lastPct = pct;
        this._emit('progress', { percent: pct, text: `准备 3D 数据 ${pct}% (${end.toLocaleString()}/${total.toLocaleString()})`, loaded: end, total });
        await _yield();
      }
    }

    this._emit('progress', { percent: 75, text: '渲染 3D 场景...', loaded: total, total });
    await _yield();

    this._chart.setOption({
      backgroundColor: bg,
      tooltip: {},
      grid3D: {
        show: true, boxWidth: 100, boxHeight: 100, boxDepth: 100,
        viewControl: {
          distance: range * 3, center: [cx, cy, cz],
          autoRotate: this._autoRotate, autoRotateSpeed: 5,
          alpha: 25, beta: 40,
        },
        xAxis3D: { type: 'value', name: 'X', splitLine: { lineStyle: { color: '#333' } } },
        yAxis3D: { type: 'value', name: 'Y', splitLine: { lineStyle: { color: '#333' } } },
        zAxis3D: { type: 'value', name: 'Z', splitLine: { lineStyle: { color: '#333' } } },
        axisPointer: { show: false },
        environment: bg || '#1a1b2e',
      },
      visualMap: {
        min: 0, max: 1, dimension: 3,
        inRange: { color: colors },
        textStyle: { color: '#8888aa' },
        calculable: false, left: 10, bottom: 40, itemWidth: 12, itemHeight: 100,
      },
      series: [{
        type: 'scatter3D', data: [],
        symbolSize: this._pointSize,
        itemStyle: { opacity: 0.8 },
        silent: false,
      }],
    }, true);

    this._emit('progress', { percent: 85, text: '构建 3D 场景...', loaded: total, total });
    await _yield();

    this._chart.setOption({ series: [{ data: data3D }] });
    this._emit('progress', { percent: 100, text: '3D 渲染完成', loaded: total, total });
  }

  // ==========================================================
  // Internal — Parsing
  // ==========================================================

  async _parseTXT(text) {
    const lines = text.split(/\r?\n/);
    const total = lines.length;
    const points = [];
    let invalid = 0;
    let lastPct = 0;

    this._emit('progress', { percent: 0, text: `解析 ${total.toLocaleString()} 行...`, loaded: 0, total });

    for (let i = 0; i < total; i += CHUNK_SIZE) {
      if (this._abort) return [];
      const end = Math.min(i + CHUNK_SIZE, total);
      for (let j = i; j < end; j++) {
        const parsed = _parseTXTLine(lines[j]);
        if (parsed) points.push(parsed);
        else invalid++;
      }
      const pct = Math.round((end / total) * 100);
      if (pct > lastPct) {
        lastPct = pct;
        this._emit('progress', { percent: pct, text: `解析中 ${pct}% (${points.length.toLocaleString()} 个点)`, loaded: end, total });
        await _yield();
      }
    }
    return points;
  }

  _parseJSON(text) {
    let data;
    try { data = JSON.parse(text); }
    catch (e) { throw new Error('JSON 格式错误: ' + e.message); }
    if (!Array.isArray(data)) throw new Error('JSON 必须是数组');

    const points = [];
    for (let i = 0; i < data.length; i++) {
      const item = data[i];
      let x, y, z;
      if (Array.isArray(item) && item.length >= 3) {
        x = parseFloat(item[0]); y = parseFloat(item[1]); z = parseFloat(item[2]);
      } else if (item && typeof item === 'object') {
        x = parseFloat(item.x ?? item.X ?? item.lon ?? item.Lon ?? item.longitude ?? item[0]);
        y = parseFloat(item.y ?? item.Y ?? item.lat ?? item.Lat ?? item.latitude ?? item[1]);
        z = parseFloat(item.z ?? item.Z ?? item.alt ?? item.Alt ?? item.altitude ?? item.value ?? item[2]);
      } else continue;
      if (isFinite(x) && isFinite(y) && isFinite(z)) points.push([x, y, z]);
    }
    return points;
  }

  _readFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error('文件读取失败'));
      reader.readAsText(file);
    });
  }

  // ==========================================================
  // Internal — Events
  // ==========================================================

  _emit(event, data) {
    const fns = this._listeners[event];
    if (!fns) return;
    for (const fn of fns) {
      try { fn(data); } catch (e) { console.error('[PointCloudRenderer] event error:', e); }
    }
  }
}
