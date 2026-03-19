#!/usr/bin/env python3
from __future__ import annotations
"""
寄存器读写工具 - 支持向Linux服务器发送寄存器并获取32位返回值
提供可扩展的解析框架和数据存储功能

主要功能：
1. 支持多种寄存器访问方式（Socket、SSH、自定义协议等）
2. 灵活的解析框架，支持位域解析和自定义解析器
3. 完整的事务记录，包含时间戳、原始值和解析数据
4. 多种存储后端（JSON、CSV、SQLite）
5. 批量读写操作和统计分析

快速开始：
    from register_tool import MockRegisterAccess, RegisterBank, BitFieldParser

    # 创建模拟访问器
    access = MockRegisterAccess()
    bank = RegisterBank(access, "测试寄存器组")

    # 创建解析器
    parser = BitFieldParser({
        'enable': {'bits': (0, 0), 'description': '使能位'},
        'mode': {'bits': (1, 3), 'description': '模式选择'}
    })
    bank.set_parser(0x1000, parser)

    # 读写寄存器
    bank.write(0x1000, 0x0000000F)
    transaction = bank.read(0x1000)
    print(f"原始值: {transaction.get_hex_value()}")
    print(f"解析数据: {transaction.parsed_data}")

扩展指南：
1. 实现自定义访问器：继承RegisterAccess类，实现read_register和write_register方法
2. 实现自定义解析器：继承RegisterParser类，实现parse方法
3. 使用不同存储后端：JSONStorage、CSVStorage、SQLiteStorage
4. 批量操作：使用read_multiple和write_multiple方法
5. 寄存器定义管理：使用RegisterDefinition类定义寄存器元数据，使用register_definition()批量注册
6. JSON配置文件：使用export_definitions()导出定义，使用load_definitions_from_json()加载定义

注意：实际使用时需要根据服务器协议实现具体的RegisterAccess子类。
"""

import time
import json
import csv
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime
from enum import Enum


class AccessMode(Enum):
    """寄存器访问模式"""
    READ = "read"
    WRITE = "write"
    READ_WRITE = "read_write"


@dataclass
class RegisterTransaction:
    """
    单次寄存器事务记录
    包含寄存器地址、访问模式、原始值、时间戳和解析后的数据
    """
    address: int                     # 寄存器地址
    mode: AccessMode                # 访问模式
    raw_value: Optional[int] = None # 原始32位值（读取时有效）
    write_value: Optional[int] = None # 写入的值（写入时有效）
    timestamp: float = field(default_factory=time.time)  # 时间戳
    parsed_data: Dict[str, Any] = field(default_factory=dict)  # 解析后的数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，便于序列化"""
        data = asdict(self)
        data['mode'] = self.mode.value
        data['timestamp_iso'] = datetime.fromtimestamp(self.timestamp).isoformat()
        return data

    def get_hex_address(self) -> str:
        """获取十六进制格式的地址"""
        return f"0x{self.address:08x}"

    def get_hex_value(self) -> Optional[str]:
        """获取十六进制格式的值（读取时为raw_value，写入时为write_value）"""
        if self.mode == AccessMode.READ and self.raw_value is not None:
            return f"0x{self.raw_value:08x}"
        elif self.mode == AccessMode.WRITE and self.write_value is not None:
            return f"0x{self.write_value:08x}"
        elif self.mode == AccessMode.READ_WRITE:
            if self.raw_value is not None:
                return f"0x{self.raw_value:08x}"
        return None


@dataclass
class RegisterDefinition:
    """寄存器定义元数据"""
    address: int                    # 寄存器地址
    name: str                      # 寄存器名称
    description: str = ""          # 功能描述
    parser: Optional[RegisterParser] = None  # 专属解析器，None表示使用默认解析器

    def get_hex_address(self) -> str:
        """获取十六进制格式的地址"""
        return f"0x{self.address:08x}"


class RegisterAccess(ABC):
    """
    寄存器访问抽象基类
    子类需要实现具体的通信协议（如Socket、SSH、SPI、I2C等）
    """

    @abstractmethod
    def read_register(self, address: int) -> int:
        """
        读取32位寄存器值

        Args:
            address: 寄存器地址

        Returns:
            32位寄存器值
        """
        pass

    @abstractmethod
    def write_register(self, address: int, value: int) -> bool:
        """
        写入32位寄存器值

        Args:
            address: 寄存器地址
            value: 要写入的32位值

        Returns:
            写入是否成功
        """
        pass

    def read_multiple(self, addresses: List[int]) -> List[int]:
        """
        批量读取多个寄存器（默认实现为循环读取，可被子类优化）

        Args:
            addresses: 寄存器地址列表

        Returns:
            寄存器值列表
        """
        return [self.read_register(addr) for addr in addresses]

    def write_multiple(self, address_value_pairs: List[tuple]) -> List[bool]:
        """
        批量写入多个寄存器

        Args:
            address_value_pairs: [(地址1, 值1), (地址2, 值2), ...]

        Returns:
            写入成功状态列表
        """
        results = []
        for addr, val in address_value_pairs:
            results.append(self.write_register(addr, val))
        return results


class RegisterParser(ABC):
    """
    寄存器解析器抽象基类
    用户可以实现自定义解析逻辑
    """

    @abstractmethod
    def parse(self, raw_value: int, address: int = None) -> Dict[str, Any]:
        """
        解析原始寄存器值

        Args:
            raw_value: 原始32位值
            address: 寄存器地址（可选）

        Returns:
            解析后的字段字典，例如 {'field1': value1, 'field2': value2}
        """
        pass

    def get_description(self) -> str:
        """获取解析器描述"""
        return self.__class__.__name__


class BitFieldParser(RegisterParser):
    """
    位域解析器示例
    将32位值按位域解析为多个字段
    """

    def __init__(self, field_map: Dict[str, Dict[str, Any]]):
        """
        初始化位域解析器

        Args:
            field_map: 字段映射字典，格式为:
                {
                    'field_name': {
                        'bits': (start, end),  # 位范围，0-based
                        'description': '字段描述',
                        'enum': {0: '值0', 1: '值1'}  # 可选，枚举映射
                    },
                    ...
                }
        """
        self.field_map = field_map

    def parse(self, raw_value: int, address: int = None) -> Dict[str, Any]:
        result = {'raw_value': raw_value, 'raw_hex': f'0x{raw_value:08x}'}
        if address is not None:
            result['address'] = address
            result['address_hex'] = f'0x{address:08x}'

        for field_name, field_info in self.field_map.items():
            start_bit, end_bit = field_info['bits']
            bit_width = end_bit - start_bit + 1
            mask = (1 << bit_width) - 1
            field_value = (raw_value >> start_bit) & mask

            # 如果有枚举映射，转换为可读字符串
            if 'enum' in field_info and field_value in field_info['enum']:
                field_value_str = field_info['enum'][field_value]
                result[f'{field_name}_str'] = field_value_str

            result[field_name] = field_value
            result[f'{field_name}_bits'] = f'{start_bit}:{end_bit}'

        return result

    def get_description(self) -> str:
        return f"BitFieldParser with fields: {list(self.field_map.keys())}"


class RegisterBank:
    """
    寄存器组管理类
    管理寄存器访问、解析和数据记录
    """

    def __init__(self, access: RegisterAccess, name: str = "default"):
        """
        初始化寄存器组

        Args:
            access: 寄存器访问器实例
            name: 寄存器组名称
        """
        self.access = access
        self.name = name
        self.transactions: List[RegisterTransaction] = []
        self.parsers: Dict[int, RegisterParser] = {}  # 地址到解析器的映射
        self.default_parser: Optional[RegisterParser] = None

        # 新增：寄存器定义管理
        self._register_definitions: Dict[int, RegisterDefinition] = {}  # 地址到定义的映射
        self.register_by_name: Dict[str, RegisterDefinition] = {}      # 名称到定义的映射

    def set_parser(self, address: int, parser: RegisterParser):
        """
        为特定寄存器地址设置解析器

        Args:
            address: 寄存器地址
            parser: 解析器实例
        """
        self.parsers[address] = parser

    def set_default_parser(self, parser: RegisterParser):
        """设置默认解析器（用于没有特定解析器的寄存器）"""
        self.default_parser = parser

    def get_parser(self, address: int) -> Optional[RegisterParser]:
        """获取寄存器对应的解析器"""
        # 首先检查专属解析器
        if address in self.parsers:
            return self.parsers[address]

        # 其次检查寄存器定义中的解析器
        definition = self._register_definitions.get(address)
        if definition is not None and definition.parser is not None:
            return definition.parser

        # 最后使用默认解析器
        return self.default_parser

    def read(self, address: int, use_parser: bool = True) -> RegisterTransaction:
        """
        读取单个寄存器

        Args:
            address: 寄存器地址
            use_parser: 是否使用解析器解析返回值

        Returns:
            寄存器事务记录
        """
        raw_value = self.access.read_register(address)
        transaction = RegisterTransaction(
            address=address,
            mode=AccessMode.READ,
            raw_value=raw_value
        )

        if use_parser:
            self._parse_transaction(transaction)

        self.transactions.append(transaction)
        return transaction

    def write(self, address: int, value: int) -> RegisterTransaction:
        """
        写入单个寄存器

        Args:
            address: 寄存器地址
            value: 要写入的32位值

        Returns:
            寄存器事务记录
        """
        success = self.access.write_register(address, value)
        transaction = RegisterTransaction(
            address=address,
            mode=AccessMode.WRITE,
            write_value=value
        )
        # 可以添加success字段，但为了简化，假设总是成功
        self.transactions.append(transaction)
        return transaction

    def read_write(self, address: int, value: int, use_parser: bool = True) -> RegisterTransaction:
        """
        先写入再读取寄存器（用于验证写入）

        Args:
            address: 寄存器地址
            value: 要写入的32位值
            use_parser: 是否使用解析器解析返回值

        Returns:
            寄存器事务记录
        """
        self.access.write_register(address, value)
        raw_value = self.access.read_register(address)
        transaction = RegisterTransaction(
            address=address,
            mode=AccessMode.READ_WRITE,
            write_value=value,
            raw_value=raw_value
        )

        if use_parser:
            self._parse_transaction(transaction)

        self.transactions.append(transaction)
        return transaction

    def read_multiple(self, addresses: List[int], use_parser: bool = True) -> List[RegisterTransaction]:
        """
        批量读取多个寄存器

        Args:
            addresses: 寄存器地址列表
            use_parser: 是否使用解析器解析返回值

        Returns:
            寄存器事务记录列表
        """
        raw_values = self.access.read_multiple(addresses)
        transactions = []

        for addr, val in zip(addresses, raw_values):
            transaction = RegisterTransaction(
                address=addr,
                mode=AccessMode.READ,
                raw_value=val
            )

            if use_parser:
                self._parse_transaction(transaction)

            transactions.append(transaction)

        self.transactions.extend(transactions)
        return transactions

    def _parse_transaction(self, transaction: RegisterTransaction):
        """解析事务的原始值"""
        if transaction.raw_value is not None:
            parser = self.get_parser(transaction.address)
            if parser is not None:
                try:
                    transaction.parsed_data = parser.parse(
                        transaction.raw_value,
                        transaction.address
                    )
                except Exception as e:
                    transaction.parsed_data = {
                        'error': f'Parse failed: {str(e)}',
                        'raw_value': transaction.raw_value
                    }

    def get_transactions(self,
                         address: Optional[int] = None,
                         mode: Optional[AccessMode] = None) -> List[RegisterTransaction]:
        """获取事务记录，可按照地址和模式过滤"""
        filtered = self.transactions

        if address is not None:
            filtered = [t for t in filtered if t.address == address]

        if mode is not None:
            filtered = [t for t in filtered if t.mode == mode]

        return filtered

    def clear_transactions(self):
        """清除所有事务记录"""
        self.transactions.clear()

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.transactions:
            return {}

        read_count = sum(1 for t in self.transactions if t.mode == AccessMode.READ)
        write_count = sum(1 for t in self.transactions if t.mode == AccessMode.WRITE)
        read_write_count = sum(1 for t in self.transactions if t.mode == AccessMode.READ_WRITE)

        addresses = set(t.address for t in self.transactions)

        return {
            'total_transactions': len(self.transactions),
            'read_count': read_count,
            'write_count': write_count,
            'read_write_count': read_write_count,
            'unique_addresses': len(addresses),
            'addresses_hex': [f'0x{addr:08x}' for addr in sorted(addresses)],
            'first_timestamp': min(t.timestamp for t in self.transactions),
            'last_timestamp': max(t.timestamp for t in self.transactions)
        }

    def register_definition(self, definition: RegisterDefinition, overwrite: bool = False):
        """注册单个寄存器定义

        Args:
            definition: 寄存器定义
            overwrite: 是否允许覆盖已存在的定义（默认False）

        Raises:
            ValueError: 如果地址或名称已存在且不允许覆盖
        """
        # 验证地址唯一性
        if definition.address in self._register_definitions and not overwrite:
            existing = self._register_definitions[definition.address]
            raise ValueError(
                f"地址冲突: 地址 0x{definition.address:08x} 已被寄存器 '{existing.name}' 使用"
            )

        # 验证名称唯一性
        if definition.name in self.register_by_name and not overwrite:
            existing = self.register_by_name[definition.name]
            raise ValueError(
                f"名称冲突: 名称 '{definition.name}' 已被地址 0x{existing.address:08x} 使用"
            )

        self._register_definitions[definition.address] = definition
        self.register_by_name[definition.name] = definition

        # 如果定义了专属解析器，自动设置
        if definition.parser is not None:
            self.set_parser(definition.address, definition.parser)

        return True

    def register_definitions(self, definitions: List[RegisterDefinition], overwrite: bool = False):
        """批量注册寄存器定义

        Args:
            definitions: 寄存器定义列表
            overwrite: 是否允许覆盖已存在的定义（默认False）

        Returns:
            成功注册的数量
        """
        count = 0
        for definition in definitions:
            try:
                self.register_definition(definition, overwrite)
                count += 1
            except ValueError as e:
                # 可以选择记录警告或跳过
                print(f"警告: 跳过寄存器定义 '{definition.name}': {e}")
        return count

    def get_definition_by_name(self, name: str) -> Optional[RegisterDefinition]:
        """按名称获取寄存器定义"""
        return self.register_by_name.get(name)

    def get_definition_by_address(self, address: int) -> Optional[RegisterDefinition]:
        """按地址获取寄存器定义"""
        return self._register_definitions.get(address)

    def read_by_name(self, name: str, use_parser: bool = True) -> RegisterTransaction:
        """按名称读取寄存器"""
        definition = self.get_definition_by_name(name)
        if definition is None:
            raise ValueError(f"未找到寄存器定义: '{name}'")
        return self.read(definition.address, use_parser)

    def write_by_name(self, name: str, value: int) -> RegisterTransaction:
        """按名称写入寄存器"""
        definition = self.get_definition_by_name(name)
        if definition is None:
            raise ValueError(f"未找到寄存器定义: '{name}'")
        return self.write(definition.address, value)

    def export_definitions(self, filepath: str = None) -> Dict[str, Any]:
        """导出寄存器定义为字典或JSON文件

        Args:
            filepath: 可选，JSON文件路径。如果提供，将保存到文件

        Returns:
            寄存器定义字典
        """
        from datetime import datetime
        definitions_list = []
        for addr, defn in sorted(self._register_definitions.items()):
            def_dict = {
                "address": addr,
                "address_hex": f"0x{addr:08x}",
                "name": defn.name,
                "description": defn.description,
                "has_parser": defn.parser is not None,
                "parser_type": defn.parser.__class__.__name__ if defn.parser else None
            }
            definitions_list.append(def_dict)

        result = {
            "metadata": {
                "bank_name": self.name,
                "export_time": datetime.now().isoformat(),
                "total_definitions": len(self._register_definitions)
            },
            "definitions": definitions_list
        }

        if filepath:
            import json
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"寄存器定义已导出到: {filepath}")

        return result

    def list_definitions(self) -> List[RegisterDefinition]:
        """获取所有寄存器定义列表（按地址排序）"""
        return [self._register_definitions[addr] for addr in sorted(self._register_definitions.keys())]

    def get_summary(self) -> Dict[str, Any]:
        """获取寄存器定义摘要统计"""
        total = len(self._register_definitions)
        with_parser = sum(1 for d in self._register_definitions.values() if d.parser is not None)

        if self._register_definitions:
            min_addr = min(self._register_definitions.keys())
            max_addr = max(self._register_definitions.keys())
        else:
            min_addr = 0
            max_addr = 0

        return {
            "total_registers": total,
            "registers_with_parser": with_parser,
            "registers_without_parser": total - with_parser,
            "address_range": {
                "min": min_addr,
                "max": max_addr
            }
        }

    def load_definitions(self, data: Dict[str, Any], overwrite: bool = False,
                         parser_factory: Optional[Callable[[Dict[str, Any]], Optional[RegisterParser]]] = None) -> int:
        """从字典数据加载寄存器定义

        Args:
            data: 包含寄存器定义的字典数据，格式与export_definitions()输出相同
            overwrite: 是否允许覆盖已存在的定义（默认False）
            parser_factory: 可选，解析器工厂函数，接收定义字典，返回解析器实例或None

        Returns:
            成功加载的寄存器定义数量
        """
        if not isinstance(data, dict) or 'definitions' not in data:
            raise ValueError("无效的数据格式，应包含 'definitions' 字段")

        definitions = data.get('definitions', [])
        count = 0

        for def_dict in definitions:
            try:
                address = def_dict.get('address')
                name = def_dict.get('name')
                description = def_dict.get('description', '')

                if address is None or name is None:
                    print(f"警告: 跳过无效定义，缺少必要字段: {def_dict}")
                    continue

                # 创建解析器（如果提供工厂函数）
                parser = None
                if parser_factory is not None:
                    try:
                        parser = parser_factory(def_dict)
                    except Exception as e:
                        print(f"警告: 解析器工厂函数失败，定义 '{name}': {e}")
                        parser = None

                # 创建寄存器定义
                reg_def = RegisterDefinition(
                    address=address,
                    name=name,
                    description=description,
                    parser=parser
                )

                # 注册定义
                self.register_definition(reg_def, overwrite)
                count += 1

            except ValueError as e:
                print(f"警告: 跳过定义 '{def_dict.get('name', 'unknown')}': {e}")
            except Exception as e:
                print(f"警告: 处理定义时发生错误 '{def_dict.get('name', 'unknown')}': {e}")

        # 更新寄存器组名称（如果数据中有metadata）
        metadata = data.get('metadata', {})
        if metadata and 'bank_name' in metadata:
            self.name = metadata['bank_name']

        return count

    def load_definitions_from_json(self, filepath: str, overwrite: bool = False,
                                   parser_factory: Optional[Callable[[Dict[str, Any]], Optional[RegisterParser]]] = None) -> int:
        """从JSON文件加载寄存器定义

        Args:
            filepath: JSON文件路径
            overwrite: 是否允许覆盖已存在的定义（默认False）
            parser_factory: 可选，解析器工厂函数，接收定义字典，返回解析器实例或None

        Returns:
            成功加载的寄存器定义数量

        Raises:
            FileNotFoundError: 文件不存在
            json.JSONDecodeError: JSON格式错误
        """
        import json
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"文件不存在: {filepath}")
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"JSON格式错误: {e}", e.doc, e.pos)

        count = self.load_definitions(data, overwrite, parser_factory)
        print(f"从文件 {filepath} 加载了 {count} 个寄存器定义")
        return count


class StorageBackend(ABC):
    """存储后端抽象基类"""

    @abstractmethod
    def save_transaction(self, transaction: RegisterTransaction):
        """保存单个事务"""
        pass

    @abstractmethod
    def save_transactions(self, transactions: List[RegisterTransaction]):
        """批量保存事务"""
        pass

    @abstractmethod
    def load_transactions(self, **filters) -> List[Dict[str, Any]]:
        """加载事务（根据过滤条件）"""
        pass

    @abstractmethod
    def close(self):
        """关闭存储连接"""
        pass


class JSONStorage(StorageBackend):
    """JSON文件存储"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.transactions = []

        # 加载现有数据
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                self.transactions = data.get('transactions', [])
        except (FileNotFoundError, json.JSONDecodeError):
            self.transactions = []

    def save_transaction(self, transaction: RegisterTransaction):
        self.transactions.append(transaction.to_dict())
        self._flush()

    def save_transactions(self, transactions: List[RegisterTransaction]):
        self.transactions.extend(t.to_dict() for t in transactions)
        self._flush()

    def load_transactions(self, **filters) -> List[Dict[str, Any]]:
        filtered = self.transactions

        if 'address' in filters:
            filtered = [t for t in filtered if t.get('address') == filters['address']]

        if 'mode' in filters:
            filtered = [t for t in filtered if t.get('mode') == filters['mode']]

        if 'start_time' in filters:
            filtered = [t for t in filtered if t.get('timestamp', 0) >= filters['start_time']]

        if 'end_time' in filters:
            filtered = [t for t in filtered if t.get('timestamp', 0) <= filters['end_time']]

        return filtered

    def _flush(self):
        """将数据写入文件"""
        data = {
            'metadata': {
                'version': '1.0',
                'created': datetime.now().isoformat(),
                'transaction_count': len(self.transactions)
            },
            'transactions': self.transactions
        }

        with open(self.filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def close(self):
        self._flush()


class CSVStorage(StorageBackend):
    """CSV文件存储"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.fieldnames = [
            'timestamp', 'timestamp_iso', 'address', 'address_hex',
            'mode', 'raw_value', 'raw_value_hex', 'write_value', 'write_value_hex'
        ]

        # 初始化CSV文件
        try:
            with open(filepath, 'r') as f:
                pass  # 文件存在
        except FileNotFoundError:
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()

    def save_transaction(self, transaction: RegisterTransaction):
        self._save_transactions([transaction])

    def save_transactions(self, transactions: List[RegisterTransaction]):
        self._save_transactions(transactions)

    def _save_transactions(self, transactions: List[RegisterTransaction]):
        rows = []
        for t in transactions:
            row = {
                'timestamp': t.timestamp,
                'timestamp_iso': datetime.fromtimestamp(t.timestamp).isoformat(),
                'address': t.address,
                'address_hex': t.get_hex_address(),
                'mode': t.mode.value,
                'raw_value': t.raw_value if t.raw_value is not None else '',
                'raw_value_hex': f'0x{t.raw_value:08x}' if t.raw_value is not None else '',
                'write_value': t.write_value if t.write_value is not None else '',
                'write_value_hex': f'0x{t.write_value:08x}' if t.write_value is not None else ''
            }
            rows.append(row)

        with open(self.filepath, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writerows(rows)

    def load_transactions(self, **filters) -> List[Dict[str, Any]]:
        # 简化的加载实现
        # 实际应用中可能需要更高效的过滤
        transactions = []
        with open(self.filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 应用过滤条件
                if filters:
                    skip = False
                    if 'address' in filters and int(row['address']) != filters['address']:
                        skip = True
                    if 'mode' in filters and row['mode'] != filters['mode']:
                        skip = True
                    if skip:
                        continue
                transactions.append(row)

        return transactions

    def close(self):
        pass  # CSV文件在每次写入时都会刷新


class SQLiteStorage(StorageBackend):
    """SQLite数据库存储"""

    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS register_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                timestamp_iso TEXT NOT NULL,
                address INTEGER NOT NULL,
                address_hex TEXT NOT NULL,
                mode TEXT NOT NULL,
                raw_value INTEGER,
                raw_value_hex TEXT,
                write_value INTEGER,
                write_value_hex TEXT,
                parsed_data TEXT  -- JSON格式的解析数据
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_address ON register_transactions (address)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp ON register_transactions (timestamp)
        ''')

        self.conn.commit()

    def save_transaction(self, transaction: RegisterTransaction):
        self.save_transactions([transaction])

    def save_transactions(self, transactions: List[RegisterTransaction]):
        cursor = self.conn.cursor()

        for t in transactions:
            parsed_json = json.dumps(t.parsed_data) if t.parsed_data else ''

            cursor.execute('''
                INSERT INTO register_transactions
                (timestamp, timestamp_iso, address, address_hex, mode,
                 raw_value, raw_value_hex, write_value, write_value_hex, parsed_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                t.timestamp,
                datetime.fromtimestamp(t.timestamp).isoformat(),
                t.address,
                t.get_hex_address(),
                t.mode.value,
                t.raw_value,
                f'0x{t.raw_value:08x}' if t.raw_value is not None else '',
                t.write_value,
                f'0x{t.write_value:08x}' if t.write_value is not None else '',
                parsed_json
            ))

        self.conn.commit()

    def load_transactions(self, **filters) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()

        query = 'SELECT * FROM register_transactions WHERE 1=1'
        params = []

        if 'address' in filters:
            query += ' AND address = ?'
            params.append(filters['address'])

        if 'mode' in filters:
            query += ' AND mode = ?'
            params.append(filters['mode'])

        if 'start_time' in filters:
            query += ' AND timestamp >= ?'
            params.append(filters['start_time'])

        if 'end_time' in filters:
            query += ' AND timestamp <= ?'
            params.append(filters['end_time'])

        cursor.execute(query, params)
        columns = [col[0] for col in cursor.description]

        transactions = []
        for row in cursor.fetchall():
            transaction = dict(zip(columns, row))
            # 解析JSON字段
            if transaction.get('parsed_data'):
                try:
                    transaction['parsed_data'] = json.loads(transaction['parsed_data'])
                except json.JSONDecodeError:
                    pass
            transactions.append(transaction)

        return transactions

    def close(self):
        self.conn.close()


# 示例实现：模拟寄存器访问器（用于测试）
class MockRegisterAccess(RegisterAccess):
    """模拟寄存器访问器，用于测试"""

    def __init__(self):
        self.registers: Dict[int, int] = {}

    def read_register(self, address: int) -> int:
        return self.registers.get(address, 0x00000000)

    def write_register(self, address: int, value: int) -> bool:
        self.registers[address] = value & 0xFFFFFFFF
        return True


# 示例实现：Socket寄存器访问器（需要服务器端配合）
class SocketRegisterAccess(RegisterAccess):
    """
    通过SSH隧道和Telnet访问寄存器
    先通过SSH连接远程主机，再通过Telnet localhost连接到5040或5050端口
    发送devmem命令读取寄存器，支持多行响应解析

    示例：
        # 基本用法
        access = SocketRegisterAccess(
            ssh_host="remote-server",
            ssh_username="root",
            telnet_port=5040
        )
        value = access.read_register(0x1000)
        print(f"寄存器值: 0x{value:08x}")
        access.close()

        # 调试模式，查看详细通信信息
        access = SocketRegisterAccess(
            ssh_host="remote-server",
            ssh_username="root",
            telnet_port=5040,
            debug=True,
            use_32_param=False  # 如果服务器不需要"32"参数
        )
        value = access.read_register(0x20202000461)
        print(f"寄存器值: 0x{value:08x}")
        access.close()
    """

    def __init__(self, ssh_host: str, ssh_username: str = 'root', ssh_key_path: str = None,
                 telnet_port: int = 5040, local_bind_port: int = 0, timeout: float = 20.0,
                 debug: bool = False, use_32_param: bool = True):
        """
        初始化SSH Telnet寄存器访问器

        Args:
            ssh_host: SSH主机地址
            ssh_username: SSH用户名，默认为root
            ssh_key_path: SSH私钥路径，可选
            telnet_port: Telnet端口，默认为5040，也可以是5050
            local_bind_port: 本地绑定端口，默认为0（系统分配）
            timeout: 超时时间，默认为20秒
            debug: 是否启用调试模式，打印详细通信信息
            use_32_param: 是否在devmem命令中添加"32"参数
        """
        self.ssh_host = ssh_host
        self.ssh_username = ssh_username
        self.ssh_key_path = ssh_key_path
        self.telnet_port = telnet_port
        self.local_bind_port = local_bind_port
        self.timeout = timeout
        self.debug = debug
        self.use_32_param = use_32_param

        self.ssh_client = None
        self.forwarded_port = None
        self.socket = None

        # 检查paramiko是否可用
        try:
            import paramiko
            self._paramiko_available = True
        except ImportError:
            self._paramiko_available = False
            raise ImportError(
                "paramiko库未安装，请使用 'pip install paramiko' 安装。"
                "此访问器需要通过SSH隧道连接。"
            )

    def _setup_ssh_tunnel(self):
        """建立SSH隧道，将本地端口转发到远程主机的Telnet端口"""
        if self.ssh_client is not None:
            return

        import paramiko

        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            if self.ssh_key_path:
                # 使用密钥认证
                self.ssh_client.connect(
                    self.ssh_host,
                    username=self.ssh_username,
                    key_filename=self.ssh_key_path,
                    timeout=10.0
                )
            else:
                # 使用密码认证（假设通过SSH代理或免密登录）
                self.ssh_client.connect(
                    self.ssh_host,
                    username=self.ssh_username,
                    timeout=10.0
                )

            # 创建本地端口转发：将本地端口转发到远程主机的localhost:telnet_port
            transport = self.ssh_client.get_transport()
            # 绑定到本地端口，转发到远程主机的localhost
            self.forwarded_port = transport.request_port_forward(
                '',  # 绑定到所有接口
                self.local_bind_port,
                'localhost',
                self.telnet_port
            )

        except Exception as e:
            self.ssh_client = None
            raise ConnectionError(f"SSH隧道建立失败: {e}")

    def _connect(self):
        """建立Socket连接（通过SSH隧道）"""
        if self.socket is not None:
            return

        # 首先建立SSH隧道
        self._setup_ssh_tunnel()

        import socket

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(self.timeout)

        try:
            # 连接到本地转发端口
            self.socket.connect(('localhost', self.forwarded_port))
        except Exception as e:
            self.socket = None
            raise ConnectionError(f"连接到SSH隧道失败: {e}")

    def read_register(self, address: int) -> int:
        """读取寄存器：发送devmem命令并解析多行响应"""
        import socket
        import time
        import re

        self._connect()
        try:
            # 在发送命令前，先读取并丢弃可能存在的欢迎消息
            # 设置短超时以读取现有数据
            original_timeout = self.socket.gettimeout()
            self.socket.settimeout(1.0)  # 短超时读取欢迎消息

            welcome_data = b""
            try:
                while True:
                    try:
                        chunk = self.socket.recv(1024)
                        if chunk:
                            welcome_data += chunk
                        else:
                            break
                    except socket.timeout:
                        # 超时表示没有更多欢迎数据
                        break
            except (socket.error, OSError) as e:
                # 忽略读取欢迎消息时的网络异常
                if self.debug:
                    print(f"[DEBUG] 读取欢迎消息时出错: {e}")
            except Exception as e:
                # 其他异常，打印调试信息但不中断
                if self.debug:
                    print(f"[DEBUG] 读取欢迎消息时出现意外错误: {e}")

            if self.debug and welcome_data:
                print(f"[DEBUG] 欢迎消息: {welcome_data.decode('utf-8', errors='ignore')}")

            # 恢复原始超时设置
            self.socket.settimeout(original_timeout)

            # 构建devmem命令
            if self.use_32_param:
                cmd = f"devmem 0x{address:x} 32\n"
            else:
                cmd = f"devmem 0x{address:x}\n"

            if self.debug:
                print(f"[DEBUG] 发送命令: {cmd.strip()}")

            self.socket.sendall(cmd.encode('utf-8'))

            # 接收响应
            response = b""
            start_time = time.time()
            last_receive_time = start_time

            while time.time() - start_time < self.timeout:
                try:
                    # 尝试接收数据
                    self.socket.settimeout(0.5)  # 使用较短超时进行轮询
                    chunk = self.socket.recv(4096)
                    if chunk:
                        response += chunk
                        last_receive_time = time.time()
                        if self.debug:
                            print(f"[DEBUG] 收到 {len(chunk)} 字节: {chunk[:100]}...")

                        # 检查是否可能收到完整响应
                        # 如果响应中包含换行和可能的提示符，可以认为响应基本完整
                        if b'\n' in chunk and time.time() - last_receive_time > 0.2:
                            # 短暂等待看看是否有更多数据
                            time.sleep(0.1)
                            continue
                    else:
                        # 接收到空数据，连接可能已关闭
                        break

                except socket.timeout:
                    # 接收超时，检查是否已收到足够数据
                    if response and time.time() - last_receive_time > 0.5:
                        # 超过0.5秒没有新数据，认为响应已完整
                        break
                    continue
                except BlockingIOError:
                    # 无数据可读
                    pass
                except ConnectionError:
                    # 连接错误，退出循环
                    break

                time.sleep(0.01)

            if self.debug:
                print(f"[DEBUG] 总响应大小: {len(response)} 字节")

            response_str = response.decode('utf-8', errors='ignore')

            if self.debug:
                print(f"[DEBUG] 响应文本:\n{response_str}")
                print(f"[DEBUG] 响应原始字节 (hex): {response.hex()[:200]}...")

            # 按行分割响应，移除空行
            lines = [line.strip() for line in response_str.split('\n') if line.strip()]

            if self.debug:
                print(f"[DEBUG] 解析后行数: {len(lines)}")
                for i, line in enumerate(lines):
                    print(f"[DEBUG]  行 {i}: '{line}'")

            # 方法1：寻找以"0x"开头的行（寄存器值）
            hex_lines = [line for line in lines if line.lower().startswith('0x')]

            if hex_lines:
                # 取最后一个十六进制值（最新的响应）
                hex_value = hex_lines[-1]
                if self.debug:
                    print(f"[DEBUG] 找到十六进制值: {hex_value}")
                try:
                    value = int(hex_value, 16)
                    if self.debug:
                        print(f"[DEBUG] 解析为整数: 0x{value:08x} ({value})")
                    return value
                except ValueError as ve:
                    raise ValueError(f"无法解析十六进制值 '{hex_value}': {ve}")

            # 方法2：查找包含十六进制数字的行（可能没有0x前缀）
            for line in reversed(lines):  # 从最后一行开始搜索
                # 查找类似十六进制数字的模式（支持0x前缀或无前缀）
                # 匹配格式：0x后跟1-8位十六进制数，或单独的1-8位十六进制数
                hex_match = re.search(r'(0x[0-9a-fA-F]{1,8}|[0-9a-fA-F]{1,8})', line)
                if hex_match:
                    hex_str = hex_match.group(0)
                    if self.debug:
                        print(f"[DEBUG] 正则匹配到十六进制: '{hex_str}' 在行: '{line}'")
                    try:
                        # 如果字符串以0x开头，直接解析
                        if hex_str.lower().startswith('0x'):
                            value = int(hex_str, 16)
                        else:
                            # 否则假设是十六进制数字（无前缀）
                            value = int(hex_str, 16)

                        if self.debug:
                            print(f"[DEBUG] 解析为整数: 0x{value:08x} ({value})")
                        return value
                    except ValueError:
                        # 解析失败，继续搜索
                        if self.debug:
                            print(f"[DEBUG] 解析失败，继续搜索")
                        continue

            # 方法3：在整段响应中搜索十六进制模式
            hex_match = re.search(r'0x[0-9a-fA-F]{1,8}', response_str)
            if hex_match:
                hex_str = hex_match.group(0)
                if self.debug:
                    print(f"[DEBUG] 全文搜索找到十六进制: {hex_str}")
                return int(hex_str, 16)

            # 方法4：搜索无前缀的十六进制数字（至少1位）
            hex_match = re.search(r'[0-9a-fA-F]{1,8}', response_str)
            if hex_match:
                hex_str = hex_match.group(0)
                if self.debug:
                    print(f"[DEBUG] 全文搜索找到无前缀十六进制: {hex_str}")
                try:
                    return int(hex_str, 16)
                except ValueError:
                    pass

            # 没有找到有效的寄存器值
            error_msg = (
                f"无法从响应中提取寄存器值。\n"
                f"命令: {cmd.strip()}\n"
                f"响应内容 ({len(response)} 字节):\n{response_str}\n"
                f"响应字节 (hex): {response.hex()[:500]}..."
            )
            if self.debug:
                print(f"[ERROR] {error_msg}")
            raise ValueError(error_msg)

        except socket.timeout:
            raise TimeoutError(f"读取寄存器超时（{self.timeout}秒）")
        except ValueError as ve:
            # 重新抛出ValueError
            raise ve
        except (socket.error, OSError, ConnectionError, UnicodeDecodeError) as e:
            raise ConnectionError(f"读取寄存器失败: {e}")
        except Exception as e:
            # 捕获其他未预料到的异常
            raise ConnectionError(f"读取寄存器时发生意外错误: {e}")

    def write_register(self, address: int, value: int) -> bool:
        """写入寄存器：不支持写入操作，返回True以满足接口要求"""
        # 根据用户要求，不需要支持写入寄存器
        # 直接返回True表示操作成功
        return True

    def close(self):
        """关闭连接和SSH隧道"""
        if self.socket:
            self.socket.close()
            self.socket = None

        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None
            self.forwarded_port = None


# 示例实现：SSH寄存器访问器（通过devmem命令）
class SSHRegisterAccess(RegisterAccess):
    """
    通过SSH执行devmem命令访问寄存器
    需要服务器已安装devmem工具，并且SSH密钥已配置
    """

    def __init__(self, host: str, username: str = 'root', key_path: str = None):
        self.host = host
        self.username = username
        self.key_path = key_path

    def _execute_command(self, command: str) -> str:
        """执行SSH命令"""
        import subprocess
        ssh_cmd = ['ssh', f'{self.username}@{self.host}']
        if self.key_path:
            ssh_cmd.extend(['-i', self.key_path])
        ssh_cmd.append(command)

        try:
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise RuntimeError(f"SSH command failed: {result.stderr}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise TimeoutError("SSH command timeout")
        except Exception as e:
            raise ConnectionError(f"SSH execution failed: {e}")

    def read_register(self, address: int) -> int:
        """读取寄存器：使用devmem读取32位值"""
        cmd = f"devmem 0x{address:08x} 32"
        output = self._execute_command(cmd)
        # 输出格式：0x12345678
        if output.startswith('0x'):
            return int(output, 16)
        else:
            raise ValueError(f"Invalid devmem output: {output}")

    def write_register(self, address: int, value: int) -> bool:
        """写入寄存器：使用devmem写入32位值"""
        cmd = f"devmem 0x{address:08x} 32 0x{value:08x}"
        output = self._execute_command(cmd)
        # devmem写入成功通常无输出或输出写入的值
        return True

    def read_multiple(self, addresses: List[int]) -> List[int]:
        """批量读取（优化：通过单次SSH执行多个命令）"""
        # 构建组合命令
        commands = []
        for addr in addresses:
            commands.append(f"devmem 0x{addr:08x} 32")
        combined_cmd = " && ".join(commands)

        output = self._execute_command(combined_cmd)
        lines = output.split('\n')

        values = []
        for line in lines:
            if line.startswith('0x'):
                values.append(int(line, 16))
            else:
                values.append(0)

        return values


# 示例使用
if __name__ == "__main__":
    print("=== 寄存器工具示例 ===")

    # 1. 创建模拟访问器
    access = MockRegisterAccess()

    # 2. 创建寄存器组
    bank = RegisterBank(access, "测试寄存器组")

    # 3. 创建位域解析器
    control_reg_parser = BitFieldParser({
        'enable': {'bits': (0, 0), 'description': '使能位'},
        'mode': {'bits': (1, 3), 'description': '模式选择',
                 'enum': {0: '模式0', 1: '模式1', 2: '模式2'}},
        'clock_div': {'bits': (4, 7), 'description': '时钟分频'},
        'status': {'bits': (8, 10), 'description': '状态位'}
    })

    bank.set_parser(0x1000, control_reg_parser)

    # 4. 执行一些操作
    print("\n1. 写入寄存器 0x1000 = 0x0000000F")
    bank.write(0x1000, 0x0000000F)

    print("2. 读取寄存器 0x1000")
    transaction = bank.read(0x1000)
    print(f"   原始值: {transaction.get_hex_value()}")
    print(f"   解析数据: {transaction.parsed_data}")

    print("3. 批量读取寄存器")
    transactions = bank.read_multiple([0x1000, 0x2000, 0x3000])
    for t in transactions:
        print(f"   地址 {t.get_hex_address()}: {t.get_hex_value()}")

    # 5. 统计信息
    stats = bank.get_statistics()
    print(f"\n统计信息:")
    for key, value in stats.items():
        print(f"   {key}: {value}")

    # 6. 保存到JSON
    print("\n保存数据到JSON文件...")
    storage = JSONStorage("register_data.json")
    storage.save_transactions(bank.transactions)
    storage.close()

    # 7. 使用新功能的示例
    print("\n=== 使用寄存器定义功能 ===")

    # 创建寄存器定义
    reg_defs = [
        RegisterDefinition(
            address=0x1000,
            name="control_register",
            description="控制寄存器",
            parser=control_reg_parser
        ),
        RegisterDefinition(
            address=0x2000,
            name="status_register",
            description="状态寄存器",
            parser=None  # 使用默认解析器
        ),
        RegisterDefinition(
            address=0x3000,
            name="config_register",
            description="配置寄存器",
            parser=BitFieldParser({
                'mode': {'bits': (0, 2), 'description': '工作模式'},
                'enable': {'bits': (3, 3), 'description': '使能标志'}
            })
        )
    ]

    # 批量注册
    registered_count = bank.register_definitions(reg_defs)
    print(f"成功注册 {registered_count} 个寄存器定义")

    # 按名称访问
    try:
        transaction = bank.read_by_name("control_register")
        print(f"按名称读取 control_register: {transaction.get_hex_value()}")
    except ValueError as e:
        print(f"错误: {e}")

    # 导出定义
    summary = bank.get_summary()
    print(f"\n寄存器摘要: {summary}")

    # 导出到JSON文件
    export_data = bank.export_definitions("register_definitions.json")
    print(f"导出 {export_data['metadata']['total_definitions']} 个寄存器定义")

    # 列出所有定义
    print("\n所有寄存器定义:")
    for i, defn in enumerate(bank.list_definitions(), 1):
        parser_info = "有专属解析器" if defn.parser else "使用默认解析器"
        print(f"  {i:2d}. {defn.name:20} (0x{defn.address:08x}): {defn.description} - {parser_info}")

    # 测试定义验证
    print("\n=== 测试定义验证 ===")
    try:
        # 尝试注册重复地址
        duplicate_def = RegisterDefinition(
            address=0x1000,
            name="duplicate_register",
            description="重复地址的寄存器"
        )
        bank.register_definition(duplicate_def)
        print("错误: 应该检测到地址冲突")
    except ValueError as e:
        print(f"正确检测到地址冲突: {e}")

    try:
        # 尝试注册重复名称
        duplicate_name_def = RegisterDefinition(
            address=0x4000,
            name="control_register",  # 重复名称
            description="重复名称的寄存器"
        )
        bank.register_definition(duplicate_name_def)
        print("错误: 应该检测到名称冲突")
    except ValueError as e:
        print(f"正确检测到名称冲突: {e}")

    # 8. 演示从JSON文件加载寄存器定义
    print("\n=== 演示从JSON文件加载寄存器定义 ===")

    # 创建一个新的寄存器组来演示加载
    new_bank = RegisterBank(access, "从JSON加载的寄存器组")

    # 定义简单的解析器工厂函数
    def simple_parser_factory(def_dict: Dict[str, Any]) -> Optional[RegisterParser]:
        """根据定义信息创建解析器（示例工厂函数）"""
        parser_type = def_dict.get('parser_type')
        name = def_dict.get('name', 'unknown')
        _address = def_dict.get('address', 0)  # 可能用于更复杂的工厂函数

        if parser_type == 'BitFieldParser':
            # 根据寄存器名称和地址创建不同的解析器
            if name == 'control_register':
                return BitFieldParser({
                    'enable': {'bits': (0, 0), 'description': '使能位'},
                    'mode': {'bits': (1, 3), 'description': '模式选择'}
                })
            elif name == 'config_register':
                return BitFieldParser({
                    'mode': {'bits': (0, 2), 'description': '工作模式'},
                    'enable': {'bits': (3, 3), 'description': '使能标志'}
                })
        # 对于没有解析器或未知类型的返回None
        return None

    try:
        # 从之前导出的文件加载
        loaded_count = new_bank.load_definitions_from_json(
            "register_definitions.json",
            overwrite=True,
            parser_factory=simple_parser_factory
        )
        print(f"成功从JSON文件加载了 {loaded_count} 个寄存器定义")

        # 显示加载的定义
        print(f"\n加载后的寄存器组: {new_bank.name}")
        print("所有寄存器定义:")
        for i, defn in enumerate(new_bank.list_definitions(), 1):
            parser_info = "有专属解析器" if defn.parser else "使用默认解析器"
            print(f"  {i:2d}. {defn.name:20} (0x{defn.address:08x}): {defn.description} - {parser_info}")

        # 测试按名称访问加载的定义
        print("\n测试按名称访问:")
        try:
            # 读取一个寄存器
            transaction = new_bank.read_by_name("control_register")
            print(f"  读取 control_register: {transaction.get_hex_value()}")
            if transaction.parsed_data:
                print(f"    解析数据: {transaction.parsed_data}")
        except ValueError as e:
            print(f"  错误: {e}")

    except FileNotFoundError as e:
        print(f"错误: 文件未找到 - {e}")
    except Exception as e:
        print(f"加载过程中发生错误: {e}")

    # 9. 演示直接加载字典数据
    print("\n=== 演示直接加载字典数据 ===")

    # 创建示例数据
    example_data = {
        "metadata": {
            "bank_name": "示例寄存器组",
            "export_time": "2026-03-18T12:00:00",
            "total_definitions": 2
        },
        "definitions": [
            {
                "address": 0x5000,
                "address_hex": "0x00005000",
                "name": "example_reg1",
                "description": "示例寄存器1",
                "has_parser": True,
                "parser_type": "BitFieldParser"
            },
            {
                "address": 0x6000,
                "address_hex": "0x00006000",
                "name": "example_reg2",
                "description": "示例寄存器2",
                "has_parser": False,
                "parser_type": None
            }
        ]
    }

    # 创建一个新的寄存器组
    example_bank = RegisterBank(access, "初始名称")

    # 加载数据（不使用解析器工厂）
    loaded_count = example_bank.load_definitions(example_data, overwrite=True)
    print(f"从字典数据加载了 {loaded_count} 个寄存器定义")
    print(f"寄存器组名称已更新为: {example_bank.name}")

    # 显示定义
    for i, defn in enumerate(example_bank.list_definitions(), 1):
        parser_info = "有专属解析器" if defn.parser else "使用默认解析器"
        print(f"  {i:2d}. {defn.name:20} (0x{defn.address:08x}): {defn.description} - {parser_info}")

    print("示例完成！")