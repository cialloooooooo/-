/**
 * 生成测试点云数据
 * 用于演示和性能测试
 *
 * 使用方法：
 *   node demo/generate-test-data.js [点数] [输出文件]
 *
 * 示例：
 *   node demo/generate-test-data.js 1000 demo/test-1k.txt
 *   node demo/generate-test-data.js 500000 demo/test-500k.txt
 */

const fs = require('fs');
const path = require('path');

// 获取参数
const count = parseInt(process.argv[2]) || 1000;
const outputFile = process.argv[3] || path.join(__dirname, 'test-data.txt');

console.log(`正在生成 ${count} 个测试点...`);

// 生成球体形状的点云数据（带随机扰动）
const lines = ['3d'];
for (let i = 0; i < count; i++) {
    // 使用球坐标生成球体分布
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const radius = 50 + (Math.random() - 0.5) * 10; // 半径 50 左右，带扰动

    const x = radius * Math.sin(phi) * Math.cos(theta);
    const y = radius * Math.sin(phi) * Math.sin(theta);
    const z = radius * Math.cos(phi);

    lines.push(`${x.toFixed(4)} ${y.toFixed(4)} ${z.toFixed(4)}`);
}

const content = lines.join('\n');
fs.writeFileSync(outputFile, content, 'utf-8');

console.log(`已生成 ${count} 个测试点，保存至: ${outputFile}`);
console.log(`文件大小: ${(Buffer.byteLength(content) / 1024).toFixed(2)} KB`);
