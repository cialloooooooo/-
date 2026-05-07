/**
 * ============================================================
 *  PointRenderer — 点云渲染引擎  v1.1
 * ============================================================
 *  支持 3D 散点图（50万+点）和 2D 多边形两种模式。
 *  零 DOM 耦合，不依赖任何框架。
 *
 *  依赖：echarts >= 5.5.0、echarts-gl >= 2.0.9
 *
 * ─── 使用方式 ──────────────────────────────────────────────
 *
 *  安装依赖（缺一不可）：
 *    pnpm add echarts echarts-gl
 *
 *  Vue / React 项目（推荐，自包含）：
 *    import PointRenderer from './point-renderer.js';
 *    const pr = new PointRenderer(document.getElementById('chart'));
 *    pr.parseAndRender(fileText, (pct) => console.log(pct + '%'));
 *
 *  浏览器 <script> 方式：
 *    <script src="echarts.min.js"></script>
 *    <script src="echarts-gl.min.js"></script>
 *    <script src="point-renderer.js"></script>
 *    <script>
 *      var pr = new PointRenderer(document.getElementById('chart'));
 *      pr.parseAndRender(fileText, function(pct) { console.log(pct + '%'); });
 *    </script>
 *
 * ─── API 速览 ──────────────────────────────────────────────
 *
 *  new PointRenderer(container, options?)  构造器
 *  .parse(text, onProgress?)              解析文本，返回 {mode, data}
 *  .render()                              渲染已解析的数据
 *  .parseAndRender(text, onProgress?)     一键解析+渲染
 *  .setData(mode, data)                   直接设置结构化数据（跳过解析）
 *  .onClick(fn)                           注册选中回调 fn({x,y,z})
 *  .dispose()                             销毁实例
 *  .getChart()                            获取 echarts 实例
 *  .getStats()                            获取数据统计
 *  .resize()                              触发放缩
 *
 * ─── options 可配置项 ──────────────────────────────────────
 *
 *  {
 *    backgroundColor: '#1a1a2e',
 *    scatter3D: { symbolSize: 3, large: true, largeThreshold: 2000 },
 *    colorRange: ['#313695', ... , '#a50026'],   // z轴浅→深颜色
 *    polygon: { lineWidth: 1.5, symbolSize: 4 },
 *  }
 *
 * ============================================================
 */
import * as echarts from 'echarts';
import 'echarts-gl';

(function(root, factory) {
  // UMD 包装：兼容 <script> / CommonJS / AMD / ES Module
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.PointRenderer = factory();
  }
}(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  // ─── 默认配置 ──────────────────────────────────────────
  var DEFAULTS = {
    scatter3D: {
      symbolSize: 3,
      large: true,
      largeThreshold: 2000,
    },
    // z 轴颜色映射 (浅→深)
    colorRange: ['#313695','#4575b4','#74add1','#abd9e9','#e0f3f8',
                 '#ffffbf','#fee090','#fdae61','#f46d43','#d73027','#a50026'],
    polygon: {
      lineWidth: 1.5,
      symbolSize: 4,
    },
    backgroundColor: '#1a1a2e',
  };

  // ─── 工具函数 ──────────────────────────────────────────
  function extend(target, source) {
    var result = {};
    for (var k in target) { result[k] = target[k]; }
    for (var k in source) { result[k] = source[k]; }
    return result;
  }

  // ─── 文件解析 ──────────────────────────────────────────
  /**
   * @param {string} text
   * @param {function(number):void} [onProgress]
   * @returns {{ mode: '3d'|'2d', data: Array }}
   */
  function parseFile(text, onProgress) {
    var lines = text.split(/\r?\n/).filter(function(l) { return l.trim(); });
    if (lines.length < 2) throw new Error('文件格式错误：至少需要2行（第一行模式声明 + 至少1行数据）');

    var modeLine = lines[0].trim().toUpperCase();
    if (modeLine !== '3D' && modeLine !== '2D') {
      throw new Error('第一行必须是 "3D" 或 "2D"，当前为: ' + modeLine);
    }
    var mode = modeLine === '3D' ? '3d' : '2d';

    var dataLines = lines.slice(1);
    var total = dataLines.length;
    var result = [];
    var batchSize = 5000;

    for (var i = 0; i < total; i++) {
      var raw = dataLines[i].trim();
      if (!raw) continue;

      if (mode === '3d') {
        var parts = raw.split(/\s+/);
        if (parts.length < 3) continue;
        var x = parseFloat(parts[0]);
        var y = parseFloat(parts[1]);
        var z = parseFloat(parts[2]);
        if (isNaN(x) || isNaN(y) || isNaN(z)) continue;
        result.push([x, y, z]);
      } else {
        var parts2 = raw.split(',');
        if (parts2.length < 3) continue;
        var vertices = [];
        for (var j = 0; j + 2 < parts2.length; j += 3) {
          var vx = parseFloat(parts2[j]);
          var vy = parseFloat(parts2[j + 1]);
          var vz = parseFloat(parts2[j + 2]);
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

    return { mode: mode, data: result };
  }

  // ─── 构建 ECharts Option ────────────────────────────────
  /** @param {Array<[number,number,number]>} data */
  function build3DOption(data, config) {
    var cfg = extend(DEFAULTS, config);

    // 计算 z 范围
    var zMin = Infinity, zMax = -Infinity;
    for (var i = 0; i < data.length; i++) {
      var z = data[i][2];
      if (z < zMin) zMin = z;
      if (z > zMax) zMax = z;
    }
    if (zMin === zMax) { zMin -= 1; zMax += 1; }

    return {
      backgroundColor: cfg.backgroundColor,
      tooltip: {
        formatter: function(p) {
          if (!p) return '';
          var v = p.value || p.data;
          return 'X: <b>' + v[0].toFixed(4) + '</b><br/>' +
                 'Y: <b>' + v[1].toFixed(4) + '</b><br/>' +
                 'Z: <b>' + v[2].toFixed(4) + '</b>';
        },
        backgroundColor: 'rgba(22,33,62,.92)',
        borderColor: '#2a2a4a',
        textStyle: { color: '#e0e0e0', fontSize: 13 },
      },
      grid3D: {
        viewControl: {
          projection: 'perspective',
          autoRotate: false,
          distance: 180,
          alpha: 25,
          beta: 45,
        },
        boxWidth: 100,
        boxHeight: 100,
        boxDepth: 100,
        axisLine: { lineStyle: { color: '#444' } },
        axisPointer: { lineStyle: { color: '#e94560' } },
        splitLine: { lineStyle: { color: '#2a2a4a' } },
        axisLabel: { color: '#888', fontSize: 10 },
      },
      xAxis3D: { name: 'X', type: 'value' },
      yAxis3D: { name: 'Y', type: 'value' },
      zAxis3D: { name: 'Z', type: 'value' },
      visualMap: {
        show: true,
        dimension: 2,
        min: zMin,
        max: zMax,
        inRange: { color: cfg.colorRange },
        text: ['Z深', 'Z浅'],
        textStyle: { color: '#aaa' },
        orient: 'vertical',
        left: 10,
        top: 'center',
      },
      series: [{
        type: 'scatter3D',
        data: data,
        symbolSize: cfg.scatter3D.symbolSize,
        large: cfg.scatter3D.large,
        largeThreshold: cfg.scatter3D.largeThreshold,
        itemStyle: { borderWidth: 0 },
        emphasis: {
          itemStyle: { borderColor: '#fff', borderWidth: 2 },
          label: {
            show: true,
            formatter: function(p) {
              var v = p.data || p.value;
              return '(' + v[0].toFixed(2) + ', ' + v[1].toFixed(2) + ', ' + v[2].toFixed(2) + ')';
            },
            color: '#fff',
            fontSize: 12,
            distance: 10,
          },
        },
      }],
    };
  }

  /** @param {Array<Array<[number,number,number]>>} data */
  function build2DOption(data, config) {
    var cfg = extend(DEFAULTS, config);
    var series = [];
    var colors = ['#e94560','#0f3460','#74add1','#fdae61','#4575b4',
                  '#d73027','#abd9e9','#fee090','#313695','#f46d43'];

    data.forEach(function(vertices, idx) {
      var color = colors[idx % colors.length];

      // 闭合多边形线段
      var lineData = vertices.map(function(v) { return [v[0], v[1]]; });
      if (lineData.length > 0) {
        lineData.push([vertices[0][0], vertices[0][1]]);
      }

      series.push({
        type: 'line',
        name: '多边形 ' + (idx + 1),
        data: lineData,
        lineStyle: { color: color, width: cfg.polygon.lineWidth },
        symbol: 'none',
        silent: true,
        z: 1,
      });

      series.push({
        type: 'scatter',
        name: '顶点组 ' + (idx + 1),
        data: vertices.map(function(v) { return [v[0], v[1]]; }),
        symbolSize: cfg.polygon.symbolSize,
        itemStyle: { color: color, borderColor: '#fff', borderWidth: 1 },
        z: 2,
      });
    });

    return {
      backgroundColor: cfg.backgroundColor,
      tooltip: {
        trigger: 'item',
        formatter: function(p) {
          if (!p || !p.value) return '';
          var px = p.value[0], py = p.value[1];
          var zInfo = '';
          for (var i = 0; i < data.length && !zInfo; i++) {
            for (var j = 0; j < data[i].length; j++) {
              if (Math.abs(data[i][j][0] - px) < 1e-6 && Math.abs(data[i][j][1] - py) < 1e-6) {
                zInfo = '<br/>Z: <b>' + data[i][j][2].toFixed(4) + '</b>';
                break;
              }
            }
          }
          return 'X: <b>' + px.toFixed(4) + '</b><br/>' +
                 'Y: <b>' + py.toFixed(4) + '</b>' + zInfo;
        },
        backgroundColor: 'rgba(22,33,62,.92)',
        borderColor: '#2a2a4a',
        textStyle: { color: '#e0e0e0', fontSize: 13 },
      },
      grid: { left: 48, right: 24, top: 24, bottom: 48 },
      xAxis: {
        type: 'value', name: 'X',
        axisLine: { lineStyle: { color: '#444' } },
        axisLabel: { color: '#888' },
        splitLine: { lineStyle: { color: '#2a2a4a' } },
      },
      yAxis: {
        type: 'value', name: 'Y',
        axisLine: { lineStyle: { color: '#444' } },
        axisLabel: { color: '#888' },
        splitLine: { lineStyle: { color: '#2a2a4a' } },
      },
      dataZoom: [
        { type: 'inside', xAxisIndex: 0 },
        { type: 'inside', yAxisIndex: 0 },
        { type: 'slider', xAxisIndex: 0, bottom: 8, height: 20,
          borderColor: '#444', backgroundColor: '#1a1a2e',
          dataBackground: { lineStyle: { color: '#555' }, areaStyle: { color: '#333' } },
          textStyle: { color: '#888' } },
        { type: 'slider', yAxisIndex: 0, right: 8, width: 20,
          borderColor: '#444', backgroundColor: '#1a1a2e',
          dataBackground: { lineStyle: { color: '#555' }, areaStyle: { color: '#333' } },
          textStyle: { color: '#888' } },
      ],
      series: series,
    };
  }

  // ─── PointRenderer 构造函数 ─────────────────────────────
  /**
   * @param {HTMLElement|string} container - 渲染容器
   * @param {object} [options] - 可选配置（会合并到默认配置上）
   */
  function PointRenderer(container, options) {
    if (typeof container === 'string') {
      container = document.querySelector(container);
    }
    if (!container || container.nodeType !== 1) {
      throw new Error('PointRenderer: 容器元素无效');
    }
    this.container = container;
    this.options = extend(DEFAULTS, options || {});
    this.chartInstance = null;
    this.mode = null;
    this.data = null;
    this._clickHandler = null;
  }

  PointRenderer.prototype = /** @lends PointRenderer# */ {

    // ── 数据加载 ────────────────────────────────────────

    /**
     * 从文本解析数据（不渲染）
     * @param {string} text - 文件文本
     * @param {function(number):void} [onProgress] 进度回调 0-100
     * @returns {{ mode:'3d'|'2d', data:Array }}
     */
    parse: function(text, onProgress) {
      var result = parseFile(text, onProgress);
      this.mode = result.mode;
      this.data = result.data;
      return result;
    },

    /**
     * 直接设置结构化数据（跳过文件解析）
     * @param {'3d'|'2d'} mode
     * @param {Array} data - 3D: Array<[x,y,z]>, 2D: Array<Array<[x,y,z]>>
     */
    setData: function(mode, data) {
      this.mode = mode;
      this.data = data;
    },

    // ── 渲染 ────────────────────────────────────────────

    /** 渲染已加载的数据 */
    render: function() {
      var self = this;
      if (!this.data) throw new Error('PointRenderer: 请先调用 parse() 或 setData() 设置数据');

      // 仅销毁旧图表实例，不清除 data/mode
      if (this.chartInstance) {
        this.chartInstance.off('click');
        this.chartInstance.dispose();
        this.chartInstance = null;
      }

      // 缓存本次渲染所需的 data 和 mode，防止异步场景下被外部篡改
      var mode = this.mode;
      var data = this.data;

      var option;
      if (mode === '3d') {
        option = build3DOption(data, this.options);
      } else {
        option = build2DOption(data, this.options);
      }

      this.chartInstance = echarts.init(this.container);
      this.chartInstance.setOption(option, true);
      this._bindClick();

      return this.chartInstance;
    },

    /**
     * 一键解析并渲染
     * @param {string} text
     * @param {function(number):void} [onProgress]
     */
    parseAndRender: function(text, onProgress) {
      this.parse(text, onProgress);
      this.render();
      return { mode: this.mode, data: this.data };
    },

    // ── 交互 ────────────────────────────────────────────

    /**
     * 注册点击选中回调
     * @param {function({x:number, y:number, z:number|null}):void} fn
     */
    onClick: function(fn) {
      this._clickHandler = fn;
      this._bindClick();
    },

    _bindClick: function() {
      var self = this;
      if (!this.chartInstance) return;
      this.chartInstance.off('click');

      this.chartInstance.on('click', function(params) {
        var coord = null;
        if (self.mode === '3d') {
          var v = params.data || params.value;
          if (v && v.length >= 3) {
            coord = { x: v[0], y: v[1], z: v[2] };
          }
        } else {
          if (params.value && params.value.length >= 2) {
            coord = { x: params.value[0], y: params.value[1], z: null };
          }
        }
        if (coord && self._clickHandler) {
          self._clickHandler(coord);
        }
      });
    },

    // ── 生命周期 ────────────────────────────────────────

    /** 销毁图表实例，释放资源 */
    dispose: function() {
      if (this.chartInstance) {
        this.chartInstance.off('click');
        this.chartInstance.dispose();
        this.chartInstance = null;
      }
      this.data = null;
      this.mode = null;
    },

    /** 强制重绘（窗口大小变化时调用） */
    resize: function() {
      if (this.chartInstance) this.chartInstance.resize();
    },

    // ── 查询 ────────────────────────────────────────────

    /** @returns {object|null} echarts 实例 */
    getChart: function() { return this.chartInstance; },

    /** @returns {'3d'|'2d'|null} */
    getMode: function() { return this.mode; },

    /**
     * 获取数据统计
     * @returns {{ mode:string, pointCount?:number, polygonCount?:number, vertexCount?:number }|null}
     */
    getStats: function() {
      if (!this.data) return null;
      if (this.mode === '3d') {
        return { mode: '3D 散点', pointCount: this.data.length };
      } else {
        var totalVertices = 0;
        this.data.forEach(function(p) { totalVertices += p.length; });
        return { mode: '2D 多边形', polygonCount: this.data.length, vertexCount: totalVertices };
      }
    },
  };

  // ─── 静态工具 ──────────────────────────────────────────
  /** 解析文件（静态方法，不创建实例） */
  PointRenderer.parseFile = parseFile;

  /** 构建 3D option（静态方法） */
  PointRenderer.build3DOption = build3DOption;

  /** 构建 2D option（静态方法） */
  PointRenderer.build2DOption = build2DOption;

  /** 版本号 */
  PointRenderer.VERSION = '1.0.0';

  return PointRenderer;
}));

// ESM 默认导出（供 Vite/Webpack/Rollup 等打包器使用）
export default PointRenderer;
