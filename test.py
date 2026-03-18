from register_tool import MockRegisterAccess, RegisterBank, BitFieldParser




if __name__ == "__main__":
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