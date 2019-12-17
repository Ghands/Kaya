# coding: utf-8

import json
import os
import re
import uuid
import functools

from copy import deepcopy

from utils import solc_gen_storage_pattern, solc_storage_command, solc_code_command, get_contract_name, ethereum_hash, check_hex_odd
from config import temp_storage_dir, temp_source_dir, temp_code_dir, temp_param_dir, temp_prestate_dir


def compile_solidity_params(contract_src_string, contract_name):
    """ Get all possible variables in a smart contract

    Args:
        contract_src_string: The source code of smart contract with string format
        contract_name: The name of this smart contract.

    Return:
        compiled_json: The compiled smart contract with json format.
        temp_source_filename: The name of the file stores the source code of a smart contract.
    """
    if not os.path.exists(temp_storage_dir):
        os.makedirs(temp_storage_dir)
    if not os.path.exists(temp_source_dir):
        os.makedirs(temp_source_dir)

    temp_source_filename = os.path.join(temp_source_dir, str(uuid.uuid1()))
    with open(temp_source_filename, "w") as file_to_source:
        file_to_source.write(contract_src_string)
        file_to_source.flush()
        file_to_source.close()
    
    temp_storage_filename = os.path.join(temp_storage_dir, str(uuid.uuid1()))
    with open(temp_storage_filename, "w") as file_to_storage:
        json.dump(solc_gen_storage_pattern(contract_src_string), file_to_storage, indent=4)
        file_to_storage.flush()
        file_to_storage.close()

    storage_running = os.popen(solc_storage_command(temp_storage_filename))
    compiled_json = json.loads(storage_running.read())

    if "errors" in compiled_json:
        raise ValueError("Please ensure the source code of smart contract is right!")

    return compiled_json, temp_source_filename


def compile_solidity_runtime(temp_source_filename, contract_name):
    """ Get the executable runtime bytecode

    Args:
        temp_source_filename: The name of a file stores the source code of a smart contract.
        contract_name: The name of this smart contract

    Return:
        The runtime bytecode of a smart contract.
    """
    code_running = os.popen(solc_code_command(temp_source_filename))
    to_delete_string = code_running.read()
    code_find_pattern = r"{code_file_name}:{contract_name}.*\n.*?runtime\spart:\s\n(.*?)\n".format(code_file_name=temp_source_filename, contract_name=contract_name)
    code_from_re = re.findall(code_find_pattern, to_delete_string)
    if len(code_from_re) != 1:
        raise ValueError("The runtime bytecode has something error, please email to the author!")

    return "0x" + code_from_re[0]


def get_contract_params(compiled_json):
    """ Get the information of parameters contained in smart contracts.

    Args:
        compiled_json: The compiled smart contract with json format.

    Return:
        contracts_params_dict: The parameters and their types contained in smart contracts. The format is like:
            {
                "file:mortal": {
                    "params": {
                        "owner": {
                            "astId": 12, 
                            "offset": 0, 
                            "slot": 0, 
                            "type": "t_address_payable"
                        },
                        "t": {
                            "astId": 32,
                            "offset": 0,
                            "slot": 1,
                            "type": "t_array(t_bool)100_storage"
                        }
                    },
                    "types": {
                        "t_address_payable": {
                            "encoding": "inplace",
                            "label": "address payable",
                            "numberOfBytes": "20"
                        },
                        "t_array(t_bool)100_storage": {
                            "base": "t_bool",
                            "encoding:" "inplace",
                            "label": "bool[100]",
                            "numberOfBytes": "128"
                        },
                        "t_bool": {
                            "encoding": "inplace",
                            "label": "bool",
                            "numberOfBytes": "1"
                        }
                    }
                }
            }
    """
    contracts_params_dict = dict()

    # print(compiled_json)
    contracts_list = compiled_json["contracts"]["file"].values()

    for single_contract in contracts_list:
        temp_contract_params = {"params": {}, "types": {}}
        contract_name = None
        
        params_list = single_contract["storageLayout"]["storage"]
        for single_param in params_list:
            contract_name = get_contract_name(contract_name, single_param.pop("contract"))
            temp_contract_params["params"][single_param.pop("label")] = deepcopy(single_param)

        if single_contract["storageLayout"]["types"] is not None:
            temp_contract_params["types"] = deepcopy(single_contract["storageLayout"]["types"])

        if contract_name is not None:
            contracts_params_dict[contract_name] = temp_contract_params

    return contracts_params_dict


def find_param_position(param_path, types_dict, this_type, this_slot:int, this_offset:int):
    """ Calculate the position of a variable

    Args:
        param_path: The path to access the final variable from the variable now.
        types_dict: The dict stores all the types.
        this_type: The type of this variable.
        this_slot: The slot this variable locates at now.
        this_offset: The offset this variable locates at now.

    Returns:
        The slot, offset and type of the final variable.
    """
    if len(param_path) == 0:
        return this_slot, this_offset, this_type

    origin_type_info = types_dict[this_type]

    if "mapping" == origin_type_info["encoding"]:
        key_type = types_dict[origin_type_info["key"]]
        key_size = key_type["numberOfBytes"]
        key = int(param_path[0]).to_bytes(32, byteorder="big")
        offset = this_slot.to_bytes(32, byteorder="big")
        all_offset = key + offset

        whole_offset = ethereum_hash(all_offset)

        value_type = origin_type_info["value"]
        a, b, c = find_param_position(param_path[1:], types_dict, value_type, int(whole_offset, 16), 0) # c means the type

        return a, b, c

    if "dynamic_array" == origin_type_info["encoding"]:
        key = param_path[0].to_bytes(32, byteorder="big")
        offset = this_slot.to_bytes(32, byteorder="big")
        all_offset = key + offset

        whole_offset = ethereum_hash(all_offset)

        value_type = origin_type_info["base"]
        a, b, c = find_param_position(param_path[1:], types_dict, value_type, int(whole_offset, 16), 0)

        return a, b, c

    if "t_array" in this_type:
        slot = this_slot
        offset = this_offset
        idx = int(param_path[0])
        base = origin_type_info["base"]
        per_size = int(types_dict[base]["numberOfBytes"])

        for i in range(idx):
            if offset + per_size > 32:
                slot += 1
                offset = 0
            offset += per_size
        
        return slot, offset, base

    if "t_struct" in this_type:
        now_member = param_path[0]
        this_member = None

        for single_member in origin_type_info["members"]:
            if single_member["label"] == now_member:
                this_member = single_member
                break

        if this_member is None:
            raise ValueError("There is no right type recorded in types dict")
        
        offset = int(this_member["offset"]) + this_offset
        slot = int(this_member["slot"]) + this_slot
        value_type = this_member["type"]
        a, b, c = find_param_position(param_path[1:], types_dict, value_type, slot, offset)

        return a, b, c

    return this_slot, this_offset, this_type


def get_true_position(param_path, params_dict, types_dict):
    """ Get the true position of the specific parameter

    Args:
        param_path: The path to get the parameter want to change
        params_dict: A dict stores the parameters in this contract
        types_dict: A dict stores the types of all parameters in this contract

    Returns:
        slot: The true number of slot.
        offset: The true number of offset.
        bottom_type: The variable type of the deepest variable.
    """
    origin_label = param_path[0]

    origin_type_dict = None
    for single_element in params_dict:
        if params_dict[single_element]["label"] == origin_label:
            origin_type_dict = params_dict[single_element]
            break
    #print(param_path)
    if origin_type_dict is None:
        raise ValueError("There is no corresponding parameter in this smart contract!")
    
    slot, offset, bottom_type = find_param_position(param_path[1:], types_dict, origin_type_dict["type"], int(origin_type_dict["slot"]), int(origin_type_dict["offset"]))

    return slot, offset, bottom_type

# 用户定义 {"mortal": [{"name": "s[1].b", "path": [t, 0], "value": 10}, {}]}

def add_offset(sorted_sub_param_dict):
    """ Add variables accross the offset

    Args:
        sorted_sub_param_dict: The sorted items from a dict contains all variables in the same slot

    Return:
        The name of all variables in the same slot and the final combined value of these variables.
    """
    # former_offset = sorted_sub_param_dict[0]
    null_value = 0
    former_offset_value = 0
    former_hex_value = null_value.to_bytes(former_offset_value, "big")

    for now_offset in sorted_sub_param_dict:
        if now_offset[1]["offset"] < former_offset_value:
            raise ValueError("There is a error in offset calculation, maybe a bug!")
        elif now_offset[1]["offset"] > former_offset_value:
            # former_hex_value += null_value.to_bytes(now_offset[1]["offset"] - former_offset_value, "big")
            former_hex_value = null_value.to_bytes(now_offset[1]["offset"] - former_offset_value, "big") + former_hex_value
            former_offset_value = now_offset[1]["offset"]
        # former_hex_value += now_offset[1]["value"].to_bytes(int(now_offset[1]["type"]["numberOfBytes"]), "big")
        print(now_offset)
        former_hex_value = now_offset[1]["value"].to_bytes(int(now_offset[1]["type"]["numberOfBytes"]), "big") + former_hex_value
        former_offset_value += int(now_offset[1]["type"]["numberOfBytes"])

    if former_offset_value > 32:
        raise ValueError("The length of final value has exceeded 256, maybe a bug!")
    if former_offset_value < 32:
        # former_hex_value += null_value.to_bytes(32 - former_offset_value, "big")
        former_hex_value = null_value.to_bytes(32 - former_offset_value, "big") + former_hex_value

    return functools.reduce(lambda x, y: x + "|" + y, [item[0] for item in sorted_sub_param_dict]), former_hex_value


def gen_storage(user_param_dict, types_dict, slot_more_than_one, slot_equal_one, slot_record_dict):
    """ Get all variables will be initialized.

    Args:
        user_param_dict: The variables with initalized value testers set.
        types_dict: The dict stores all the types.
        slot_more_than_one: The set stores the slots whose number of variables more than 1.
        slot_equal_one: The set stores the slots whose number of variabels equals to 1.
        slot_record_dict: The dict stores information about all variables.

    Return:
        storage: The final elements in the storage of the receiver address in Prestate.
        corresponding: The dict stores the corresponsing relationship of slots and variable names.
    """
    storage = dict()
    corresponding = dict()
    for slot_num in slot_more_than_one:
        sub_param_dict = dict([(key, user_param_dict[key]) for key in slot_record_dict[slot_num]])
        sorted_sub_param_dict = sorted(sub_param_dict.items(), key=lambda value: value[1]["offset"])
        all_param_name, final_value = add_offset(sorted_sub_param_dict) # all_param_name 暂未使用
        storage[check_hex_odd(hex(slot_num))] = "0x" + final_value.hex()
        corresponding[slot_num] = all_param_name

    for slot_num in slot_equal_one:
        single_key = slot_record_dict[slot_num][0]
        all_param_name, final_value = add_offset([(single_key, user_param_dict[single_key])]) # all_param_name 暂未使用
        storage[check_hex_odd(hex(slot_num))] = "0x" + final_value.hex()
        corresponding[slot_num] = all_param_name

    # print(storage)
    return storage, corresponding


def get_contracts_status(user_commit, contracts_params_dict):
    """ Generate the status for each smart contract

    Args:
        user_commit: The information of all variables testers want to initialize.
        contracts_params_dict: The dict stores all variabels of all contracts.

    Return:
        contracts_list: A list of contracts, each contract contains its prestate information.
    """
    contracts_list = list()
    for true_contract_name in user_commit.keys():
        single_contract_name = "file:" + true_contract_name
        user_param_dict = dict()
        slot_record_dict = dict() # Record the number of parameters in per slot
        slot_more_than_one = set()
        slot_equal_one = set()
        params_dict = contracts_params_dict[single_contract_name]["params"]
        types_dict = contracts_params_dict[single_contract_name]["types"]
        for single_param in user_commit[true_contract_name]:
            param_slot, param_offset, param_type = get_true_position(single_param["path"], params_dict, types_dict)
            user_param_dict[single_param["name"]] = {
                "slot": param_slot, 
                "offset": param_offset, 
                "value": single_param["value"],
                "type": types_dict[param_type]
            }
            
            if slot_record_dict.get(param_slot) is None:
                slot_record_dict[param_slot] = [single_param["name"]]
                slot_equal_one.add(param_slot)
            else:
                slot_record_dict[param_slot].append(single_param["name"])
                slot_more_than_one.add(param_slot)
                slot_equal_one.remove(param_slot)

        temp_corresponding = dict()
        for key_item in params_dict.keys():
            temp_corresponding[int(params_dict[key_item]["slot"])] = key_item

        storage, corresponding = gen_storage(user_param_dict, types_dict, slot_more_than_one, slot_equal_one, slot_record_dict)

        corresponding.update(temp_corresponding)

        contracts_list.append(({
            "balance": "1000000000000000000000000000",
            # "code": "0x" + compiled_json["contracts"]["runtime-code"],
            "nonce": hex(0), # 需要修改
            "storage": storage
        }, corresponding))
    
    return contracts_list


def gen_prestate(sender_info, contracts_info=None):
    """ Generate the prestate for a transaction

    Args:
        sender_info: The information about sender address.
        contracts_info: The information about the smart contracts used in this transaction.

    Returns:
        The prestate and the dict stores the corresponding relationship about slots and variable names.
    """
    state_dict={}
    state_dict['alloc']={}

    if len(contracts_info) > 1:
        raise ValueError("The number of smart contracts exceed 1, this is not support now, please email to the author!")

    state_dict["alloc"]["0x0000000000000000000000007265636569766572"] = contracts_info[0][0]

    # if contracts_info is not None:
    #     for i in contracts_info:
    #         state_dict['alloc']["0x000000000000000000000000000000000000000%x"%index]=i
    #         index=index+1

    state_dict['alloc'][sender_info["address"]]={"balance": sender_info["balance"]}
    state_dict['coinbase']="0x0000000000000000000000000000000000000000"
    state_dict['config']={"homesteadBlock": 0, "daoForkBlock": 0, "eip150Block": 0, "eip155Block": 0, "eip158Block": 0, "byzantiumBlock": 0, "constantinopleBlock": 0, "petersburgBlock": 0, "istanbulBlock": 0}
    state_dict['difficulty']="0x0"
    state_dict["extraData"]="0x"
    state_dict["gasLimit"]="0x2FEFD800"
    state_dict['mixhash']="0x0000000000000000000000000000000000000000000000000000000000000000"
    state_dict['nonce']="0x0000000000000000"
    state_dict['timestamp']='0x00'
    state_dict['number']='0x01'
    
    # pre_state = json.dumps(state_dict)
    return state_dict, contracts_info[0][1]


def find_params(contract_src_code, contract_name):
    """ Find all possible variables contained in a smart contract

    Args:
        contract_src_code: The source code of a smart contract
        contract_name: The name of the smart contract.

    Return:
        contracts_params_dict: The dict stores information of all variables corresponding smart contracts.
        temp_param_filename: The name of a file stores all variables.
        temp_source_filename: The name of a file stores the source code of a smart contract.
    """
    if contract_name is None:
        raise ValueError("Please input the name of smart contract!")

    compiled_json, temp_source_filename = compile_solidity_params(contract_src_code, contract_name)
    contracts_params_dict = get_contract_params(compiled_json)

    if not os.path.exists(temp_param_dir):
        os.makedirs(temp_param_dir)
    temp_param_filename = os.path.join(temp_param_dir, str(uuid.uuid1()))
    with open(temp_param_filename, "w") as fparam:
        json.dump(contracts_params_dict, fparam)
        fparam.flush()
        fparam.close()

    return contracts_params_dict, temp_param_filename, temp_source_filename


def run(sender_info, temp_param_filename, user_commit):
    """ The main function to get the prestate

    Args:
        sender_info: The information of sender address
        temp_param_filename: The name of a file stores the varirables.
        user_commit: The information of all variables testers want to initialize.

    Return:
        The generated prestate
    """
    if not isinstance(user_commit, dict):
        raise TypeError("Please check the type of your DSL input. If you have no parameter want to modify, please exit.")

    with open(temp_param_filename, "r") as fparam:
        contracts_params_dict = json.load(fparam)
        fparam.close()

    if user_commit is None:
        return gen_prestate(sender_info)
    else:
        contracts_info = get_contracts_status(user_commit, contracts_params_dict)
        return gen_prestate(sender_info, contracts_info)


if __name__ == "__main__":
    _, temp_param_filename, _ = find_params(open("content.sol", "r").read(), "SnailThrone")

    pre_state = run(
        {"address": "0x0000000000000000000000000000000000000001", "balance": "0x10000"},
        temp_param_filename,
        {"SnailThrone": [{"name":"GOD_TIMER_INTERVAL","path":["GOD_TIMER_INTERVAL"],"value":12},{"name":"pharaohReq","path":["pharaohReq"],"value":40},{"name":"TOKEN_MAX_BUY","path":["TOKEN_MAX_BUY"],"value":4000000000000000000},{"name":"TOKEN_PRICE_MULT","path":["TOKEN_PRICE_MULT"],"value":10000000},{"name":"maxSnail","path":["maxSnail"],"value":100},{"name":"TOKEN_PRICE_FLOOR","path":["TOKEN_PRICE_FLOOR"],"value":20000000000000},{"name":"TIME_TO_HATCH_1SNAIL","path":["TIME_TO_HATCH_1SNAIL"],"value":1080000},{"name":"GOD_TIMER_BOOST","path":["GOD_TIMER_BOOST"],"value":480},{"name":"PHARAOH_REQ_START","path":["PHARAOH_REQ_START"],"value":40},{"name":"GOD_TIMER_START","path":["GOD_TIMER_START"],"value":86400},{"name":"lastClaim","path":["lastClaim"],"value":0},{"name":"gameStarted","path":["gameStarted"],"value":1},{"name":"hatcherySnail","path":["hatcherySnail",1],"value":1}]}

    )

    print(pre_state)

    with open("test_pre_state.txt", "w") as fopen:
        fopen.write(json.dumps(pre_state))
        fopen.flush()
        fopen.close()

    evm_running = os.popen("evm --sender {sender} --receiver {receiver} --input {input} --value 3 --prestate {prestate} --dump run".format(sender="0x0000000000000000000000000000000000000001", input="59423a7f0000000000000000000000000000000000000000000000000000000000000000", prestate="test_pre_state.txt", receiver="0x0000000000000000000000007265636569766572"))

    print(evm_running.read())
