/**
 * PointCloudManager - 点云渲染统一管理器
 *
 * 这是对外暴露的核心入口，封装了完整的渲染逻辑
 * 调用方只需传入 DOM 容器和 TXT 文件，即可自动完成解析和渲染
 *
 * 使用示例：
 *   // 方式一：直接传入文件内容
 *   const manager = new PointCloudManager('container');
 *   await manager.loadFromContent(txtContent);
 *
 *   // 方式二：传入 File 对象（浏览器文件上传）
 *   const manager = new PointCloudManager('container');
 *   await manager.loadFromFile(file);
 *
 *   // 方式三：传入 URL
 *   const manager = new PointCloudManager('container');
 *   await manager.loadFromUrl('/data/points.txt');
 *
 *   // 方式四：手动设置数据和渲染
 *   const manager = new PointCloudManager('container', { renderMode: '3d' });
 *   manager.init();
 *   manager.setData(pointsArray);
 *   manager.render();
 *
 *   // 销毁
 *   manager.dispose();
 */

import PointCloud3DRenderer from './renderers/PointCloud3DRenderer.js';
import PointCloud2DRenderer from './renderers/PointCloud2DRenderer.js';
import TxtPointParser from './parsers/TxtPointParser.js';

export default class PointCloudManager {
    /**
     * @param {HTMLElement|string} dom - 容器 DOM 元素或其 ID
     * @param {Object} [options] - 配置项
     * @param {string} [options.renderMode='3d'] - 默认渲染模式（当文件第一行未指定时使用）
     * @param {Object} [options.rendererOptions] - 传递给渲染器的额外选项
     * @param {Object} [options.parserOptions] - 传递给解析器的选项
     * @param {Function} [options.onProgress] - 解析进度回调 (progress: 0-1) => void
     * @param {Function} [options.onReady] - 渲染完成回调 (renderer) => void
     * @param {Function} [options.onError] - 错误回调 (error) => void
     */
    constructor(dom, options = {}) {
        this.dom = dom;
        this.options = {
            renderMode: '3d',
            rendererOptions: {},
            parserOptions: {},
            onProgress: null,
            onReady: null,
            onError: null,
            ...options,
        };

        /** @type {PointCloud3DRenderer|PointCloud2DRenderer|null} */
        this.renderer = null;

        /** @type {TxtPointParser|null} */
        this.parser = null;

        /** 当前渲染模式 */
        this.currentMode = null;

        /** 是否已初始化 */
        this._initialized = false;
    }

    /**
     * 初始化渲染器
     * @param {string} mode - 渲染模式 '3d' | '2d'
     * @returns {this}
     */
    init(mode) {
        if (this._initialized) {
            this.dispose();
        }

        this.currentMode = mode || this.options.renderMode;

        // 根据模式创建对应的渲染器
        const rendererOptions = {
            ...this.options.rendererOptions,
            onProgress: this.options.onProgress,
        };

        if (this.currentMode === '3d') {
            this.renderer = new PointCloud3DRenderer(this.dom, rendererOptions);
        } else {
            this.renderer = new PointCloud2DRenderer(this.dom, rendererOptions);
        }

        this.renderer.init();
        this._initialized = true;

        return this;
    }

    /**
     * 设置点云数据
     * @param {Array<{x:number, y:number, z:number}>} points
     * @returns {this}
     */
    setData(points) {
        if (!this._initialized) {
            throw new Error('请先调用 init() 初始化');
        }
        this.renderer.setData(points);
        return this;
    }

    /**
     * 渲染点云
     * @returns {this}
     */
    render() {
        if (!this._initialized) {
            throw new Error('请先调用 init() 初始化');
        }
        this.renderer.render();

        if (this.options.onReady) {
            this.options.onReady(this.renderer);
        }

        return this;
    }

    /**
     * 从 TXT 文件内容加载并渲染
     * @param {string} content - TXT 文件文本内容
     * @returns {Promise<this>}
     */
    async loadFromContent(content) {
        try {
            // 创建解析器
            this.parser = new TxtPointParser({
                ...this.options.parserOptions,
                onProgress: this.options.onProgress,
            });

            // 解析文件
            const { mode, points } = this.parser.parse(content);

            // 初始化渲染器
            this.init(mode);

            // 设置数据并渲染
            this.setData(points);
            this.render();

            return this;
        } catch (error) {
            if (this.options.onError) {
                this.options.onError(error);
            }
            throw error;
        }
    }

    /**
     * 从 File 对象加载并渲染（浏览器文件上传）
     * @param {File} file - 浏览器 File 对象
     * @returns {Promise<this>}
     */
    async loadFromFile(file) {
        try {
            // 创建解析器
            this.parser = new TxtPointParser({
                ...this.options.parserOptions,
                onProgress: this.options.onProgress,
            });

            // 解析文件
            const { mode, points } = await this.parser.parseFile(file);

            // 初始化渲染器
            this.init(mode);

            // 设置数据并渲染
            this.setData(points);
            this.render();

            return this;
        } catch (error) {
            if (this.options.onError) {
                this.options.onError(error);
            }
            throw error;
        }
    }

    /**
     * 从 URL 加载并渲染
     * @param {string} url - 文件 URL
     * @returns {Promise<this>}
     */
    async loadFromUrl(url) {
        try {
            // 创建解析器
            this.parser = new TxtPointParser({
                ...this.options.parserOptions,
                onProgress: this.options.onProgress,
            });

            // 解析文件
            const { mode, points } = await this.parser.parseFromUrl(url);

            // 初始化渲染器
            this.init(mode);

            // 设置数据并渲染
            this.setData(points);
            this.render();

            return this;
        } catch (error) {
            if (this.options.onError) {
                this.options.onError(error);
            }
            throw error;
        }
    }

    /**
     * 更新数据并重新渲染
     * @param {Array<{x:number, y:number, z:number}>} points
     * @returns {this}
     */
    update(points) {
        if (!this._initialized) {
            throw new Error('请先调用 init() 初始化');
        }
        this.renderer.update(points);
        return this;
    }

    /**
     * 切换渲染模式
     * @param {string} mode - '3d' | '2d'
     * @returns {this}
     */
    switchMode(mode) {
        if (mode === this.currentMode) return this;

        // 保留当前数据
        const currentPoints = this.renderer ? this.renderer.points : [];

        // 重新初始化
        this.init(mode);

        if (currentPoints.length > 0) {
            this.setData(currentPoints);
            this.render();
        }

        return this;
    }

    /**
     * 获取当前渲染器实例
     * @returns {PointCloud3DRenderer|PointCloud2DRenderer|null}
     */
    getRenderer() {
        return this.renderer;
    }

    /**
     * 获取当前渲染模式
     * @returns {string|null}
     */
    getMode() {
        return this.currentMode;
    }

    /**
     * 销毁实例，释放资源
     */
    dispose() {
        if (this.renderer) {
            this.renderer.dispose();
            this.renderer = null;
        }
        this.parser = null;
        this._initialized = false;
        this.currentMode = null;
    }
}
