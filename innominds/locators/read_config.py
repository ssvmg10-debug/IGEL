import yaml
import os
import sys
from pathlib import Path

root_path = Path(__file__).resolve().parents[1]
print(root_path)


sys.path.append(root_path)

try:
    file_path = os.path.join(root_path,"locators",'ums_locator.yaml')

    with open(file_path,'r') as file:
        config_data=yaml.safe_load(file)

    web_element = config_data['web_element']
    print(web_element)

except Exception as e:
    print(f"Exception occurred reading config file {e}")
    exit(1)

def get_element_by_name(string,xpath):
    for i in range(len(web_element)):
        for element in web_element:
            name = element['name']
            if name == string:
                xpath_selector = str(element[xpath])
                return xpath_selector



