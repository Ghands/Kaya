# coding: utf-8

import os
import json
import re
import uuid

from flask import Flask, request, jsonify

from PreState import run as get_prestate
from PreState import find_params as get_params
from PreState import compile_solidity_runtime as get_runtime
from config import temp_prestate_dir, temp_source_dir, temp_param_dir
from utils import transfer_address_to_parameter, convert_list2map


app = Flask(__name__)


@app.route("/evm/params", methods=["POST"], strict_slashes=False)
def find_params():
    contract_src_code = request.form.get("contract_src_code")
    contract_name = request.form.get("contract_name")
    contracts_params_dict, rely_code_p, rely_code_s = get_params(contract_src_code, contract_name)

    return jsonify({"contracts_params": contracts_params_dict, "rely_code_p": rely_code_p, "rely_code_s": rely_code_s})


@app.route("/evm/cmd-running", methods=["POST"], strict_slashes=False)
def check_cmd_storage():
    context_json = json.loads(request.form.get("context"))
    contract_src_code = request.form.get("contract_src_code")
    contract_name = request.form.get("contract_name")

    _, temp_param_filename, temp_source_filename = get_params(contract_src_code, contract_name)
    runtime_code = get_runtime(temp_source_filename, contract_name)
    prestate, corresponding = get_prestate(context_json["sender_info"], temp_param_filename, context_json["setted_params"])

    temp_state_filename = os.path.join(temp_prestate_dir, str(uuid.uuid1()))
    with open(temp_state_filename, "w") as fstate:
        json.dump(prestate, fstate)
        fstate.flush()
        fstate.close()

    tx_result = dict()
    for single_tx_key in context_json["Transactions"]:
        single_transaction = context_json["Transactions"][single_tx_key]

        tx_result_string = os.popen("evm --sender {sender} --receiver {receiver} --input {input} --code {code} --value {value} --prestate {prestate} --dump run".format(
            sender=single_transaction["Sender"], receiver="0x0000000000000000000000007265636569766572", input=single_transaction["data"], value=single_transaction["total-fee-eth"], 
            code=runtime_code, prestate=temp_state_filename)).read().strip()

        json_string = tx_result_string[:tx_result_string.rindex("}") + 1]

        tx_result[single_tx_key] = transfer_address_to_parameter(json.loads(json_string)["accounts"]["0x0000000000000000000000007265636569766572"]["storage"], corresponding)

    source_variables = convert_list2map(context_json["setted_params"][contract_name])
    changed_behavior_list = list()
    for behavior_name in tx_result.keys():
        sub_params = tx_result[behavior_name]
        temp_dict = dict()
        for single_param in sub_params.keys():
            temp_src_value = source_variables.get(single_param)
            if temp_src_value is None:
                temp_dict[single_param] = {"source": None, "now": sub_params[single_param]}
            elif temp_src_value != sub_params[single_param]:
                temp_dict[single_param] = {"source": temp_src_value, "now": sub_params[single_param]}
        changed_behavior_list.append({"behavior_name": behavior_name, "variables": temp_dict})

    return jsonify(changed_behavior_list)


@app.route("/evm/running", methods=["POST"], strict_slashes=False)
def check_storage():
    context_json = json.loads(request.form.get("context"))
    rely_code_p = request.form.get("rely_code_p")
    rely_code_s = request.form.get("rely_code_s")
    contract_name = request.form.get("contract_name")

    if os.path.basename(rely_code_s) not in os.listdir(temp_source_dir):
        raise ValueError("Your session have been out of date, please request parameters again!")
    else:
        runtime_code = get_runtime(rely_code_s, contract_name)

    if os.path.basename(rely_code_p) not in os.listdir(temp_param_dir):
        raise ValueError("Your session have been out of date, please request parameters again!")

    if not os.path.exists(temp_prestate_dir):
        os.makedirs(temp_prestate_dir)

    prestate, corresponding = get_prestate(context_json["sender_info"], 
        rely_code_p, context_json["setted_params"])

    temp_state_filename = os.path.join(temp_prestate_dir, str(uuid.uuid1()))
    with open(temp_state_filename, "w") as fstate:
        json.dump(prestate, fstate)
        fstate.flush()
        fstate.close()

    tx_result = dict()
    for single_tx_key in context_json["Transactions"]:
        single_transaction = context_json["Transactions"][single_tx_key]

        tx_result_string = os.popen("evm --sender {sender} --receiver {receiver} --input {input} --code {code} --value {value} --prestate {prestate} --dump run".format(
            sender=single_transaction["Sender"], receiver="0x0000000000000000000000007265636569766572", input=single_transaction["data"], value="4000000000000000000",#value=single_transaction["total-fee-eth"], 
            code=runtime_code, prestate=temp_state_filename)).read().strip()

        # print(tx_result_string)
        json_string = tx_result_string[:tx_result_string.rindex("}") + 1]

        tx_result[single_tx_key] = transfer_address_to_parameter(json.loads(json_string)["accounts"]["0x0000000000000000000000007265636569766572"]["storage"], corresponding)

    return jsonify(tx_result)


if __name__ == "__main__":
    app.run(host="0.0.0.0")