/**
 * PointCloudRenderer - 点云渲染库入口
 *
 * 导出所有核心模块，方便按需引入
 *
 * 使用示例：
 *   // 方式一：使用统一管理器（推荐）
 *   import PointCloudManager from 'point-cloud-renderer';
 *   const manager = new PointCloudManager('container');
 *   await manager.loadFromFile(file);
 *
 *   // 方式二：直接使用渲染器
 *   import { PointCloud3DRenderer, TxtPointParser } from 'point-cloud-renderer';
 *   const parser = new TxtPointParser();
 *   const { mode, points } = parser.parse(content);
 *   const renderer = new PointCloud3DRenderer('container');
 *   renderer.init();
 *   renderer.setData(points);
 *   renderer.render();
 */

// 核心基类
export { default as PointCloudRenderer } from './core/PointCloudRenderer.js';

// 渲染器
export { default as PointCloud3DRenderer } from './renderers/PointCloud3DRenderer.js';
export { default as PointCloud2DRenderer } from './renderers/PointCloud2DRenderer.js';

// 解析器
export { default as TxtPointParser } from './parsers/TxtPointParser.js';

// 统一管理器（默认导出）
export { default } from './PointCloudManager.js';
