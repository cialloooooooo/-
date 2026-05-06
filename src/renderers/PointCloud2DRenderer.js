/**
 * PointCloud2DRenderer - 2D 点云渲染器
 *
 * 基于 ECharts 散点图实现高性能 2D 点云渲染
 * 支持 50 万级别点云数据的流畅渲染
 *
 * 注意：这是一个预留实现，后续可根据需求扩展更多 2D 渲染能力
 * 例如：热力图、密度图、聚类图等
 */

import PointCloudRenderer from '../core/PointCloudRenderer.js';

export default class PointCloud2DRenderer extends PointCloudRenderer {
    /**
     * @param {HTMLElement|string} dom
     * @param {Object} [options]
     * @param {number} [options.pointSize=2] - 2D 点的大小
     * @param {string} [options.symbol='circle'] - 点的形状：'circle' | 'rect' | 'diamond' | 'triangle'
     * @param {boolean} [options.showGrid=true] - 是否显示网格
     * @param {boolean} [options.sampling=false] - 是否启用数据采样（大量点时提升性能）
     * @param {number} [options.progressive=5000] - 渐进渲染阈值
     * @param {number} [options.progressiveThreshold=30000] - 渐进渲染步长
     * @param {Function} [options.colorMapper] - 自定义颜色映射
     * @param {Object} [options.chartOptions] - 额外 ECharts 配置
     */
    constructor(dom, options = {}) {
        super(dom, {
            renderMode: '2d',
            ...options,
        });

        this.options = {
            ...this.options,
            pointSize: options.pointSize ?? 2,
            symbol: options.symbol ?? 'circle',
            showGrid: options.showGrid ?? true,
            sampling: options.sampling ?? false,
            progressive: options.progressive ?? 5000,
            progressiveThreshold: options.progressiveThreshold ?? 30000,
        };
    }

    /**
     * 渲染 2D 点云
     * @override
     * @returns {this}
     */
    render() {
        if (!this._initialized) {
            throw new Error('请先调用 init() 方法初始化');
        }

        const { minX, maxX, minY, maxY, minZ, maxZ } = this.dataRange;
        const points = this.points;

        // 构建数据数组：[[x, y, z, color], ...]
        // 保留 z 值用于颜色映射
        const data = new Array(points.length);
        for (let i = 0; i < points.length; i++) {
            const p = points[i];
            data[i] = [p.x, p.y, p.z, this._getColor(p.z)];
        }

        const option = {
            tooltip: {
                formatter: (params) => {
                    const d = params.data;
                    return `X: ${d[0].toFixed(2)}<br/>Y: ${d[1].toFixed(2)}<br/>Z: ${d[2].toFixed(2)}`;
                },
            },
            grid: {
                show: this.options.showGrid,
                left: '10%',
                right: '10%',
                bottom: '10%',
                top: '10%',
                containLabel: true,
            },
            xAxis: {
                type: 'value',
                name: 'X',
                min: minX,
                max: maxX,
                splitLine: {
                    show: this.options.showGrid,
                },
            },
            yAxis: {
                type: 'value',
                name: 'Y',
                min: minY,
                max: maxY,
                splitLine: {
                    show: this.options.showGrid,
                },
            },
            // 可选：添加视觉映射组件，展示 z 值颜色映射
            visualMap: {
                show: true,
                min: minZ,
                max: maxZ,
                dimension: 2, // 使用第 3 维（z 值）做映射
                inRange: {
                    color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#fee090', '#fdae61', '#f46d43', '#d73027'],
                },
                calculable: true,
                text: ['高 Z', '低 Z'],
                textStyle: {
                    color: '#333',
                },
            },
            series: [
                {
                    type: 'scatter',
                    data: data,
                    symbolSize: this.options.pointSize,
                    symbol: this.options.symbol,
                    // 使用 itemStyle 的 color 为每个点单独着色
                    // 如果 visualMap 启用，则 visualMap 会覆盖此设置
                    itemStyle: {
                        color: (params) => params.data[3],
                        opacity: 0.7,
                    },
                    // 渐进渲染
                    progressive: this.options.progressive,
                    progressiveThreshold: this.options.progressiveThreshold,
                    // 数据采样
                    sampling: this.options.sampling ? 'lttb' : 'none',
                    // 关闭动画
                    animation: false,
                    // 关闭标签
                    label: {
                        show: false,
                    },
                    // 关闭 emphasis 高亮（提升性能）
                    emphasis: {
                        scale: false,
                        label: {
                            show: false,
                        },
                    },
                },
            ],
            // 合并用户自定义 chartOptions
            ...this.options.chartOptions,
        };

        this.chart.setOption(option, true);
        return this;
    }

    /**
     * 设置点的大小
     * @param {number} size
     * @returns {this}
     */
    setPointSize(size) {
        this.options.pointSize = size;
        if (this._initialized) {
            this.render();
        }
        return this;
    }

    /**
     * 设置点的形状
     * @param {string} symbol - 'circle' | 'rect' | 'diamond' | 'triangle'
     * @returns {this}
     */
    setSymbol(symbol) {
        this.options.symbol = symbol;
        if (this._initialized) {
            this.render();
        }
        return this;
    }

    /**
     * 切换网格显示
     * @param {boolean} show
     * @returns {this}
     */
    toggleGrid(show) {
        this.options.showGrid = show;
        if (this._initialized) {
            this.render();
        }
        return this;
    }
}
