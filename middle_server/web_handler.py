# coding: utf-8

import time
import json

from config import target_website_url

from utils import tab_new_and_link, switch_tab, read_from_clipboard, start_chrome, login_metamask, find_dict, element_action


def goto_website(driver):
    """ Create a new tab and open the page of SnailThrone in this tab

    Args:
        driver: The browser driver
    """
    tab_new_and_link(driver, target_website_url)
    time.sleep(3)
    switch_tab(driver, "SnailThrone")
    time.sleep(1)


def execute_single_case(driver, single_case):
    """ Execute single case to start a transaction

    Args:
        driver: The browser driver
        single_case: Parameters of a case in settings
    """
    case_steps = single_case["items"]
    for single_step in case_steps:
        now_loc = driver
        if single_step.get("area") is not None:
            for each_loc in single_step["area"]:
                for key in each_loc.keys():
                    now_loc = find_dict[key](driver)(each_loc[key])

        all_targets = now_loc.find_elements_by_tag_name(single_step["tag_name"])
        for single_target in all_targets:
            if single_target.get_attribute(single_step["filter_key"]) == single_step["filter_value"]:
                element_action[single_step["action"]](single_target, single_step.get("action_value"))
                break
        time.sleep(2)

        if single_step.get("switch_window") is not None:
            switch_tab(driver, single_step["switch_window"])
            time.sleep(1)


def get_tx_data(driver):
    """ Read transaction related data in MetaMask

    Args:
        driver: The browser driver

    Return:
        tx_data: A dict stores all related data of a transaction. This contains these keys: Sender, Receiver, action, title, sub-title, gas-fee-eth, gas-fee-$, total-fee-eth, total-fee-$, data
    """
    tx_data = dict()

    # Get sender and receiver
    for idx, single_role in enumerate(driver.find_elements_by_class_name("sender-to-recipient__tooltip-container")):
        single_role.click()
        time.sleep(1)
        if idx == 0:
            tx_data["Sender"] = read_from_clipboard()
        else:
            tx_data["Receiver"] = read_from_clipboard()

    # Get the main content
    tx_data["action"] = driver.find_element_by_class_name("confirm-page-container-summary__action").text
    tx_data["title"] = driver.find_element_by_class_name("confirm-page-container-summary__title").find_element_by_tag_name("span").text
    tx_data["sub-title"] = driver.find_element_by_class_name("confirm-page-container-summary__subtitle").find_element_by_tag_name("span").text

    # Get the gas fee, total fee and data of Tx
    li_tags = driver.find_elements_by_tag_name("li")
    for single_li in li_tags:
        if single_li.text.lower() == "details":
            single_li.click()
            time.sleep(1)
            detail_spans = driver.find_element_by_class_name("confirm-page-container-content__details").find_elements_by_tag_name("span")
            tx_data["gas-fee-eth"] = detail_spans[0].text
            tx_data["gas-fee-$"] = detail_spans[1].text
            tx_data["total-fee-eth"] = "%d" % (float(detail_spans[2].text) * 10 ** 18)
            tx_data["total-fee-$"] = detail_spans[3].text
        else:
            single_li.click()
            time.sleep(1)
            tx_data["data"] = driver.find_elements_by_class_name("confirm-page-container-content__data-box")[-1].text

    # Refuse the Tx
    driver.find_elements_by_tag_name("button")[0].click()
    time.sleep(1)

    # Go back to SnailThone
    switch_tab(driver, "SnailThrone")
    time.sleep(1)

    return tx_data


def run_web_crawler(test_cases):
    """ Execute the options to get the data of transaction

    Args:
        test_cases: Parameters to start transactions

    Return:
        total_tx_data: Information of transactions.
    """
    driver = start_chrome()
    login_metamask(driver)
    goto_website (driver)

    total_tx_data = dict()
    for single_case in test_cases:
        execute_single_case(driver, single_case)
        single_tx_data = get_tx_data(driver)
        # print(single_tx_data)
        total_tx_data[single_case["name"]] = single_tx_data

    # Close the browser
    for temp_handle in driver.window_handles:
        driver.switch_to_window(temp_handle)
        driver.close()
    driver.quit()
    
    return total_tx_data