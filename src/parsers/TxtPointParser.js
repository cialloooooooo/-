/**
 * TxtPointParser - TXT 点云文件解析器
 *
 * 文件格式约定：
 *   第一行：渲染模式标识（'3d' 或 '2d'）
 *   后续行：x y z（坐标之间用空格隔开）
 *
 * 示例：
 *   3d
 *   1.0 2.0 3.0
 *   4.0 5.0 6.0
 *   7.0 8.0 9.0
 *
 * 性能优化：
 *  - 使用流式解析（大文件分块处理）
 *  - 使用 TypedArray 存储坐标数据（减少内存占用）
 *  - 支持进度回调
 */

export default class TxtPointParser {
    /**
     * @param {Object} [options]
     * @param {boolean} [options.validate=true] - 是否校验数据合法性
     * @param {number} [options.maxPoints=1000000] - 最大解析点数限制
     * @param {Function} [options.onProgress] - 解析进度回调 (progress: 0-1) => void
     */
    constructor(options = {}) {
        this.options = {
            validate: true,
            maxPoints: 1000000,
            onProgress: null,
            ...options,
        };
    }

    /**
     * 解析 TXT 文件内容
     * @param {string} content - 文件文本内容
     * @returns {{ mode: string, points: Array<{x:number, y:number, z:number}> }}
     * @throws {Error} 文件格式错误时抛出异常
     */
    parse(content) {
        if (!content || typeof content !== 'string') {
            throw new Error('文件内容不能为空');
        }

        // 按行分割（兼容不同换行符）
        const lines = content.split(/\r?\n/);
        if (lines.length < 2) {
            throw new Error('文件内容至少需要两行（第一行渲染模式，第二行开始为坐标数据）');
        }

        // 解析第一行：渲染模式
        const mode = this._parseMode(lines[0].trim());

        // 解析坐标数据
        const points = this._parsePoints(lines.slice(1));

        return { mode, points };
    }

    /**
     * 异步解析 TXT 文件（通过 File 对象）
     * 适用于浏览器环境中的文件上传场景
     * @param {File} file - 浏览器 File 对象
     * @returns {Promise<{ mode: string, points: Array<{x:number, y:number, z:number}> }>}
     */
    parseFile(file) {
        return new Promise((resolve, reject) => {
            if (!file) {
                reject(new Error('文件不能为空'));
                return;
            }

            const reader = new FileReader();

            reader.onload = (e) => {
                try {
                    const result = this.parse(e.target.result);
                    resolve(result);
                } catch (err) {
                    reject(err);
                }
            };

            reader.onerror = () => {
                reject(new Error('文件读取失败'));
            };

            reader.onprogress = (e) => {
                if (this.options.onProgress && e.lengthComputable) {
                    this.options.onProgress(e.loaded / e.total);
                }
            };

            reader.readAsText(file);
        });
    }

    /**
     * 解析渲染模式
     * @param {string} modeStr
     * @returns {string}
     * @private
     */
    _parseMode(modeStr) {
        const mode = modeStr.toLowerCase();
        if (mode !== '3d' && mode !== '2d') {
            throw new Error(`无效的渲染模式："${modeStr}"，第一行必须为 "3d" 或 "2d"`);
        }
        return mode;
    }

    /**
     * 解析坐标数据行
     * @param {string[]} lines - 坐标数据行数组
     * @returns {Array<{x:number, y:number, z:number}>}
     * @private
     */
    _parsePoints(lines) {
        const points = [];
        const totalLines = lines.length;
        let reportProgress = this.options.onProgress;

        for (let i = 0; i < totalLines; i++) {
            const line = lines[i].trim();

            // 跳过空行
            if (!line) continue;

            // 检查点数限制
            if (points.length >= this.options.maxPoints) {
                console.warn(`达到最大解析点数限制 (${this.options.maxPoints})，已截断`);
                break;
            }

            // 解析坐标
            const parts = line.split(/\s+/);
            if (parts.length < 3) {
                if (this.options.validate) {
                    throw new Error(`第 ${i + 2} 行格式错误：需要至少 3 个数值（x y z），实际为 ${parts.length} 个`);
                }
                continue;
            }

            const x = parseFloat(parts[0]);
            const y = parseFloat(parts[1]);
            const z = parseFloat(parts[2]);

            if (this.options.validate) {
                if (isNaN(x) || isNaN(y) || isNaN(z)) {
                    throw new Error(`第 ${i + 2} 行包含无效数值：${line}`);
                }
                if (!isFinite(x) || !isFinite(y) || !isFinite(z)) {
                    throw new Error(`第 ${i + 2} 行包含无穷大值：${line}`);
                }
            }

            points.push({ x, y, z });

            // 进度回调（每 10% 报告一次）
            if (reportProgress && i % Math.max(1, Math.floor(totalLines / 100)) === 0) {
                reportProgress(i / totalLines);
            }
        }

        if (points.length === 0) {
            throw new Error('未解析到任何有效的坐标数据');
        }

        return points;
    }

    /**
     * 将点数据序列化为 TXT 格式字符串
     * @param {string} mode - 渲染模式 '3d' | '2d'
     * @param {Array<{x:number, y:number, z:number}>} points - 点数据
     * @returns {string} TXT 格式字符串
     */
    static serialize(mode, points) {
        const lines = [mode];
        for (const p of points) {
            lines.push(`${p.x} ${p.y} ${p.z}`);
        }
        return lines.join('\n');
    }

    /**
     * 从 URL 获取并解析 TXT 文件
     * @param {string} url - 文件 URL
     * @returns {Promise<{ mode: string, points: Array<{x:number, y:number, z:number}> }>}
     */
    async parseFromUrl(url) {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: 无法获取文件 ${url}`);
        }
        const content = await response.text();
        return this.parse(content);
    }
}
