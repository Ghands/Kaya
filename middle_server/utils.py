# coding: utf-8

import os
import time
# import platform

# import win32clipboard as clipboard
# import win32con

import pyperclip

import xml.dom.minidom as xmldom

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from config import CHROME_PATH, CHROME_DEBUG_PORT, CHROME_USERDATA_PATH, CHROME_DRIVER_PATH
from config import METAMASK_url, METAMASK_pass


def read_from_clipboard():
    """ Read the most recent context in clipboard

    Returns:
        The unicode string in the clipboard.
    """

    return pyperclip.paste()


def start_chrome():
    """ Start the chrome and get a browser driver

    Return:
        driver: The browser driver
    """
    os.system("start {CHROME_PATH} --remote-debugging-port={CHROME_DEBUG_PORT} --user-data-dir=\"{CHROME_USERDATA_PATH}\" --lang=zh-CN".format(
        CHROME_PATH=CHROME_PATH, CHROME_DEBUG_PORT=CHROME_DEBUG_PORT, CHROME_USERDATA_PATH=CHROME_USERDATA_PATH))

    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(
        CHROME_DRIVER_PATH, chrome_options=chrome_options)
    time.sleep(2)

    return driver


def login_metamask(driver):
    """ Login the MetaMask to make ETH related website can access your account

    Args:
        driver: The browser driver
    """
    driver.get(METAMASK_url)
    time.sleep(3)

    driver.find_element_by_id("password").send_keys(METAMASK_pass)
    button_elements = driver.find_elements_by_tag_name("button")
    for single_button in button_elements:
        if single_button.get_attribute("type") == "submit":
            single_button.click()
            break
    time.sleep(3)


def switch_tab(driver, tab_name, number=1):
    """ Switch the focused tab in browser

    Args:
        driver: The browser driver
        tab_name: The key name of the tab you want to switch. It can be the part of the full title.
        number: When more than 1 tab have the `tab_name`, indicate the sequence number of the tab you want to switch.
    """
    handles = driver.window_handles
    repeat_counts = 0
    for single_handle in handles:
        driver.switch_to_window(single_handle)
        if tab_name.lower() in driver.title.lower():
            repeat_counts += 1
            if repeat_counts == number:
                break


def tab_new_and_link(driver, link_address):
    """ Create a new tab and open the link in  this tab

    Args:
        driver: The browser driver
        link_address: The url of the page you want to jump
    """
    new_tab_js = "window.open(\"{}\");".format(link_address)
    driver.execute_script(new_tab_js)


# Selenium find executions
def element_insert(element, value):
    element.clear()
    return element.send_keys(value)


find_dict = {
    "class-name": lambda driver: driver.find_element_by_class_name,
    "class-name-more": lambda driver: driver.find_elements_by_class_name,
    "id": lambda driver: driver.find_element_by_id,
    "id-more": lambda driver: driver.find_elements_by_id,
    "tag-name": lambda driver: driver.find_element_by_tag_name,
    "tag-name-more": lambda driver: driver.find_elements_by_tag_name,
}


element_action = {
    "click": lambda element, _: element.click(),
    "insert": element_insert,
    "delete": lambda element, _: element.clear()
}


def search_for_tree(xml_obj, container):
    """ transform the XML object.

    Args:
        xml_obj: The XML object.
        container: The object to store the transformed elements.

    Return:
        container: The object store more elements.
    """
    if isinstance(container, list):
        for child in xml_obj:
            if child.attrib["type"] == "dict":
                temp_container = dict()
                search_for_tree(child, temp_container)
                container.append(temp_container)
            elif child.attrib["type"] == "list":
                temp_container = list()
                search_for_tree(child, temp_container)
                container.append(temp_container)
            elif child.attrib["type"] == "int":
                container.append(int(child.text))
            else:
                container.append(child.text)
    elif isinstance(container, dict):
        for child in xml_obj:
            if child.attrib["type"] == "dict":
                temp_container = dict()
                search_for_tree(child, temp_container)
                container[child.tag] = temp_container
            elif child.attrib["type"] == "list":
                temp_container = list()
                search_for_tree(child, temp_container)
                container[child.tag] = temp_container
            elif child.attrib["type"] == "int":
                container[child.tag] = int(child.text)
            else:
                container[child.tag] = child.text
    return container


def recursive_parameters(types, this_type, depth, key_name, flag):
    """ Obtain the type and value of a variable

    Args:
        types: The dict stores information of all types.
        this_type: The type of this variable.
        depth： The depth of this variable. For `a[2].b`, its depth is 3.
        key_name: The prefix string of variable's name.
        flag: Indicates the peak type of this variable

    Return:
        A dict contains basic information of a variable.
    """
    depth += 1
    base_depth = depth
    if "t_array" in this_type:
        base_type = types[this_type]["base"]
        deeper_dict, depth = recursive_parameters(
            types, base_type, base_depth, key_name, flag)
        return {
            "outer_param_type": "t_array",
            "outer_param_size": types[this_type]["numberOfBytes"],
            "param_type": "t_uint256",
            "type_size": "32",
            "r_param_name": key_name + "+" + "t_array" + "+" + str(base_depth),
            "default_value": 0,
            "deeper_dict": deeper_dict
        }, depth
    elif "t_mapping" in this_type:
        key_type, value_type = this_type[this_type.index(
            "(") + 1: this_type.index(")")].split(",")
        deeper_dict, depth = recursive_parameters(
            types, value_type.strip(), base_depth, key_name, flag)
        return {
            "outer_param_type": "t_mapping",
            "outer_param_size": types[this_type]["numberOfBytes"],
            "param_type": key_type,
            "type_size": types[key_type]["numberOfBytes"],
            "r_param_name": key_name + "+" + "t_mapping" + "+" + str(base_depth),
            "default_value": 0,
            "deeper_dict": deeper_dict
        }, depth

    else:
        return {
            "outer_param_type": "-",
            "outer_param_size": "-",
            "param_type": this_type,
            "type_size": types[this_type]["numberOfBytes"],
            "r_param_name": key_name + "+" + flag + "+" + str(base_depth),
            "default_value": 0
        }, depth


def generate_name(path_list):
    """ Get the true name of a variable.

    Args: 
        path_list: The list contains the related information about a variable.

    Return:
        name: The true name of a variable.
    """
    name = path_list[0]
    for item in path_list[1:]:
        name += "[" + item + "]"
    return name


def clear_useless_end(input_string):
    """ Drop useless chars of a string, in case of the situation that testers         input '1,2,,,,,'.

    Args:
        input_string: The string need to be cleaned.

    Return:
        The cleaned input string.
    """
    input_string = input_string.strip()
    while input_string.endswith(","):
        input_string = input_string[:-1]
    return input_string


def get_variable_groups(all_inputs):
    """ Get all possible values of a variable, for the situation that testers         input more than one value in a input element.

    Args:
        all_inputs: The tester input string.
    
    Return:
        final_groups: The list of valid inputs.
    """
    row_length = len(all_inputs[0])
    for single_input in all_inputs[1:]:
        if len(single_input) != row_length:
            raise ValueError(
                "Please make sure the length is the same if you want to input multiple values when the type of variables is t_array or t_mapping")

    final_groups = list()
    row_length = len(all_inputs[0])
    col_length = len(all_inputs)
    for i in range(1, row_length):
        temp_list = list()
        for j in range(col_length):
            temp_list.append((all_inputs[j][0], all_inputs[j][i]))
        final_groups.append(temp_list)
    return final_groups


def split_name_values(param_items):
    """ Get the corresponding value of each possible input.

    Args:
        param_items: The item contains peak variable type, sub-variable name and tester input string.

    Return:
        return_list: The name list of each possible variable name.
    """
    return_list = list()
    for single_item in param_items:
        temp_list = [single_item[1]]
        temp_list.extend(clear_useless_end(single_item[2]).split(","))
        return_list.append(temp_list)

    return return_list


def generate_path(param_key, param_items):
    """ Genrate all possible variables with their name.

    Args:
        param_key: The peak name element of each variable.
        param_items: The item contains peak variable type, sub-variable name and tester input string.

    Returns:
        The full name, the path to visit value, the initial value want to be set.
    """

    total_lengths = split_name_values(param_items)
    all_groups = get_variable_groups(total_lengths)

    for single_group in all_groups:

        path_list = list()
        path_list.append(param_key)

        sorted_items = sorted(single_group, key=lambda x: x[0])
        for item in sorted_items[:-1]:
            path_list.append(item[1])

        yield generate_name(path_list), path_list, int(sorted_items[-1][1])


def convert_list2map(variable_lists):
    """ Transfer the container type of all variables from list to map.

    Args:
        variable_lists: A list stores all variabels.

    Returns:
        return_dict: A dict stores all variables.
    """
    return_dict = dict()
    for single_variable in variable_lists:
        return_dict[single_variable["name"]] = single_variable["value"]
    return return_dict