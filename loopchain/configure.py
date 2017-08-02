# Copyright [theloop]
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
""" A module for configuration"""

import re
import loopchain
from loopchain.configure_default import *
try:
    from loopchain.configure_user import *
    ENABLE_USER_CONFIG = True
except ImportError:
    # no error just no user configure module
    ENABLE_USER_CONFIG = False


class DataType(IntEnum):
    string = 0
    int = 1
    float = 2
    bool = 3


class ConfigureMetaClass(type):
    """특정 클래스에서 metaclass 로 지정하면 해당 클래스는 singleton이 된다.
    사용예: class BlockChain(metaclass=SingletonMetaClass):
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(ConfigureMetaClass, cls).__call__(*args, **kwargs)

        return cls._instances[cls]


class Configure(metaclass=ConfigureMetaClass):

    def __init__(self):
        # print("Set Configure... only once in scope from system environment.")

        # configure_info_list = {configure_attr: configure_type}
        self.__configure_info_list = {}

        self.__load_configure(loopchain.configure_default)
        if ENABLE_USER_CONFIG:
            self.__load_configure(loopchain.configure_user)

        # print(f"conf.ENABLE_PROFILING: {globals()['ENABLE_PROFILING']}, "
        #       f"type({type(globals()['ENABLE_PROFILING'])})")
        # print(f"conf.GRPC_TIMEOUT: {globals()['GRPC_TIMEOUT']}, "
        #       f"type({type(globals()['GRPC_TIMEOUT'])})")
        # print(f"conf.LEADER_BLOCK_CREATION_LIMIT: {globals()['LEADER_BLOCK_CREATION_LIMIT']}, "
        #       f"type({type(globals()['LEADER_BLOCK_CREATION_LIMIT'])})")
        # print(f"conf.TOKEN_TYPE_TOKEN: {globals()['TOKEN_TYPE_TOKEN']}, "
        #       f"type({type(globals()['TOKEN_TYPE_TOKEN'])})")

    @property
    def configure_info_list(self):
        return self.__configure_info_list

    def __load_configure(self, configure_module):
        configure_name_list = dir(configure_module)

        for configure_attr in configure_name_list:
            try:
                # print(configure_attr)
                configure_default = getattr(configure_module, configure_attr)
                configure_value = os.getenv(configure_attr, configure_default)

                # turn configure value to int or float after some condition check.
                # cast type string to original type if it exists in the globals().
                if isinstance(configure_value, str) and len(configure_value) > 0 and \
                        not isinstance(configure_default, str):
                    if re.match("^\d+?\.\d+?$", configure_value) is not None:
                        # print("float configure value")
                        try:
                            configure_value = float(configure_value)
                        except Exception as e:
                            print(f"this value can't convert to float! {configure_value}: {e}")
                    elif configure_value.isnumeric():
                        configure_value = int(configure_value)

                # record type of configurations for managing in Configure class.
                # requirement: bool must be checked earlier than int.
                # If not, all of int and bool will be checked as int.
                if isinstance(configure_value, bool):
                    configure_type = DataType.bool
                elif isinstance(configure_value, float):
                    configure_type = DataType.float
                elif isinstance(configure_value, str):
                    configure_type = DataType.string
                elif isinstance(configure_value, int):
                    configure_type = DataType.int
                else:
                    configure_type = None

                    # checking for environment variable of system
                if configure_attr.find('__') == -1 and configure_type is not None:
                    globals()[configure_attr] = configure_value
                    self.__configure_info_list[configure_attr] = configure_type

            except Exception as e:
                # no configure value
                print(f"this is not configure key({configure_attr}): {e}")


def get_configuration(configure_name):
    if configure_name in globals():
        return {
            'name': configure_name,
            'value': str(globals()[configure_name]),
            'type': Configure().configure_info_list[configure_name]
        }
    else:
        return None


def set_configuration(configure_name, configure_value):
    if configure_name in globals():
        globals()[configure_name] = configure_value
        return True
    else:
        return False


def get_all_configurations():
    rs_configuration_list = []

    for configuration_key in Configure().configure_info_list.keys():
        rs_configuration_list.append({
            'name': configuration_key,
            'value': str(globals()[configuration_key]),
            'type': Configure().configure_info_list[configuration_key]
        })

    return rs_configuration_list


Configure()
