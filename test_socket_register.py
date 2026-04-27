#!/usr/bin/env python3
"""
测试 SocketRegisterAccess 类的脚本
注意：这只是一个示例，实际使用时需要提供正确的SSH连接参数
"""

import sys
sys.path.insert(0, '.')

try:
    from register_tool import SocketRegisterAccess, MockRegisterAccess, RegisterBank
    print("导入成功")
except ImportError as e:
    print(f"导入失败: {e}")
    sys.exit(1)

def test_mock():
    """测试模拟访问器"""
    print("\n=== 测试模拟访问器 ===")
    access = MockRegisterAccess()
    bank = RegisterBank(access, "测试寄存器组")

    # 写入测试值
    bank.write(0x1000, 0x12345678)

    # 读取测试值
    transaction = bank.read(0x1000)
    print(f"地址: 0x{transaction.address:08x}")
    print(f"值: 0x{transaction.raw_value:08x}")

    return True

def test_socket_example():
    """展示SocketRegisterAccess的使用示例"""
    print("\n=== SocketRegisterAccess 使用示例 ===")
    print("""
# 基本用法示例：
access = SocketRegisterAccess(
    ssh_host="remote-server",
    ssh_username="root",
    telnet_port=5040,
    debug=False,           # 设置为True可查看详细通信信息
    use_32_param=True     # 根据服务器要求调整
)

try:
    # 读取寄存器
    value = access.read_register(0x1000)
    print(f"寄存器值: 0x{value:08x}")
except Exception as e:
    print(f"读取失败: {e}")
finally:
    access.close()

# 根据用户提供的服务器响应示例，可能需要以下设置：
# 1. use_32_param=False (如果服务器命令不需要"32"参数)
# 2. 地址可能是64位，如0x20202000461
# 3. 调试模式可以帮助诊断问题
    """)

def main():
    print("SocketRegisterAccess 测试脚本")
    print("=" * 50)

    # 测试模拟访问器
    test_mock()

    # 显示Socket访问器使用示例
    test_socket_example()

    print("\n注意事项:")
    print("1. 需要安装 paramiko: pip install paramiko")
    print("2. 需要正确的SSH密钥或密码认证")
    print("3. 远程服务器需要运行telnet服务在5040/5050端口")
    print("4. 使用debug=True可以查看详细通信信息")
    print("5. 根据服务器响应调整use_32_param参数")

if __name__ == "__main__":
    main()