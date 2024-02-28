#!/usr/bin/env python

# Copyright 2019 UnitedStack (Beijing) CO.,LTD.
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

import argparse
import datetime
import difflib
import os
import re

try:
    from colorama import Fore
    from colorama import init
    init()
except ImportError:
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description='Inventory files comparison tool'
    )
    parser.add_argument(
        '-o', '--old',
        default=os.path.abspath('/etc/maine/ustack-hosts'),
        help='path of old inventory file'
    )
    parser.add_argument(
        '-n', '--new',
        default=os.path.abspath('/etc/maine/ustack-hosts.rpmnew'),
        help='path of new inventory file'
    )
    parser.add_argument(
        '-g', '--group',
        action='store_true',
        help='Diff groups only'
    )
    parser.add_argument(
        '--merge',
        action='store_true',
        help='Replace CUSTOMIZE BEGIN to CUSTOMIZE END in the new inventory '
             'with the old one')
    return parser.parse_args()


def diff_inventory(old, new, group):
    group_pattern = r"\[.*\]"
    oi = open(old, 'r').read()
    ni = open(new, 'r').read()
    if group:
        oi = re.findall(group_pattern, oi)
        ni = re.findall(group_pattern, ni)
    else:
        oi = oi.splitlines()
        ni = ni.splitlines()

    diff = difflib.unified_diff(oi, ni, fromfile=old, tofile=new, lineterm='')
    diff = color_diff(diff)
    print('\n'.join(diff))


def merge_inventory(old, new):
    CUSTOMIZE_RE = re.compile(
        r'# CUSTOMIZE BEGIN.*# CUSTOMIZE END', re.S)
    oi = open(old, 'r').read()
    ni = open(new, 'r').read()
    old_replacement_range = CUSTOMIZE_RE.search(oi)
    new_replacement_range = CUSTOMIZE_RE.search(ni)
    if old_replacement_range and new_replacement_range:
        with open(new, 'w') as f:
            content = ni.replace(
                new_replacement_range.group(0),
                old_replacement_range.group(0))
            with open(old, 'w') as f:
                f.write(content)
        bak_file_name = (
            old + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '.bak')
        with open(bak_file_name, 'w') as f:
            f.write(oi)
    else:
        print('Stop merging inventories! There must be a CUSTOMIZE block in '
              'both the new file and the old file!')


def color_diff(diff):
    for line in diff:
        if line.startswith('+'):
            yield Fore.GREEN + line + Fore.RESET
        elif line.startswith('-'):
            yield Fore.RED + line + Fore.RESET
        elif line.startswith('@'):
            yield Fore.BLUE + line + Fore.RESET
        else:
            yield line


def main():
    try:
        args = parse_args()
        if args.merge:
            merge_inventory(args.old, args.new)
        else:
            diff_inventory(args.old, args.new, args.group)
    except Exception:
        raise


if __name__ == '__main__':
    main()
