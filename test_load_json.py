#!/usr/bin/env python3
"""测试从JSON文件加载寄存器定义"""
import json
import os
from register_tool import MockRegisterAccess, RegisterBank, RegisterDefinition, BitFieldParser

def test_load_json():
    # 1. 首先创建一个JSON文件
    test_data = {
        "metadata": {
            "bank_name": "测试JSON加载",
            "export_time": "2026-03-18T12:00:00",
            "total_definitions": 3
        },
        "definitions": [
            {
                "address": 0x1000,
                "address_hex": "0x00001000",
                "name": "ctrl_reg",
                "description": "控制寄存器",
                "has_parser": True,
                "parser_type": "BitFieldParser"
            },
            {
                "address": 0x2000,
                "address_hex": "0x00002000",
                "name": "status_reg",
                "description": "状态寄存器",
                "has_parser": False,
                "parser_type": None
            },
            {
                "address": 0x3000,
                "address_hex": "0x00003000",
                "name": "config_reg",
                "description": "配置寄存器",
                "has_parser": True,
                "parser_type": "BitFieldParser"
            }
        ]
    }

    # 保存到文件
    with open("test_register_defs.json", "w", encoding="utf-8") as f:
        json.dump(test_data, f, indent=2, ensure_ascii=False)
    print("创建测试JSON文件: test_register_defs.json")

    # 2. 创建解析器工厂函数
    def my_parser_factory(def_dict):
        """根据定义信息创建解析器"""
        parser_type = def_dict.get('parser_type')
        name = def_dict.get('name')

        if parser_type == 'BitFieldParser':
            if name == 'ctrl_reg':
                return BitFieldParser({
                    'enable': {'bits': (0, 0), 'description': '使能位'},
                    'mode': {'bits': (1, 3), 'description': '模式'}
                })
            elif name == 'config_reg':
                return BitFieldParser({
                    'mode': {'bits': (0, 2), 'description': '工作模式'},
                    'enable': {'bits': (3, 3), 'description': '使能'}
                })
        return None

    # 3. 创建寄存器组并加载JSON
    access = MockRegisterAccess()
    bank = RegisterBank(access, "初始名称")

    print("\n从JSON文件加载寄存器定义...")
    loaded_count = bank.load_definitions_from_json(
        "test_register_defs.json",
        overwrite=True,
        parser_factory=my_parser_factory
    )
    print(f"成功加载 {loaded_count} 个寄存器定义")
    print(f"寄存器组名称: {bank.name}")

    # 4. 验证加载结果
    print("\n验证加载结果:")

    # 检查定义是否存在
    ctrl_def = bank.get_definition_by_name("ctrl_reg")
    assert ctrl_def is not None, "ctrl_reg 定义未找到"
    assert ctrl_def.address == 0x1000, "地址不正确"
    assert ctrl_def.description == "控制寄存器", "描述不正确"

    status_def = bank.get_definition_by_name("status_reg")
    assert status_def is not None, "status_reg 定义未找到"

    config_def = bank.get_definition_by_name("config_reg")
    assert config_def is not None, "config_reg 定义未找到"

    print("所有寄存器定义加载成功")

    # 5. 检查解析器是否正确设置
    print("\n检查解析器设置:")

    # ctrl_reg 应该有专属解析器
    ctrl_parser = bank.get_parser(0x1000)
    assert ctrl_parser is not None, "ctrl_reg 应该有关联的解析器"
    assert isinstance(ctrl_parser, BitFieldParser), "解析器类型应该是BitFieldParser"
    print("ctrl_reg 有专属解析器")

    # status_reg 应该没有专属解析器（工厂函数返回None）
    status_parser = bank.get_parser(0x2000)
    print(f"  status_reg 解析器: {status_parser}")

    # config_reg 应该有专属解析器
    config_parser = bank.get_parser(0x3000)
    assert config_parser is not None, "config_reg 应该有关联的解析器"
    assert isinstance(config_parser, BitFieldParser), "解析器类型应该是BitFieldParser"
    print("config_reg 有专属解析器")

    # 6. 测试按名称访问
    print("\n测试按名称访问寄存器:")

    # 写入测试值
    bank.write_by_name("ctrl_reg", 0x0000000F)

    # 读取并解析
    transaction = bank.read_by_name("ctrl_reg", use_parser=True)
    print(f"  读取 ctrl_reg: {transaction.get_hex_value()}")
    if transaction.parsed_data:
        print(f"    解析数据: {transaction.parsed_data}")
        assert 'enable' in transaction.parsed_data, "解析数据应包含'enable'字段"
        assert 'mode' in transaction.parsed_data, "解析数据应包含'mode'字段"
        print("解析数据正确")

    # 7. 列出所有定义
    print("\n所有寄存器定义:")
    for i, defn in enumerate(bank.list_definitions(), 1):
        has_parser = defn.parser is not None
        # 检查解析器映射
        mapped_parser = bank.get_parser(defn.address)

        print(f"  {i:2d}. {defn.name:15} (0x{defn.address:04x}): {defn.description}")
        print(f"      定义中解析器: {has_parser}, 映射中解析器: {mapped_parser is not None}")

    # 8. 清理
    if os.path.exists("test_register_defs.json"):
        os.remove("test_register_defs.json")
        print("\n清理测试文件: test_register_defs.json")

    print("\n所有测试通过！")

if __name__ == "__main__":
    test_load_json()