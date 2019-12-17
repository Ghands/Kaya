# coding: utf-8

from _pysha3 import keccak_256

# Solidity compiler related
solc_gen_storage_pattern = lambda x: {
    'language': 'Solidity',
    'sources': {
        'file':{'content': x}
    },
    'settings': {
        'outputSelection': {
            'file':{
                "*" : ["storageLayout"]
                # "*":["storageLayout", "evm.bytecode.object"]
            }
        }
    }
}


# solc_gen_command = lambda x: ".\\solidity-windows\\solc.exe --standard-json < %s" % x
solc_storage_command = lambda x: "solc --standard-json < %s" % x
solc_code_command = lambda x: "solc --bin-runtime %s" % x


def get_contract_name(src_contract_name, dest_contract_name):
    if src_contract_name is None:
        return dest_contract_name
    else:
        if src_contract_name == dest_contract_name:
            return src_contract_name
        else:
            raise ValueError("A single contract contains different contract names!")


def ethereum_hash(value):
    k = keccak_256()
    k.update(value)
    return k.hexdigest()


def check_hex_odd(hex_value):
    if not hex_value.startswith("0x"):
        raise ValueError("The input value is not a HEX value!")

    if len(hex_value) % 2 != 0:
        return hex_value[:2] + "0" + hex_value[2:]
    
    return hex_value