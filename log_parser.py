#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2017 theloop, Inc.
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
"""loopchain docker process log parser"""

import json
import sys

print(f"loopchain log parser")

if len(sys.argv) < 3:
    exit('need params input file output file')

input_file = sys.argv[1]
output_file = sys.argv[2]

print(f"input_file({input_file})")
f = open("./" + input_file, 'r')
out = open("./" + output_file, "a")

while True:
    line = f.readline()
    if not line:
        break

    line_elements = line.split('\t')
    json_data = json.loads(line_elements[2])

    try:
        log_type = json_data['log'].split(" ")[3]
        # TODO getopt 로 옵션 받아서 화면에서 log 재생하는 기능 구현하기
        if log_type in ["DEBUG", "INFO", "SPAM", "WARNING"]:
            # print(f"{log_type}")
            pass
        else:  # print ERROR and Exception
            print(f"{json_data['log']}")
    except IndexError:
        # print(f"there is no loopchain log: ({line})")
        pass

    out.write(json_data['log'] + '\n')

f.close()
out.close()
