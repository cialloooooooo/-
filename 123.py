import random

# 配置
point_num = 500000
min_val = 0.0
max_val = 100.0  # 坐标范围 0~100，可自行修改

with open("points_50w.txt", "w", encoding="utf-8") as f:
    for _ in range(point_num):
        x = random.uniform(min_val, max_val)
        y = random.uniform(min_val, max_val)
        z = random.uniform(min_val, max_val)
        f.write(f"{x:.3f} {y:.3f} {z:.3f}\n")

print("生成完成，共", point_num, "个点")
'''
Write(echart-renderer\examples\vue-example.md)               
  ⎿  Wrote 246 lines to echart-renderer\examples\vue-example.md
     ## Vue 3 + PointCloudRenderer 集成             
                                                        
     将 `PointCloudRenderer.js` 复制到你的 `src/utils/` 目录下，然后在 Vue 组件中使用。
                                                                                                                                                                                                                                                                      
     ### 基础组件 (Vue 3 Composition API)
                                                                                                                                                                                                                                                                      
     ```vue                                                                        
     <template>                                                                                                                                                                                                                                                       
       <div class="point-cloud-viewer">                                            
         <!-- 工具栏 -->
     … +236 lines (ctrl+o to expand)

● Let me verify the final project structure.             
                                                  
  Read 2 files (ctrl+o to expand)                   
                                                                                                                  
● 项目重构完成。以下是完整的文件结构和调用指南。    
                                                                                                                                                                                                                                                                      
  ---                                                                                     
  项目结构                                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                      
  echart-renderer/                                                                                                                                                                                                                                                    
  ├── PointCloudRenderer.js       # 核心可复用类 (ES Module)                                                                                                                                                                                                          
  ├── index.html                  # 独立演示工具 (已重构使用该类)
  └── examples/                                                                                                                                                                                                                                                       
      ├── vanilla-example.html    # 极简独立 demo                                                                                                                                                                                                                     
      ├── react-example.md        # React 集成指南 + 完整组件代码
      └── vue-example.md          # Vue 3 集成指南 + 完整组件代码

  ---
  如何在前端项目中调用

  方式一：复制 PointCloudRenderer.js 到你项目中

  最简单的用法：

  import { PointCloudRenderer } from './path/to/PointCloudRenderer.js';

  // 1. 创建实例，传入 DOM 容器
  const renderer = new PointCloudRenderer(document.getElementById('chart'));

  // 2. 监听进度（可选）
  renderer.on('progress', ({ percent, text }) => {
    updateMyProgressBar(percent, text);
  });

  // 3. 加载数据 — 支持三种方式
  await renderer.loadPoints([[x1,y1,z1], [x2,y2,z2], ...]);     // 直接传数组
  await renderer.loadFromFile(fileObject);                        // 传 File 对象
  await renderer.loadFromText(textContent, 'txt');                // 传文本

  // 4. 控制
  renderer.setMode('3d');         // 切换 2D/3D
  renderer.setPointSize(5);       // 点大小
  renderer.setColorScheme('warm');// 配色
  renderer.setAutoRotate(true);   // 3D 自动旋转

  // 5. 导出
  const dataURL = renderer.getDataURL({ pixelRatio: 2 });

  // 6. 销毁
  renderer.destroy();

  方式二：作为独立工具使用

  直接用浏览器打开 index.html，支持拖拽文件、测试数据、导出图片。

  ---
  完整 API

  ┌────────────────────────────┬───────────────────────────────────────────────────────────────┐
  │            方法            │                             说明                              │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ constructor(dom, opts?)    │ 创建渲染器，opts.theme / opts.renderer / opts.backgroundColor │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ loadPoints(points)         │ 加载 [[x,y,z],...] 数组                                       │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ loadFromFile(file)         │ 读取并解析 .txt/.json 文件                                    │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ loadFromText(text, format) │ 解析文本内容                                                  │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ `setMode('2d'              │ '3d')`                                                        │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ setPointSize(n)            │ 点大小 1–10                                                   │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ setColorScheme(key)        │ 配色: spectral / cool / warm / viridis / greyscale            │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ setAutoRotate(bool)        │ 3D 自动旋转                                                   │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ setSampling(type)          │ 2D 采样: none / lttb / average                                │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ getDataURL(opts)           │ 导出 PNG Data URL                                             │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ on(event, fn)              │ 监听: progress / load / loadstart / error / modechange / warn │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ off(event, fn)             │ 取消监听                                                      │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ getPointCount()            │ 当前点数                                                      │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ getBounds()                │ 坐标范围 {xMin,xMax,yMin,yMax,zMin,zMax}                      │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ getCurrentMode()           │ 当前模式                                                      │
  ├────────────────────────────┼───────────────────────────────────────────────────────────────┤
  │ destroy()                  │ 释放资源                                                      │
  └────────────────────────────┴───────────────────────────────────────────────────────────────┘

  ---
  React / Vue 快速引用

  # 将 PointCloudRenderer.js 复制到项目中
  cp PointCloudRenderer.js your-project/src/utils/

  # 确保安装了 ECharts
  npm install echarts echarts-gl

  详细的 React 组件和 Vue 3 组件代码见 examples/react-example.md / examples/vue-example.md，复制即可用。
'''