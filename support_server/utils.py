# coding: utf-8

from _pysha3 import keccak_256


# THe wrapper for getting possible variables
solc_gen_storage_pattern = lambda x: {
    'language': 'Solidity',
    'sources': {
        'file':{'content': x}
    },
    'settings': {
        'outputSelection': {
            'file':{
                "*" : ["storageLayout"]
            }
        }
    }
}


# Get possible variables with bash command
solc_storage_command = lambda x: "solc --standard-json < %s" % x
# Get runtime bytecode with bash command
solc_code_command = lambda x: "solc --bin-runtime %s" % x


def compare_contract_name(src_contract_name, dest_contract_name):
    """ Compare the contract name, keep the contract name unique.

    Args:
        src_contract_name: The recorded contract name.
        dest_contract_name: The contract name need to be compared

    Return:
        dest_contract_name: The unique contract Name

    Raise:
        ValueError: These two names are different when the `src_contract_name` is not None, which cannot happen in normal situations.
    """
    if src_contract_name is None:
        return dest_contract_name
    else:
        if src_contract_name == dest_contract_name:
            return dest_contract_name
        else:
            raise ValueError("A single contract contains different contract names!")


def ethereum_hash(value):
    """ Calculate the hash

    Args:
        value: The value need to generate the hash

    Return:# coding: utf-8

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
        Generated hash.
    """
    k = keccak_256()
    k.update(value)
    return k.hexdigest()


def check_hex_odd(hex_value):
    """ Check the HEX string, make sure it be normal.

    Args:
        hex_value: The HEX string need to be checked.

    Return:
        hex_value: The modified HEX string.
    """
    if not hex_value.startswith("0x"):
        raise ValueError("The input value is not a HEX value!")

    if len(hex_value) % 2 != 0:
        return hex_value[:2] + "0" + hex_value[2:]
    
    return hex_value



def transfer_address_to_parameter(storage_dict, corresponding):
    """ Transform the address of variables into name 

    Args:
        storage_dict: The dict stores the addresses need to be transformed.
        corresponding: The dict stores the address and corresponding name.

    Return:
        return_dict: The dict stores the transformed variables
    """
    return_dict = dict()
    for key in storage_dict:
        return_dict[corresponding[int(key, 16)]] = int(storage_dict[key], 16)

    return return_dict


def convert_list2map(variable_lists):
    """ Transform the type of the object which stores variables with initialized values, from list to map

    Args:
        variable_lists: The list stores all variables with initialized values.

    Return:
        return_dict: The dict stores variables.
    """
    return_dict = dict()
    for single_variable in variable_lists:
        return_dict[single_variable["name"]] = single_variable["value"]
    return return_dict