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
import csv
import os
import re
import yaml


def parse_args():
    parser = argparse.ArgumentParser(
        description='Hosts generator'
    )
    parser.add_argument(
        '-c', '--csv_path',
        default=os.path.abspath('/etc/kolla/config/bifrost/servers.csv'),
        help='path of servers.csv file'
    )
    parser.add_argument(
        '-p', '--port_name',
        default="pxe",
        help='port name in csv file'
    )
    return parser.parse_args()


def parse_csv(csv_path):
    with open(csv_path, 'r') as csv_data:
        reader = csv.DictReader(csv_data)
        out = yaml.safe_dump([dict(row) for row in reader])
    return yaml.safe_load(out)


def parse_hosts(networks, port_name):
    hosts = []
    if port_name == 'pxe':
        port_name += '_address'
    for row in networks:
        with open('/etc/hosts', 'r') as f:
            content = f.read()
        if not re.search(row['hostname'], content):
            hosts.append(
                row[port_name] + ' ' + row['hostname'] + '\n'
            )
    with open('/etc/hosts', 'a') as f:
        for host in hosts:
            f.write(host)


def main():
    args = parse_args()
    networks = parse_csv(args.csv_path)
    parse_hosts(networks, args.port_name)


if __name__ == '__main__':
    main()
