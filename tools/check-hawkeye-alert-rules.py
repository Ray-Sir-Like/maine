#!/usr/bin/env python
# Copyright 2018 The Hawkeye Authors. All rights reserved.
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
import sys

import yaml


def validate_rule(f_path):
    content = None
    with open(f_path, 'r') as f:
        content = yaml.safe_load(f)
    if content:
        if 'groups' in content:
            for group in content['groups']:
                if not group.get('name'):
                    return 'failed'
                rules = group.get('rules')
                if not rules:
                    return 'failed'
                for rule in rules:
                    if not rule.get('alert'):
                        return 'failed'
                    if not rule.get('enabled'):
                        return 'failed'
                    if not rule.get('expr'):
                        return 'failed'
                    labels = rule.get('labels')
                    if not labels:
                        return 'failed'
                    if not labels.get('severity'):
                        return 'failed'
                    if not labels.get('service'):
                        return 'failed'
                    annotations = rule.get('annotations')
                    if not annotations:
                        return 'failed'
                    if not annotations.get('description'):
                        return 'failed'
    return 'ok'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rule-file", help="hawkeye alert file")
    args = parser.parse_args()
    if args.rule_file:
        print("check alert file: %s" % args.rule_file)
        result = validate_rule(args.rule_file)
        if result != 'ok':
            print("alert file: %s is invalid" % args.rule_file)
            sys.exit(1)


if __name__ == '__main__':
    main()
