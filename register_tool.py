#!/usr/bin/env python3
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
        return self.parsers.get(address, self.default_parser)

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
    通过TCP Socket访问寄存器
    假设服务器协议：发送4字节地址（大端序），接收4字节值（大端序）
    """

    def __init__(self, host: str = 'localhost', port: int = 8888):
        self.host = host
        self.port = port
        self.socket = None

    def _connect(self):
        """建立Socket连接"""
        import socket
        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.socket.settimeout(5.0)

    def read_register(self, address: int) -> int:
        """读取寄存器"""
        self._connect()
        try:
            # 发送4字节地址（大端序）
            data = address.to_bytes(4, byteorder='big')
            self.socket.sendall(data)
            # 接收4字节返回值（大端序）
            response = self.socket.recv(4)
            if len(response) != 4:
                raise ValueError(f"Invalid response length: {len(response)}")
            return int.from_bytes(response, byteorder='big')
        except Exception as e:
            raise ConnectionError(f"Socket read failed: {e}")

    def write_register(self, address: int, value: int) -> bool:
        """写入寄存器（假设协议：发送8字节，前4字节地址，后4字节值）"""
        self._connect()
        try:
            data = address.to_bytes(4, byteorder='big') + value.to_bytes(4, byteorder='big')
            self.socket.sendall(data)
            # 假设服务器返回1字节成功标志
            response = self.socket.recv(1)
            return len(response) == 1 and response[0] == 1
        except Exception as e:
            raise ConnectionError(f"Socket write failed: {e}")

    def close(self):
        """关闭连接"""
        if self.socket:
            self.socket.close()
            self.socket = None


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

    print("示例完成！")