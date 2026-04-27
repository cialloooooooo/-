## React + PointCloudRenderer 集成

将 `PointCloudRenderer.js` 复制到你的 `src/` 目录下，然后在 React 组件中使用。

### 基础组件

```jsx
import { useEffect, useRef, useState, useCallback } from 'react';
import { PointCloudRenderer } from './PointCloudRenderer';

export default function PointCloudViewer() {
  const containerRef = useRef(null);
  const rendererRef = useRef(null);
  const [progress, setProgress] = useState({ percent: 0, text: '' });
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // 创建渲染器
    const renderer = new PointCloudRenderer(containerRef.current, {
      theme: 'dark',
      backgroundColor: '#1a1b2e',
    });
    rendererRef.current = renderer;

    // 监听事件
    renderer.on('progress', (p) => {
      setProgress(p);
      setLoading(true);
    });
    renderer.on('load', ({ total, bounds }) => {
      setLoading(false);
      setStats({ total, bounds });
    });
    renderer.on('error', ({ message }) => {
      setLoading(false);
      console.error(message);
    });

    return () => {
      renderer.destroy();
      rendererRef.current = null;
    };
  }, []);

  const handleFileUpload = useCallback(async (e) => {
    const file = e.target.files?.[0];
    if (!file || !rendererRef.current) return;
    try {
      await rendererRef.current.loadFromFile(file);
    } catch (err) {
      console.error(err);
    }
  }, []);

  const loadSampleData = useCallback(async () => {
    if (!rendererRef.current) return;
    const count = 100000;
    const points = [];
    for (let i = 0; i < count; i++) {
      const t = Math.random() * Math.PI * 2;
      const r = Math.random() * 10;
      points.push([
        r * Math.cos(t),
        r * Math.sin(t),
        Math.sin(r * 0.5) * Math.cos(r * 0.3) * 2 + (Math.random() - 0.5) * 0.3,
      ]);
    }
    try {
      await rendererRef.current.loadPoints(points);
    } catch (err) {
      console.error(err);
    }
  }, []);

  const switchMode = useCallback((mode) => {
    if (rendererRef.current) rendererRef.current.setMode(mode);
  }, []);

  const exportImage = useCallback(() => {
    if (!rendererRef.current) return;
    const url = rendererRef.current.getDataURL({ pixelRatio: 2 });
    const a = document.createElement('a');
    a.download = `pointcloud_${Date.now()}.png`;
    a.href = url;
    a.click();
  }, []);

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* 工具栏 */}
      <div style={{ padding: 10, background: '#232540', display: 'flex', gap: 8, alignItems: 'center' }}>
        <input type="file" accept=".txt,.json" onChange={handleFileUpload} />
        <button onClick={loadSampleData}>测试数据</button>

        <select onChange={(e) => switchMode(e.target.value)} defaultValue="2d">
          <option value="2d">2D (Z→颜色)</option>
          <option value="3d">3D</option>
        </select>

        <button onClick={exportImage}>导出图片</button>

        {stats && (
          <span style={{ color: '#8888aa', fontSize: 12, marginLeft: 'auto' }}>
            {stats.total.toLocaleString()} 点
          </span>
        )}
      </div>

      {/* 进度条 */}
      {loading && (
        <div style={{ padding: '4px 16px', background: '#232540', borderTop: '1px solid #3a3d5c' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ color: '#8888aa', fontSize: 12 }}>{progress.text}</span>
            <div style={{
              flex: 1, height: 4, background: '#2a2d4a', borderRadius: 2, overflow: 'hidden',
            }}>
              <div style={{
                height: '100%', width: `${progress.percent}%`,
                background: 'linear-gradient(90deg, #6c5ce7, #00cec9)',
                transition: 'width .15s',
              }} />
            </div>
            <span style={{ color: '#8888aa', fontSize: 12, minWidth: 40, textAlign: 'right' }}>
              {progress.percent}%
            </span>
          </div>
        </div>
      )}

      {/* 图表容器 */}
      <div ref={containerRef} style={{ flex: 1 }} />
    </div>
  );
}
```

### 安装注意事项

1. 将 `PointCloudRenderer.js` 放入你的 `src/` 目录
2. 确保页面已加载 ECharts + ECharts GL（通过 CDN script 标签或 npm 包）：

```bash
npm install echarts echarts-gl
```

然后在组件入口处导入：

```javascript
import 'echarts';
import 'echarts-gl';
// 在 PointCloudRenderer 实例化前导入即可
```

3. 如果使用 TypeScript，可以创建类型声明文件 `PointCloudRenderer.d.ts`：

```typescript
export interface PointCloudRendererOptions {
  theme?: string;
  renderer?: 'canvas' | 'svg';
  backgroundColor?: string;
}

export interface ProgressEvent {
  percent: number;
  text: string;
  loaded: number;
  total: number;
}

export interface LoadEvent {
  total: number;
  bounds: {
    xMin: number; xMax: number;
    yMin: number; yMax: number;
    zMin: number; zMax: number;
  } | null;
}

export class PointCloudRenderer {
  constructor(container: HTMLElement, options?: PointCloudRendererOptions);
  loadPoints(points: number[][]): Promise<void>;
  loadFromText(text: string, format: 'txt' | 'json'): Promise<number>;
  loadFromFile(file: File): Promise<number>;
  setMode(mode: '2d' | '3d'): Promise<void>;
  setPointSize(size: number): void;
  setColorScheme(scheme: string): void;
  setAutoRotate(on: boolean): void;
  setSampling(type: 'none' | 'lttb' | 'average'): void;
  getDataURL(opts?: { type?: string; pixelRatio?: number; backgroundColor?: string }): string;
  on(event: 'progress', fn: (data: ProgressEvent) => void): void;
  on(event: 'load' | 'loadstart', fn: (data: LoadEvent) => void): void;
  on(event: 'error' | 'warn', fn: (data: { message: string }) => void): void;
  on(event: 'modechange', fn: (data: { mode: string }) => void): void;
  off(event: string, fn: Function): void;
  getPointCount(): number;
  getBounds(): object | null;
  getCurrentMode(): string;
  destroy(): void;
}
```
