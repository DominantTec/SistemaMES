from pymodbus.client import ModbusTcpClient


def get_registers_values(machine, register_number):
    if machine == 'MAQ1':
        client = ModbusTcpClient(host="192.168.11.89", port=502, timeout=10)
    else:
        client = ModbusTcpClient(host="192.168.11.90", port=502, timeout=10)

    register = client.read_holding_registers(register_number).registers[0]

    client.close()

    return register


def post_registers_values(machine, register_number, value):
    if machine == 'MAQ1':
        client = ModbusTcpClient(host="192.168.11.89", port=502, timeout=10)
    else:
        client = ModbusTcpClient(host="192.168.11.90", port=502, timeout=10)

    try:
        client.write_register(register_number, value)
        client.close()
        return True
    except:
        client.close()
        return False
