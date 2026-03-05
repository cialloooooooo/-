#!/usr/bin/env python3
"""
Telnet寄存器管理器 - 通过Telnet连接Linux服务器，查询固定寄存器组

主要功能：
1. 通过Telnet连接服务器，发送寄存器查询命令
2. 管理固定寄存器组，通过名称访问
3. 可扩展的解析器系统，支持不同寄存器的不同解析规则
4. 保存查询结果（寄存器名、地址、返回值、解析结果）
5. 支持先获取原始值，后执行解析的流程

设计理念：
- 寄存器定义与解析器分离，便于扩展
- 解析结果动态写入寄存器对象
- 支持多种输出格式（字典、JSON）
- 清晰的错误处理

使用示例：
    from telnet_register_manager import TelnetRegisterAccess, Register, RegisterSet

    # 1. 创建Telnet连接
    access = TelnetRegisterAccess(host='192.168.1.100', username='root', password='password')

    # 2. 创建寄存器对象
    reg_ctrl = Register(name='CTRL', address=0x1000, description='控制寄存器')
    reg_status = Register(name='STATUS', address=0x1004, description='状态寄存器')

    # 3. 创建寄存器组
    regset = RegisterSet(access)
    regset.add_register(reg_ctrl)
    regset.add_register(reg_status)

    # 4. 定义解析器
    def ctrl_parser(raw_value):
        return {
            'enable': (raw_value >> 0) & 0x1,
            'mode': (raw_value >> 1) & 0x7,
            'clock_div': (raw_value >> 4) & 0xF
        }

    reg_ctrl.set_parser(ctrl_parser)

    # 5. 批量读取
    regset.read_all()

    # 6. 执行解析
    regset.parse_all()

    # 7. 查看结果
    for reg in regset.registers:
        print(f"{reg.name}: 值=0x{reg.value:08x}, 解析={reg.parsed_result}")

    # 8. 保存结果
    regset.save_to_json('results.json')
"""

import json
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from abc import ABC, abstractmethod

# 尝试导入telnetlib，如果失败则提供模拟版本
try:
    import telnetlib
    TELNETLIB_AVAILABLE = True
except ImportError:
    TELNETLIB_AVAILABLE = False
    print("警告: telnetlib模块不可用，TelnetRegisterAccess将使用模拟模式")

    # 创建模拟的telnetlib模块
    class MockTelnet:
        def __init__(self, host, port, timeout):
            self.host = host
            self.port = port
            self.timeout = timeout
            self.closed = False

        def read_until(self, expected, timeout=None):
            return b"mock login success # "

        def expect(self, list_of_regexps, timeout=None):
            return (0, None, b"login: ")

        def write(self, data):
            pass

        def read_very_eager(self):
            return b"mock output"

        def close(self):
            self.closed = True

    # 创建模拟的telnetlib模块
    class MockTelnetlib:
        def Telnet(self, host, port, timeout):
            return MockTelnet(host, port, timeout)

    telnetlib = MockTelnetlib()


# ============================================================================
# 基础异常类
# ============================================================================

class RegisterError(Exception):
    """寄存器相关异常的基类"""
    pass


class ConnectionError(RegisterError):
    """连接相关异常"""
    pass


class ParseError(RegisterError):
    """解析相关异常"""
    pass


# ============================================================================
# 寄存器类
# ============================================================================

@dataclass
class Register:
    """
    寄存器类 - 存储寄存器信息和查询结果

    属性：
    - name: 寄存器名称（唯一标识）
    - address: 寄存器地址
    - description: 寄存器描述
    - value: 读取到的原始值（32位整数）
    - parsed_result: 解析结果（字典或字符串）
    - parser: 解析函数
    - last_read_time: 最后读取时间
    - error: 错误信息（如果有）
    """

    name: str
    address: int
    description: str = ""
    value: Optional[int] = None
    parsed_result: Any = ""  # 初始为空字符串，解析后可为字典或字符串
    parser: Optional[Callable[[int], Any]] = None
    last_read_time: Optional[float] = None
    error: Optional[str] = None

    def get_hex_address(self) -> str:
        """获取十六进制格式的地址"""
        return f"0x{self.address:08x}"

    def get_hex_value(self) -> Optional[str]:
        """获取十六进制格式的值"""
        if self.value is not None:
            return f"0x{self.value:08x}"
        return None

    def set_parser(self, parser_func: Callable[[int], Any]):
        """设置解析函数"""
        self.parser = parser_func

    def parse(self) -> bool:
        """
        执行解析

        Returns:
            bool: 解析是否成功
        """
        if self.value is None:
            self.error = "无可解析的值（value为None）"
            return False

        if self.parser is None:
            # 如果没有解析器，将原始值作为结果
            self.parsed_result = {"raw_value": self.value, "raw_hex": self.get_hex_value()}
            return True

        try:
            self.parsed_result = self.parser(self.value)
            return True
        except Exception as e:
            self.error = f"解析失败: {str(e)}"
            self.parsed_result = {"error": str(e), "raw_value": self.value}
            return False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，便于序列化"""
        result = asdict(self)

        # 处理不可JSON序列化的字段
        if callable(result.get('parser')):
            result['parser'] = result['parser'].__name__ if hasattr(result['parser'], '__name__') else 'callable'

        # 添加十六进制表示
        result['hex_address'] = self.get_hex_address()
        result['hex_value'] = self.get_hex_value()

        # 时间戳格式化
        if result['last_read_time']:
            result['last_read_time_iso'] = datetime.fromtimestamp(result['last_read_time']).isoformat()

        return result

    def __str__(self) -> str:
        """字符串表示"""
        value_str = self.get_hex_value() if self.value is not None else "None"
        return f"Register(name={self.name}, address={self.get_hex_address()}, value={value_str})"


# ============================================================================
# 寄存器访问接口
# ============================================================================

class RegisterAccess(ABC):
    """寄存器访问抽象基类"""

    @abstractmethod
    def read_register(self, address: int) -> int:
        """读取寄存器值"""
        pass

    @abstractmethod
    def write_register(self, address: int, value: int) -> bool:
        """写入寄存器值"""
        pass

    def close(self):
        """关闭连接（可选）"""
        pass


class TelnetRegisterAccess(RegisterAccess):
    """
    通过Telnet连接访问寄存器

    协议假设：
    1. 连接到Telnet服务器
    2. 登录（如果需要）
    3. 发送命令读取寄存器（如：read_reg 0x1000）
    4. 解析命令输出获取寄存器值

    注意：实际命令格式需要根据服务器调整
    """

    def __init__(self, host: str, port: int = 23,
                 username: str = None, password: str = None,
                 timeout: float = 10.0,
                 read_command: str = "read_reg {address:08x}",
                 write_command: str = "write_reg {address:08x} {value:08x}",
                 prompt: str = "# "):
        """
        初始化Telnet连接

        Args:
            host: 服务器地址
            port: Telnet端口，默认23
            username: 用户名
            password: 密码
            timeout: 超时时间（秒）
            read_command: 读取命令模板，{address:08x}将被替换为十六进制地址
            write_command: 写入命令模板，{address:08x}和{value:08x}将被替换
            prompt: 命令提示符，用于等待命令完成
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.read_command = read_command
        self.write_command = write_command
        self.prompt = prompt

        self.tn = None
        self._connected = False

    def _connect(self):
        """建立Telnet连接并登录"""
        if self._connected and self.tn:
            return

        try:
            print(f"正在连接到 {self.host}:{self.port}...")
            self.tn = telnetlib.Telnet(self.host, self.port, timeout=self.timeout)

            # 如果需要登录
            if self.username:
                # 等待用户名提示（常见提示符：login:, username:等）
                login_prompt = b"login: "
                username_prompt = b"username: "
                login_or_username = b"ogin: "  # 匹配login或username

                # 尝试读取直到看到登录提示
                index, _, _ = self.tn.expect([login_prompt, username_prompt, login_or_username], timeout=self.timeout)
                self.tn.write(self.username.encode('ascii') + b"\n")

                if self.password:
                    # 等待密码提示
                    self.tn.read_until(b"Password: ", timeout=self.timeout)
                    self.tn.write(self.password.encode('ascii') + b"\n")

            # 等待命令提示符，表示登录成功
            if self.prompt:
                self.tn.read_until(self.prompt.encode('ascii'), timeout=self.timeout)

            self._connected = True
            print(f"已连接到 {self.host}:{self.port}")

        except Exception as e:
            raise ConnectionError(f"Telnet连接失败: {e}")

    def _send_command(self, command: str) -> str:
        """
        发送命令并获取输出

        Args:
            command: 要发送的命令

        Returns:
            命令输出（去除命令回显和提示符）
        """
        self._connect()

        try:
            # 发送命令
            self.tn.write(command.encode('ascii') + b"\n")

            # 等待命令完成（直到出现提示符）
            if self.prompt:
                output = self.tn.read_until(self.prompt.encode('ascii'), timeout=self.timeout)
            else:
                # 如果没有提示符，等待一小段时间
                time.sleep(0.5)
                output = self.tn.read_very_eager()

            # 解码输出
            output_str = output.decode('ascii', errors='ignore')

            # 移除命令回显和提示符
            lines = output_str.split('\n')

            # 查找命令回显（通常是第一行包含命令本身）
            # 和提示符（最后一行）
            result_lines = []
            for i, line in enumerate(lines):
                # 跳过空行和可能包含命令回显的行
                if line.strip() and command not in line:
                    # 检查是否是提示符（可能包含$ # >等）
                    if self.prompt and line.strip().endswith(self.prompt.strip()):
                        continue
                    result_lines.append(line.strip())

            return '\n'.join(result_lines).strip()

        except Exception as e:
            raise ConnectionError(f"发送命令失败: {e}")

    def _parse_register_output(self, output: str) -> int:
        """
        解析寄存器命令输出

        支持格式：
        - 十六进制: 0x12345678
        - 十进制: 305419896
        - 纯十六进制（无0x前缀）: 12345678

        Args:
            output: 命令输出字符串

        Returns:
            解析出的32位整数值
        """
        if not output:
            raise ValueError("输出为空")

        output = output.strip()

        # 尝试解析十六进制格式 (0x12345678)
        if output.startswith('0x') or output.startswith('0X'):
            try:
                return int(output, 16)
            except ValueError:
                pass

        # 尝试解析十进制格式
        try:
            return int(output)
        except ValueError:
            pass

        # 尝试解析无前缀十六进制
        try:
            # 检查是否看起来像十六进制（只包含0-9,a-f,A-F）
            import re
            if re.match(r'^[0-9a-fA-F]+$', output):
                return int(output, 16)
        except ValueError:
            pass

        raise ValueError(f"无法解析寄存器输出: '{output}'")

    def read_register(self, address: int) -> int:
        """
        读取寄存器值

        Args:
            address: 寄存器地址

        Returns:
            32位寄存器值
        """
        # 构建读取命令
        cmd = self.read_command.format(address=address)
        output = self._send_command(cmd)

        # 解析输出
        return self._parse_register_output(output)

    def write_register(self, address: int, value: int) -> bool:
        """
        写入寄存器值

        Args:
            address: 寄存器地址
            value: 要写入的32位值

        Returns:
            写入是否成功
        """
        # 构建写入命令
        cmd = self.write_command.format(address=address, value=value)
        output = self._send_command(cmd)

        # 根据实际服务器响应判断是否成功
        # 这里假设只要没有错误信息就成功
        if output and ("error" in output.lower() or "fail" in output.lower()):
            return False

        return True

    def close(self):
        """关闭Telnet连接"""
        if self.tn:
            self.tn.close()
            self.tn = None
            self._connected = False
            print(f"已断开与 {self.host}:{self.port} 的连接")

    def __enter__(self):
        """支持with语句"""
        self._connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持with语句"""
        self.close()

    def __del__(self):
        """析构时关闭连接"""
        try:
            self.close()
        except:
            pass


# ============================================================================
# 解析器系统
# ============================================================================

class ParserRegistry:
    """
    解析器注册表 - 管理可重用的解析器

    支持通过名称注册和获取解析器，便于扩展
    """

    def __init__(self):
        self._parsers: Dict[str, Callable[[int], Any]] = {}

    def register(self, name: str, parser_func: Callable[[int], Any]):
        """注册解析器"""
        self._parsers[name] = parser_func

    def get(self, name: str) -> Optional[Callable[[int], Any]]:
        """获取解析器"""
        return self._parsers.get(name)

    def list(self) -> List[str]:
        """列出所有注册的解析器名称"""
        return list(self._parsers.keys())

    def clear(self):
        """清空所有解析器"""
        self._parsers.clear()


# 全局解析器注册表
parser_registry = ParserRegistry()


# ============================================================================
# 预定义解析器（示例）
# ============================================================================

def bitfield_parser(field_defs: Dict[str, Dict[str, Any]]) -> Callable[[int], Dict[str, Any]]:
    """
    创建位域解析器

    Args:
        field_defs: 字段定义字典
            格式: {
                'field_name': {
                    'bits': (start, end),  # 位范围，0-based，包含两端
                    'description': '字段描述',
                    'enum': {0: '值0', 1: '值1'}  # 可选，枚举映射
                },
                ...
            }

    Returns:
        解析函数
    """
    def parser(raw_value: int) -> Dict[str, Any]:
        result = {
            'raw_value': raw_value,
            'raw_hex': f'0x{raw_value:08x}'
        }

        for field_name, field_info in field_defs.items():
            start_bit, end_bit = field_info['bits']
            bit_width = end_bit - start_bit + 1
            mask = (1 << bit_width) - 1
            field_value = (raw_value >> start_bit) & mask

            # 如果有枚举映射，添加字符串表示
            if 'enum' in field_info and field_value in field_info['enum']:
                result[f'{field_name}_str'] = field_info['enum'][field_value]

            result[field_name] = field_value
            result[f'{field_name}_bits'] = f'{start_bit}:{end_bit}'

            if 'description' in field_info:
                result[f'{field_name}_desc'] = field_info['description']

        return result

    return parser


def status_register_parser(raw_value: int) -> Dict[str, Any]:
    """状态寄存器解析器示例"""
    result = {
        'raw_value': raw_value,
        'raw_hex': f'0x{raw_value:08x}'
    }

    # 解析各个状态位
    result['ready'] = (raw_value >> 0) & 0x1
    result['busy'] = (raw_value >> 1) & 0x1
    result['error'] = (raw_value >> 2) & 0x1
    result['overflow'] = (raw_value >> 3) & 0x1
    result['fifo_empty'] = (raw_value >> 4) & 0x1
    result['fifo_full'] = (raw_value >> 5) & 0x1

    # 状态描述
    status_desc = []
    if result['ready']:
        status_desc.append("就绪")
    if result['busy']:
        status_desc.append("忙碌")
    if result['error']:
        status_desc.append("错误")
    if result['overflow']:
        status_desc.append("溢出")
    if result['fifo_empty']:
        status_desc.append("FIFO空")
    if result['fifo_full']:
        status_desc.append("FIFO满")

    result['status_description'] = " | ".join(status_desc) if status_desc else "空闲"

    return result


def data_register_parser(raw_value: int) -> Dict[str, Any]:
    """数据寄存器解析器示例 - 简单返回原始值"""
    return {
        'raw_value': raw_value,
        'raw_hex': f'0x{raw_value:08x}',
        'decimal': raw_value,
        'upper_16bits': (raw_value >> 16) & 0xFFFF,
        'lower_16bits': raw_value & 0xFFFF
    }


# 注册示例解析器
parser_registry.register('status', status_register_parser)
parser_registry.register('data', data_register_parser)


# ============================================================================
# 寄存器组管理
# ============================================================================

class RegisterSet:
    """
    寄存器组管理类

    管理一组固定寄存器，提供批量操作和解析功能
    """

    def __init__(self, access: RegisterAccess, name: str = "register_set"):
        """
        初始化寄存器组

        Args:
            access: 寄存器访问器实例
            name: 寄存器组名称
        """
        self.access = access
        self.name = name
        self.registers: Dict[str, Register] = {}  # 名称 -> Register对象
        self._address_to_name: Dict[int, str] = {}  # 地址 -> 名称映射

    def add_register(self, register: Register):
        """
        添加寄存器到组中

        Args:
            register: Register对象

        Raises:
            ValueError: 如果名称或地址已存在
        """
        if register.name in self.registers:
            raise ValueError(f"寄存器名称 '{register.name}' 已存在")

        if register.address in self._address_to_name:
            existing_name = self._address_to_name[register.address]
            raise ValueError(f"地址 0x{register.address:08x} 已被寄存器 '{existing_name}' 占用")

        self.registers[register.name] = register
        self._address_to_name[register.address] = register.name

    def add_registers(self, registers: List[Register]):
        """批量添加寄存器"""
        for reg in registers:
            self.add_register(reg)

    def get_register(self, name: str) -> Optional[Register]:
        """获取寄存器对象"""
        return self.registers.get(name)

    def get_register_by_address(self, address: int) -> Optional[Register]:
        """通过地址获取寄存器对象"""
        name = self._address_to_name.get(address)
        return self.registers.get(name) if name else None

    def read_all(self, ignore_errors: bool = True) -> Dict[str, bool]:
        """
        读取所有寄存器的值

        Args:
            ignore_errors: 是否忽略单个寄存器的读取错误

        Returns:
            字典：寄存器名称 -> 读取是否成功
        """
        results = {}

        for name, register in self.registers.items():
            try:
                value = self.access.read_register(register.address)
                register.value = value
                register.last_read_time = time.time()
                register.error = None
                results[name] = True

                print(f"读取 {name} (0x{register.address:08x}): 0x{value:08x}")

            except Exception as e:
                register.value = None
                register.error = str(e)
                results[name] = False

                if ignore_errors:
                    print(f"读取 {name} (0x{register.address:08x}) 失败: {e}")
                else:
                    raise RegisterError(f"读取寄存器 {name} 失败: {e}")

        return results

    def parse_all(self, ignore_errors: bool = True) -> Dict[str, bool]:
        """
        解析所有寄存器的值

        Args:
            ignore_errors: 是否忽略单个寄存器的解析错误

        Returns:
            字典：寄存器名称 -> 解析是否成功
        """
        results = {}

        for name, register in self.registers.items():
            try:
                success = register.parse()
                results[name] = success

                if success:
                    print(f"解析 {name}: 成功")
                else:
                    print(f"解析 {name}: 失败 - {register.error}")

            except Exception as e:
                register.error = f"解析异常: {str(e)}"
                results[name] = False

                if ignore_errors:
                    print(f"解析 {name} 异常: {e}")
                else:
                    raise ParseError(f"解析寄存器 {name} 异常: {e}")

        return results

    def read_and_parse_all(self, ignore_errors: bool = True) -> Dict[str, Dict[str, bool]]:
        """
        读取并解析所有寄存器

        Args:
            ignore_errors: 是否忽略错误

        Returns:
            字典：{
                'read_results': {名称: 读取成功},
                'parse_results': {名称: 解析成功}
            }
        """
        read_results = self.read_all(ignore_errors)
        parse_results = self.parse_all(ignore_errors)

        return {
            'read_results': read_results,
            'parse_results': parse_results
        }

    def clear_results(self):
        """清除所有寄存器的结果（值、解析结果、错误）"""
        for register in self.registers.values():
            register.value = None
            register.parsed_result = ""
            register.error = None
            register.last_read_time = None

    def get_results_dict(self) -> Dict[str, Any]:
        """获取所有寄存器的结果字典"""
        results = {}
        for name, register in self.registers.items():
            results[name] = register.to_dict()
        return results

    def save_to_json(self, filename: str, indent: int = 2):
        """
        保存结果到JSON文件

        Args:
            filename: 文件名
            indent: JSON缩进
        """
        data = {
            'metadata': {
                'name': self.name,
                'timestamp': time.time(),
                'timestamp_iso': datetime.now().isoformat(),
                'register_count': len(self.registers)
            },
            'results': self.get_results_dict()
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)

        print(f"结果已保存到 {filename}")

    def print_summary(self):
        """打印结果摘要"""
        print(f"\n寄存器组: {self.name}")
        print(f"寄存器数量: {len(self.registers)}")
        print("-" * 60)

        for name, register in self.registers.items():
            value_str = register.get_hex_value() if register.value is not None else "None"
            error_str = f" [错误: {register.error}]" if register.error else ""

            print(f"{name:20} {register.get_hex_address():12} {value_str:12}{error_str}")

            # 如果有解析结果，打印简要信息
            if register.parsed_result and register.parsed_result != "":
                if isinstance(register.parsed_result, dict):
                    # 如果是字典，只打印前几个键值对
                    items = list(register.parsed_result.items())[:3]
                    preview = ", ".join(f"{k}: {v}" for k, v in items)
                    if len(register.parsed_result) > 3:
                        preview += ", ..."
                    print(f"                    解析: {preview}")
                else:
                    print(f"                    解析: {str(register.parsed_result)[:50]}...")

        print("-" * 60)

    def __len__(self) -> int:
        """返回寄存器数量"""
        return len(self.registers)

    def __contains__(self, name: str) -> bool:
        """检查是否包含指定名称的寄存器"""
        return name in self.registers

    def __iter__(self):
        """迭代寄存器名称"""
        return iter(self.registers.keys())

    def __getitem__(self, name: str) -> Register:
        """通过名称获取寄存器"""
        if name not in self.registers:
            raise KeyError(f"寄存器 '{name}' 不存在")
        return self.registers[name]


# ============================================================================
# 工具函数
# ============================================================================

def create_register_set_from_dict(access: RegisterAccess,
                                  register_defs: Dict[str, Dict[str, Any]],
                                  name: str = "register_set") -> RegisterSet:
    """
    从字典定义创建寄存器组

    Args:
        access: 寄存器访问器
        register_defs: 寄存器定义字典
            格式: {
                'REG_NAME': {
                    'address': 0x1000,           # 寄存器地址
                    'description': '描述',       # 可选
                    'parser': 解析函数或解析器名称,  # 可选
                },
                ...
            }
        name: 寄存器组名称

    Returns:
        RegisterSet实例
    """
    regset = RegisterSet(access, name)

    for reg_name, reg_info in register_defs.items():
        if 'address' not in reg_info:
            raise ValueError(f"寄存器 '{reg_name}' 必须包含 'address' 字段")

        # 创建寄存器对象
        reg = Register(
            name=reg_name,
            address=reg_info['address'],
            description=reg_info.get('description', '')
        )

        # 设置解析器
        if 'parser' in reg_info:
            parser = reg_info['parser']

            if isinstance(parser, str):
                # 如果是字符串，从注册表获取
                parser_func = parser_registry.get(parser)
                if parser_func:
                    reg.set_parser(parser_func)
                else:
                    print(f"警告: 未找到解析器 '{parser}'，寄存器 '{reg_name}' 将不使用解析器")
            elif callable(parser):
                # 如果是函数，直接设置
                reg.set_parser(parser)
            else:
                print(f"警告: 寄存器 '{reg_name}' 的解析器类型无效: {type(parser)}")

        # 添加到寄存器组
        regset.add_register(reg)

    return regset


# ============================================================================
# 示例使用
# ============================================================================

def main_example():
    """使用示例"""
    print("=" * 60)
    print("Telnet寄存器管理器示例")
    print("=" * 60)

    # 注意：以下示例使用模拟数据，实际使用时需要真实服务器

    # 1. 创建模拟Telnet连接（实际使用时替换为真实连接）
    print("\n1. 创建模拟Telnet连接")

    class MockTelnetAccess(RegisterAccess):
        """模拟Telnet访问器，用于测试"""
        def __init__(self):
            self.registers = {
                0x1000: 0x0000000F,  # CTRL
                0x1004: 0x00000005,  # STATUS
                0x1008: 0x12345678,  # DATA
                0x100C: 0x00000001,  # CONFIG
                0x1010: 0x00000000,  # VERSION
            }

        def read_register(self, address: int) -> int:
            print(f"  模拟读取: 0x{address:08x}")
            return self.registers.get(address, 0x00000000)

        def write_register(self, address: int, value: int) -> bool:
            print(f"  模拟写入: 0x{address:08x} = 0x{value:08x}")
            self.registers[address] = value
            return True

        def close(self):
            print("  模拟连接关闭")

    access = MockTelnetAccess()

    # 实际使用时取消注释以下代码：
    # access = TelnetRegisterAccess(
    #     host='192.168.1.100',
    #     port=23,
    #     username='root',
    #     password='password',
    #     read_command="read_reg 0x{address:08x}",
    #     write_command="write_reg 0x{address:08x} 0x{value:08x}"
    # )

    # 2. 定义寄存器组
    print("\n2. 定义寄存器组")

    # 创建位域解析器
    ctrl_parser = bitfield_parser({
        'enable': {'bits': (0, 0), 'description': '使能位'},
        'mode': {'bits': (1, 3), 'description': '模式选择',
                 'enum': {0: '模式0', 1: '模式1', 2: '模式2', 3: '模式3'}},
        'clock_div': {'bits': (4, 7), 'description': '时钟分频'},
        'reset': {'bits': (8, 8), 'description': '复位位'}
    })

    # 寄存器定义字典
    register_defs = {
        'CTRL': {
            'address': 0x1000,
            'description': '控制寄存器',
            'parser': ctrl_parser
        },
        'STATUS': {
            'address': 0x1004,
            'description': '状态寄存器',
            'parser': 'status'  # 使用注册表中的解析器
        },
        'DATA': {
            'address': 0x1008,
            'description': '数据寄存器',
            'parser': 'data'  # 使用注册表中的解析器
        },
        'CONFIG': {
            'address': 0x100C,
            'description': '配置寄存器'
            # 无解析器，将只保存原始值
        },
        'VERSION': {
            'address': 0x1010,
            'description': '版本寄存器',
            'parser': lambda x: {'major': (x >> 24) & 0xFF,
                                 'minor': (x >> 16) & 0xFF,
                                 'patch': (x >> 8) & 0xFF,
                                 'build': x & 0xFF}
        }
    }

    # 3. 创建寄存器组
    print("\n3. 创建寄存器组")
    regset = create_register_set_from_dict(access, register_defs, name="示例寄存器组")

    # 4. 批量读取所有寄存器
    print("\n4. 批量读取所有寄存器（先获取原始值）")
    read_results = regset.read_all()
    print(f"读取成功: {sum(read_results.values())}/{len(regset)}")

    # 5. 执行解析函数
    print("\n5. 执行解析函数")
    parse_results = regset.parse_all()
    print(f"解析成功: {sum(parse_results.values())}/{len(regset)}")

    # 6. 打印结果摘要
    print("\n6. 结果摘要")
    regset.print_summary()

    # 7. 保存结果
    print("\n7. 保存结果到JSON文件")
    regset.save_to_json("telnet_register_results.json")

    # 8. 演示单个寄存器访问
    print("\n8. 演示单个寄存器访问")
    ctrl_reg = regset['CTRL']
    print(f"CTRL寄存器: {ctrl_reg}")
    print(f"  解析结果: {ctrl_reg.parsed_result}")

    # 9. 演示修改和重新解析
    print("\n9. 演示修改和重新解析")

    # 创建一个新的解析器
    def simple_parser(raw_value: int) -> str:
        return f"值: 0x{raw_value:08x} ({raw_value})"

    ctrl_reg.set_parser(simple_parser)
    ctrl_reg.parse()
    print(f"CTRL新解析结果: {ctrl_reg.parsed_result}")

    # 10. 关闭连接
    print("\n10. 关闭连接")
    access.close()

    print("\n" + "=" * 60)
    print("示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    main_example()