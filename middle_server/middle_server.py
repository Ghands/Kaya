# coding: utf-8

import requests
import json

import xml.etree.cElementTree as ET

from copy import deepcopy

from flask import Flask, request, render_template, make_response
from config import server_host
from utils import search_for_tree, recursive_parameters, convert_list2map, generate_path
from web_handler import run_web_crawler

app = Flask(__name__)


@app.route("/kaya/start", methods=["GET"], strict_slashes=False)
def welcome_page():
    return render_template("start.html")


@app.route("/kaya/get_parameter", methods=["POST"], strict_slashes=False)
def get_parameter():
    contract_src_code = request.form.get("contract_src_code")
    contract_name = request.form.get("contract_name")
    data = {
        "contract_src_code": contract_src_code,
        "contract_name": contract_name
    }
    r = requests.post("http://%s/evm/params" % server_host, data=data).json()

    parameter_list = list()
    rely_code_p = r["rely_code_p"]
    rely_code_s = r["rely_code_s"]
    params = r["contracts_params"]["file:%s" % contract_name]["params"]
    types = r["contracts_params"]["file:%s" % contract_name]["types"]
    for key in params.keys():
        this_type = params[key]["type"]
        if "t_array" in this_type:
            flag = "t_array"
            base_depth = 1
            deeper_dict, depth = recursive_parameters(
                types, types[this_type]["base"], base_depth, key, flag)
            parameter_list.append(
                {"param_name": key, "outer_param_type": "t_array", "outer_param_size": types[this_type]["numberOfBytes"], "param_type": "t_uint256", "type_size": "32", "r_param_name": key + "+" + "t_array" + "+" + str(base_depth), "default_value": 0, "deeper_dict": deeper_dict, "depth": depth})
        elif "t_mapping" in this_type:
            flag = "t_mapping"
            base_depth = 1
            key_type, value_type = this_type[this_type.index(
                "(") + 1: this_type.index(")")] .split(",")
            deeper_dict, depth = recursive_parameters(
                types, value_type.strip(), base_depth, key, flag)
            parameter_list.append({"param_name": key, "outer_param_type": "t_mapping", "outer_param_size": types[this_type]["numberOfBytes"], "param_type": key_type, "type_size": types[
                                  key_type]["numberOfBytes"], "r_param_name": key + "+" + "t_mapping" + "+" + str(base_depth), "default_value": 0, "deeper_dict": deeper_dict, "depth": depth})
        else:
            depth = 1
            parameter_list.append(
                {"param_name": key, "outer_param_type": "-", "outer_param_size": "-", "param_type": this_type, "type_size": types[this_type]["numberOfBytes"], "r_param_name": key + "+" + "-" + "+" + str(depth), "default_value": 0, "depth": depth})

    resp = make_response(render_template(
        "set_parameter.html", param_list=parameter_list, contract_name=contract_name))
    resp.set_cookie("rely_code_p", rely_code_p)
    resp.set_cookie("rely_code_s", rely_code_s)

    return resp


@app.route("/kaya/define_parameter", methods=["POST"], strict_slashes=False)
def get_running_result():
    input_values = request.form
    rely_code_p = request.cookies.get("rely_code_p")
    rely_code_s = request.cookies.get("rely_code_s")
    param_dict = dict()
    # print(input_values)

    for key in input_values:
        if key not in ["contract_name", "selenium_setting"]:
            key_patterns = key.split("+")
            former_pattern = key_patterns[0]
            if param_dict.get(former_pattern) is None:
                param_dict[former_pattern] = [
                    (key_patterns[1], key_patterns[2], input_values[key])]
            else:
                param_dict[former_pattern].append(
                    (key_patterns[1], key_patterns[2], input_values[key]))

    set_param_list = list()
    for item in param_dict:
        # if param_dict[item][0][0] == "-":
        for temp_tuple in generate_path(item, param_dict[item]):
            item_name, item_path, item_value = temp_tuple
            set_param_list.append(
                {"name": item_name, "path": item_path, "value": item_value})

    setted_params = {input_values["contract_name"]: set_param_list}

    # test_cases = json.loads(input_values["selenium_setting"])
    test_cases = search_for_tree(ET.fromstring(
        input_values["selenium_setting"]), list())
    # print(test_cases)

    total_tx_data = run_web_crawler(test_cases)
    # print(total_tx_data)
    transactions = dict()
    for item in total_tx_data:
        transactions[item] = {"Sender": total_tx_data[item]["Sender"], "data": total_tx_data[item]
                              ["data"], "total-fee-eth": total_tx_data[item]["total-fee-eth"]}
        sender_address = total_tx_data[item]["Sender"]  # Maybe have a bug

    context_json = {"setted_params": setted_params, "Transactions": transactions, "sender_info": {
        "address": sender_address, "balance": "1000000000000000000000000000"}}

    data = {"context": json.dumps(context_json), "rely_code_p": rely_code_p,
            "rely_code_s": rely_code_s, "contract_name": input_values["contract_name"]}

    print(data)

    # print(data)
    r = requests.post("http://%s/evm/running" % server_host, data=data).json()

    # Compare all variables.
    source_variables = convert_list2map(
        setted_params[input_values["contract_name"]])
    changed_behavior_list = list()
    for behavior_name in r.keys():
        sub_params = r[behavior_name]
        temp_dict = dict()
        for single_param in sub_params.keys():
            temp_src_value = source_variables.get(single_param)
            if temp_src_value is None:
                temp_dict[single_param] = {
                    "source": None, "now": sub_params[single_param]}
            elif temp_src_value != sub_params[single_param]:
                temp_dict[single_param] = {
                    "source": temp_src_value, "now": sub_params[single_param]}
        changed_behavior_list.append(
            {"behavior_name": behavior_name, "variables": temp_dict})

    return render_template("show_result.html", behavior_list=changed_behavior_list)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)
