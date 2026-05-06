/**
 * PointCloudRenderer - 点云渲染引擎基类
 *
 * 职责：
 *  - 提供统一的渲染生命周期管理（init、render、dispose）
 *  - 定义子类必须实现的接口
 *  - 提供公共的工具方法（颜色映射、坐标归一化等）
 *
 * 设计思路：
 *  - 采用模板方法模式，子类只需实现 render() 和 dispose() 即可
 *  - 颜色映射策略可插拔，方便扩展不同的配色方案
 *  - 预留了坐标预处理钩子，方便子类做特殊处理
 */

export default class PointCloudRenderer {
    /**
     * @param {HTMLElement|string} dom - 容器 DOM 元素或其 ID
     * @param {Object} [options] - 配置项
     * @param {string} [options.renderMode='3d'] - 渲染模式：'3d' | '2d'
     * @param {Function} [options.colorMapper] - 自定义颜色映射函数 (zValue, minZ, maxZ) => color
     * @param {Object} [options.chartOptions] - 额外的 ECharts 配置，会与默认配置合并
     * @param {boolean} [options.autoResize=true] - 是否自动监听窗口 resize
     * @param {number} [options.pointSize=1] - 点的大小
     * @param {number} [options.animationDuration=0] - 动画时长（毫秒），大量点建议设为 0
     */
    constructor(dom, options = {}) {
        if (new.target === PointCloudRenderer) {
            throw new Error('PointCloudRenderer 是抽象类，不能直接实例化');
        }

        this.dom = typeof dom === 'string' ? document.getElementById(dom) : dom;
        if (!this.dom) {
            throw new Error('无效的 DOM 容器');
        }

        this.options = {
            renderMode: '3d',
            autoResize: true,
            pointSize: 1,
            animationDuration: 0,
            colorMapper: null,
            chartOptions: {},
            ...options,
        };

        /** @type {import('echarts').ECharts|null} */
        this.chart = null;

        /** @type {Array<{x:number, y:number, z:number}>} */
        this.points = [];

        /** 数据范围统计 */
        this.dataRange = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity, minZ: Infinity, maxZ: -Infinity };

        /** 是否已初始化 */
        this._initialized = false;

        /** resize 防抖句柄 */
        this._resizeHandler = null;
    }

    /**
     * 初始化 ECharts 实例
     * @returns {this}
     */
    init() {
        if (this._initialized) {
            console.warn('PointCloudRenderer 已经初始化，请勿重复调用');
            return this;
        }

        // 动态导入 echarts（支持按需加载）
        const echarts = this._loadECharts();
        this.chart = echarts.init(this.dom);

        if (this.options.autoResize) {
            this._bindResize();
        }

        this._initialized = true;
        return this;
    }

    /**
     * 加载 ECharts 实例（子类可重写以支持不同版本的 echarts）
     * @protected
     */
    _loadECharts() {
        // 默认从全局 window.echarts 获取，也支持 import 传入
        if (typeof echarts !== 'undefined') return echarts;
        throw new Error('请先引入 ECharts 库');
    }

    /**
     * 绑定窗口 resize 事件
     * @protected
     */
    _bindResize() {
        this._resizeHandler = () => {
            if (this.chart) {
                this.chart.resize();
            }
        };
        window.addEventListener('resize', this._resizeHandler);
    }

    /**
     * 设置点云数据
     * @param {Array<{x:number, y:number, z:number}>} points - 点数据数组
     * @returns {this}
     */
    setData(points) {
        if (!Array.isArray(points)) {
            throw new Error('点数据必须是一个数组');
        }
        this.points = points;
        this._calcDataRange();
        return this;
    }

    /**
     * 计算数据范围
     * @protected
     */
    _calcDataRange() {
        const range = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity, minZ: Infinity, maxZ: -Infinity };

        for (let i = 0, len = this.points.length; i < len; i++) {
            const p = this.points[i];
            if (p.x < range.minX) range.minX = p.x;
            if (p.x > range.maxX) range.maxX = p.x;
            if (p.y < range.minY) range.minY = p.y;
            if (p.y > range.maxY) range.maxY = p.y;
            if (p.z < range.minZ) range.minZ = p.z;
            if (p.z > range.maxZ) range.maxZ = p.z;
        }

        this.dataRange = range;
    }

    /**
     * 获取默认的颜色映射函数
     * 将 z 值映射到颜色（从蓝到红渐变）
     * @param {number} z - Z 坐标值
     * @param {number} minZ - Z 最小值
     * @param {number} maxZ - Z 最大值
     * @returns {string} CSS 颜色字符串
     */
    static defaultColorMapper(z, minZ, maxZ) {
        if (minZ === maxZ) return '#5470c6';

        // 将 z 值归一化到 [0, 1]
        const t = (z - minZ) / (maxZ - minZ);

        // 蓝 -> 青 -> 绿 -> 黄 -> 红 渐变
        const r = Math.min(255, Math.floor(t * 510));
        const g = Math.min(255, Math.floor((1 - Math.abs(t - 0.5) * 2) * 255));
        const b = Math.min(255, Math.floor((1 - t) * 510));

        return `rgb(${Math.min(255, r)}, ${Math.min(255, g)}, ${Math.min(255, b)})`;
    }

    /**
     * 获取颜色值
     * 优先使用自定义 colorMapper，否则使用默认映射
     * @param {number} z
     * @returns {string}
     * @protected
     */
    _getColor(z) {
        const { minZ, maxZ } = this.dataRange;
        if (this.options.colorMapper) {
            return this.options.colorMapper(z, minZ, maxZ);
        }
        return PointCloudRenderer.defaultColorMapper(z, minZ, maxZ);
    }

    /**
     * 渲染点云（抽象方法，子类必须实现）
     * @abstract
     * @returns {this}
     */
    render() {
        throw new Error('子类必须实现 render() 方法');
    }

    /**
     * 更新数据并重新渲染
     * @param {Array<{x:number, y:number, z:number}>} points
     * @returns {this}
     */
    update(points) {
        this.setData(points);
        return this.render();
    }

    /**
     * 销毁实例，释放资源
     */
    dispose() {
        if (this._resizeHandler) {
            window.removeEventListener('resize', this._resizeHandler);
            this._resizeHandler = null;
        }
        if (this.chart) {
            this.chart.dispose();
            this.chart = null;
        }
        this.points = [];
        this._initialized = false;
    }

    /**
     * 获取当前 ECharts 实例
     * @returns {import('echarts').ECharts|null}
     */
    getChart() {
        return this.chart;
    }

    /**
     * 获取数据范围
     * @returns {{minX:number, maxX:number, minY:number, maxY:number, minZ:number, maxZ:number}}
     */
    getDataRange() {
        return { ...this.dataRange };
    }
}
