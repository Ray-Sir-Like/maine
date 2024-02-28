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

import csv
import yaml

from ironicclient import client

kwargs = {'endpoint': 'http://localhost:7385'}

ironic = client.get_client(1, **kwargs)

nodes = ironic.node.list()

excepted_hosts = []

registered_hosts = []

deployed_hosts = []

unregistered_hosts = []

undeployed_hosts = []

registered_string = """
==================================
All nodes registered successfully!
==================================
"""

deployed_string = """
================================
All nodes deployed successfully!
================================
"""


def parse_csv(csv_path):
    with open(csv_path, 'r') as csv_data:
        reader = csv.DictReader(csv_data)
        out = yaml.safe_dump([dict(row) for row in reader])
    return yaml.safe_load(out)


def main():
    deploying_state = ['wait call-back', 'deploying']

    excepted_nodes = parse_csv('/etc/bifrost/servers.csv')

    for excepted_node in excepted_nodes:
        excepted_hosts.append(excepted_node['ipmi_address'])

    for actual_node in nodes:
        ipmi_address = ironic.node.get(
            actual_node.uuid
        ).driver_info['ipmi_address']

        if ipmi_address in excepted_hosts and \
           actual_node.provision_state == 'enroll' and \
           actual_node.power_state == 'power off':
            registered_hosts.append(ipmi_address)
            print("Node '%s' registered" % ipmi_address)

        elif ipmi_address in excepted_hosts and actual_node.provision_state == 'active':
            deployed_hosts.append(ipmi_address)
            print("Node '%s' deployed" % ipmi_address)

        elif actual_node.provision_state in deploying_state:
            undeployed_hosts.append(ipmi_address)
            print("Node '%s' deploying" % ipmi_address)

        elif actual_node.provision_state == 'deploy failed':
            undeployed_hosts.append(ipmi_address)
            print("Node '%s' deploy failed" % ipmi_address)

    rdu_hosts = registered_hosts + deployed_hosts + undeployed_hosts
    unregistered_hosts = [i for i in excepted_hosts if i not in rdu_hosts]

    if sorted(excepted_hosts) == sorted(registered_hosts):
        print(registered_string)

    elif sorted(excepted_hosts) == sorted(deployed_hosts):
        print(deployed_string)

    print("Unregistered hosts: %s" % unregistered_hosts)

    print("Undeployed hosts: %s" % undeployed_hosts)


if __name__ == '__main__':
    main()
