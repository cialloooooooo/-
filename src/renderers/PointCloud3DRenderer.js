/**
 * PointCloud3DRenderer - 3D 点云渲染器
 *
 * 基于 ECharts GL 实现高性能 3D 散点图渲染
 * 支持 50 万级别点云数据的流畅渲染
 *
 * 性能优化策略：
 *  1. 使用 scatter3D 系列，利用 WebGL 硬件加速
 *  2. 关闭动画（animationDuration: 0）
 *  3. 使用 symbolSize 控制点大小而非复杂图形
 *  4. 数据量极大时自动启用渐进渲染（progressive）
 *  5. 关闭不必要的交互效果
 *
 * 交互功能：
 *  - 支持点击选中点，通过 onPointClick 回调返回坐标信息
 *  - 选中点会高亮显示（放大 + 变色）
 *  - 支持清除选中状态
 */

import PointCloudRenderer from '../core/PointCloudRenderer.js';

export default class PointCloud3DRenderer extends PointCloudRenderer {
    /**
     * @param {HTMLElement|string} dom
     * @param {Object} [options]
     * @param {number} [options.pointSize=1] - 3D 点的大小
     * @param {boolean} [options.autoRotate=false] - 是否自动旋转
     * @param {number} [options.autoRotateSpeed=10] - 自动旋转速度
     * @param {number} [options.progressive=5000] - 渐进渲染阈值（点数超过此值启用渐进渲染）
     * @param {number} [options.progressiveThreshold=30000] - 渐进渲染步长
     * @param {Object} [options.grid3D] - 3D 坐标系自定义配置
     * @param {Function} [options.colorMapper] - 自定义颜色映射
     * @param {Object} [options.chartOptions] - 额外 ECharts 配置
     * @param {Function} [options.onPointClick] - 点击点回调 (point: {x, y, z, index}) => void
     * @param {boolean} [options.enableClick=true] - 是否启用点击选中功能
     */
    constructor(dom, options = {}) {
        super(dom, {
            renderMode: '3d',
            ...options,
        });

        this.options = {
            ...this.options,
            pointSize: options.pointSize ?? 1,
            autoRotate: options.autoRotate ?? false,
            autoRotateSpeed: options.autoRotateSpeed ?? 10,
            progressive: options.progressive ?? 5000,
            progressiveThreshold: options.progressiveThreshold ?? 30000,
            grid3D: options.grid3D ?? {},
            onPointClick: options.onPointClick || null,
            enableClick: options.enableClick !== false,
        };

        /** 当前选中的点索引 */
        this._selectedIndex = -1;

        /** 点击事件是否已绑定 */
        this._clickBound = false;
    }

    /**
     * 初始化（扩展：绑定点击事件）
     * @override
     */
    init() {
        super.init();
        if (this.options.enableClick) {
            this._bindClickEvent();
        }
        return this;
    }

    /**
     * 绑定点击事件
     * @protected
     */
    _bindClickEvent() {
        if (this._clickBound || !this.chart) return;

        this.chart.on('click', 'series.scatter3D', (params) => {
            // params.data 格式：[x, y, z, color]
            const data = params.data;
            const index = params.dataIndex;

            if (!data) return;

            const point = {
                x: data[0],
                y: data[1],
                z: data[2],
                index: index,
            };

            // 选中该点（高亮）
            this._selectedIndex = index;
            this._highlightPoint(index);

            // 触发回调
            if (this.options.onPointClick) {
                this.options.onPointClick(point);
            }
        });

        // 点击空白区域取消选中
        this.chart.getZr().on('click', (params) => {
            // 判断是否点击在图形上
            const target = params.target;
            if (!target) {
                this.clearSelection();
            }
        });

        this._clickBound = true;
    }

    /**
     * 高亮选中的点
     * 通过更新 series 中对应数据项的样式来实现
     * @param {number} index - 选中的点索引
     * @protected
     */
    _highlightPoint(index) {
        if (!this.chart || index < 0) return;

        // 使用 ECharts 的 dispatchAction 来高亮
        this.chart.dispatchAction({
            type: 'highlight',
            seriesIndex: 0,
            dataIndex: index,
        });
    }

    /**
     * 清除选中状态
     * @returns {this}
     */
    clearSelection() {
        if (this._selectedIndex >= 0 && this.chart) {
            this.chart.dispatchAction({
                type: 'downplay',
                seriesIndex: 0,
            });
            this._selectedIndex = -1;

            // 触发取消选中回调
            if (this.options.onPointClick) {
                this.options.onPointClick(null);
            }
        }
        return this;
    }

    /**
     * 获取当前选中的点
     * @returns {{x:number, y:number, z:number, index:number}|null}
     */
    getSelectedPoint() {
        if (this._selectedIndex < 0 || !this.points[this._selectedIndex]) {
            return null;
        }
        const p = this.points[this._selectedIndex];
        return { ...p, index: this._selectedIndex };
    }

    /**
     * 加载 ECharts（需要 echarts-gl 扩展）
     * @override
     * @protected
     */
    _loadECharts() {
        if (typeof echarts !== 'undefined') return echarts;
        throw new Error('请先引入 ECharts 和 echarts-gl 库');
    }

    /**
     * 渲染 3D 点云
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
        const data = new Array(points.length);
        for (let i = 0; i < points.length; i++) {
            const p = points[i];
            data[i] = [p.x, p.y, p.z, this._getColor(p.z)];
        }

        // 构建 ECharts option
        const option = {
            tooltip: {
                formatter: (params) => {
                    const d = params.data;
                    return `X: ${d[0].toFixed(2)}<br/>Y: ${d[1].toFixed(2)}<br/>Z: ${d[2].toFixed(2)}`;
                },
            },
            grid3D: {
                show: true,
                boxWidth: 100,
                boxHeight: 100,
                boxDepth: 100,
                axisPointer: {
                    show: false,
                },
                viewControl: {
                    autoRotate: this.options.autoRotate,
                    autoRotateSpeed: this.options.autoRotateSpeed,
                    distance: this._calcCameraDistance(),
                    minDistance: 10,
                    maxDistance: 500,
                    alpha: 30,
                    beta: 45,
                },
                postEffect: {
                    enable: false,
                },
                light: {
                    main: {
                        intensity: 1.2,
                        shadow: false,
                    },
                    ambient: {
                        intensity: 0.6,
                    },
                },
                ...this.options.grid3D,
            },
            xAxis3D: {
                type: 'value',
                name: 'X',
                min: minX,
                max: maxX,
            },
            yAxis3D: {
                type: 'value',
                name: 'Y',
                min: minY,
                max: maxY,
            },
            zAxis3D: {
                type: 'value',
                name: 'Z',
                min: minZ,
                max: maxZ,
            },
            series: [
                {
                    type: 'scatter3D',
                    data: data,
                    symbolSize: this.options.pointSize,
                    itemStyle: {
                        color: (params) => params.data[3],
                        opacity: 0.8,
                    },
                    progressive: this.options.progressive,
                    progressiveThreshold: this.options.progressiveThreshold,
                    animation: false,
                    // 启用选中模式（支持点击高亮）
                    selectedMode: this.options.enableClick ? 'single' : false,
                    label: {
                        show: false,
                    },
                    // emphasis 状态：鼠标悬停或选中时放大并显示标签
                    emphasis: {
                        scale: true,
                        focus: 'series',
                        label: {
                            show: true,
                            formatter: (params) => {
                                const d = params.data;
                                return `(${d[0].toFixed(1)}, ${d[1].toFixed(1)}, ${d[2].toFixed(1)})`;
                            },
                            position: 'top',
                            fontSize: 12,
                            color: '#fff',
                            backgroundColor: 'rgba(0,0,0,0.6)',
                            padding: [4, 8],
                            borderRadius: 4,
                        },
                    },
                    blendMode: 'source-over',
                },
            ],
            ...this.options.chartOptions,
        };

        this.chart.setOption(option, true);

        // 重新绑定点击事件（setOption 后需要重新绑定）
        if (this.options.enableClick && !this._clickBound) {
            this._bindClickEvent();
        }

        return this;
    }

    /**
     * 根据数据范围自动计算相机距离
     * @returns {number}
     * @private
     */
    _calcCameraDistance() {
        const { minX, maxX, minY, maxY, minZ, maxZ } = this.dataRange;
        const rangeX = maxX - minX || 1;
        const rangeY = maxY - minY || 1;
        const rangeZ = maxZ - minZ || 1;
        const maxRange = Math.max(rangeX, rangeY, rangeZ);
        return Math.max(maxRange * 2.5, 100);
    }

    /**
     * 设置自动旋转
     * @param {boolean} enable
     * @param {number} [speed]
     * @returns {this}
     */
    setAutoRotate(enable, speed) {
        this.options.autoRotate = enable;
        if (speed !== undefined) {
            this.options.autoRotateSpeed = speed;
        }
        if (this._initialized) {
            this.render();
        }
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
     * 销毁
     * @override
     */
    dispose() {
        if (this.chart && this._clickBound) {
            this.chart.off('click');
            if (this.chart.getZr()) {
                this.chart.getZr().off('click');
            }
        }
        this._clickBound = false;
        this._selectedIndex = -1;
        super.dispose();
    }
}
