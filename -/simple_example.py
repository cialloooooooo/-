#!/usr/bin/env python3
"""
Telnet寄存器管理器 - 简单使用示例

这个示例展示了如何使用telnet_register_manager.py的基本功能
"""

# 直接导入，假设文件在同一目录
try:
    from telnet_register_manager import (
        Register, RegisterSet, TelnetRegisterAccess,
        bitfield_parser, create_register_set_from_dict,
        parser_registry
    )
except ImportError:
    print("请将本文件放在与telnet_register_manager.py相同的目录下")
    print("或者修改导入路径")
    exit(1)


def simple_example():
    """最简单的使用示例"""
    print("=== 简单使用示例 ===\n")

    # 1. 创建Telnet连接（这里使用模拟模式，实际使用时需要真实服务器）
    print("1. 创建Telnet连接")

    # 模拟访问器（实际使用时替换为真实Telnet连接）
    class MockAccess:
        def read_register(self, address):
            # 模拟返回不同的值
            if address == 0x1000:
                return 0x0000000F  # CTRL
            elif address == 0x1004:
                return 0x00000005  # STATUS
            else:
                return 0x00000000

        def write_register(self, address, value):
            print(f"写入 0x{address:08x} = 0x{value:08x}")
            return True

        def close(self):
            print("连接关闭")

    access = MockAccess()

    # 实际使用时：
    # access = TelnetRegisterAccess(
    #     host='192.168.1.100',
    #     username='root',
    #     password='password',
    #     read_command="read_reg 0x{address:08x}"
    # )

    # 2. 创建寄存器对象
    print("\n2. 创建寄存器对象")

    # 创建控制寄存器
    ctrl_reg = Register(
        name="CTRL",
        address=0x1000,
        description="控制寄存器"
    )

    # 创建状态寄存器
    status_reg = Register(
        name="STATUS",
        address=0x1004,
        description="状态寄存器"
    )

    # 3. 创建寄存器组
    print("\n3. 创建寄存器组")
    regset = RegisterSet(access, name="我的寄存器组")
    regset.add_register(ctrl_reg)
    regset.add_register(status_reg)

    # 4. 定义解析器
    print("\n4. 定义解析器")

    # 为CTRL寄存器创建位域解析器
    ctrl_parser = bitfield_parser({
        'enable': {'bits': (0, 0), 'description': '使能位'},
        'mode': {'bits': (1, 3), 'description': '模式选择'}
    })
    ctrl_reg.set_parser(ctrl_parser)

    # 为STATUS寄存器创建简单解析器
    def status_parser(value):
        return {
            'ready': (value >> 0) & 0x1,
            'busy': (value >> 1) & 0x1,
            'error': (value >> 2) & 0x1,
            'status': '正常' if ((value >> 0) & 0x1) else '未就绪'
        }
    status_reg.set_parser(status_parser)

    # 5. 批量读取所有寄存器（先获取原始值）
    print("\n5. 批量读取所有寄存器")
    regset.read_all()

    # 6. 执行解析函数
    print("\n6. 执行解析函数")
    regset.parse_all()

    # 7. 查看结果
    print("\n7. 查看结果")
    for reg in [ctrl_reg, status_reg]:
        print(f"\n{reg.name}寄存器:")
        print(f"  地址: {reg.get_hex_address()}")
        print(f"  原始值: {reg.get_hex_value()}")
        print(f"  解析结果: {reg.parsed_result}")

    # 8. 保存结果
    print("\n8. 保存结果到JSON")
    regset.save_to_json("simple_results.json")

    # 9. 关闭连接
    print("\n9. 关闭连接")
    access.close()

    print("\n=== 示例完成 ===")


def dict_example():
    """使用字典定义寄存器的示例"""
    print("\n\n=== 使用字典定义寄存器示例 ===\n")

    # 模拟访问器
    class MockAccess:
        def read_register(self, address):
            return 0x12345678  # 固定返回值用于演示

        def write_register(self, address, value):
            return True

        def close(self):
            pass

    access = MockAccess()

    # 寄存器定义字典
    register_defs = {
        'REG1': {
            'address': 0x2000,
            'description': '寄存器1',
            'parser': lambda x: {'value': x, 'hex': f'0x{x:08x}'}
        },
        'REG2': {
            'address': 0x2004,
            'description': '寄存器2',
            'parser': bitfield_parser({
                'bit0': {'bits': (0, 0), 'description': '位0'},
                'bit1_3': {'bits': (1, 3), 'description': '位1-3'}
            })
        },
        'REG3': {
            'address': 0x2008,
            'description': '寄存器3'
            # 无解析器
        }
    }

    # 使用工具函数创建寄存器组
    regset = create_register_set_from_dict(
        access, register_defs, name="字典示例组"
    )

    # 读取并解析
    regset.read_and_parse_all()

    # 打印摘要
    regset.print_summary()

    print("\n=== 字典示例完成 ===")


if __name__ == "__main__":
    simple_example()
    dict_example()