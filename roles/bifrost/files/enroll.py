#!/usr/bin/env python
#
# Copyright 2020 UnitedStack (Beijing) CO.,LTD.
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
import json
import logging

import multiprocessing
from multiprocessing.pool import ThreadPool

from ironicclient import client
from ironicclient.common import http
from ironicclient.common import utils

LATEST_VERSION = http.LATEST_VERSION

# use latest version 1.58 for ironic client
# node.create will become to 'avaiable' state when using default version 1.9
# 'enroll' state while using 1.58
kwargs = {
    'os_ironic_api_version': LATEST_VERSION,
    'endpoint': 'http://localhost:7385'
}
ironic = client.get_client(1, **kwargs)

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# use hostname to get ipmi_address, ipmi_port, ipmi_hostname, ipmi_password dict
hostname_ipmi = {}
# use ipmi_address, ipmi_port to get hostname
ipmi_hostname = {}


class BaremetalHost(object):
    def __init__(self, ipmi_address, ipmi_port, uuid):
        self.ipmi_address = ipmi_address + ':' + str(ipmi_port)
        self.uuid = uuid

    def set_hostname(self, hostname):
        self.hostname = hostname.lower()
        name = ironic.node.get(self.uuid).name
        # if name is None, replace name
        if self.hostname != name:
            value = ['name=%(name)s' % {'name': self.hostname.lower()}]
            patch = utils.args_array_to_patch("replace", value)
            ironic.node.update(self.uuid, patch)


# NOTE(Xing Zhang): Set baremetal hosts info from three localtion
# and avoid use 'for' in 'for' in case of large scale cluster
# Just loop two times for every hosts
node_hostname_in_ironic = {}
node_in_ironic = {}


def load_csv(file_path="/etc/bifrost/servers.csv"):
    with open(file_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        out = json.dumps([dict(row) for row in reader])

    global hostname_ipmi, ipmi_hostname

    for server in json.loads(out):
        hostname_ipmi[server['hostname']] = server
        ipmi_hostname[server['ipmi_address'] + ':' + str(server.get('ipmi_port', 623))] = server['hostname']
    if len(hostname_ipmi):
        logging.info('Found {count} node(s) in servers.csv: {hostname}'.format(
            count=len(hostname_ipmi), hostname=' '.join(hostname_ipmi.keys())))
    else:
        logging.error('No node was found in servers.csv, please check it.')
        exit(1)


def update_node_info(node):
    global node_hostname_in_ironic
    global node_in_ironic
    ipmi_address = ironic.node.get(node.uuid).driver_info.get(('ipmi_address'))
    ipmi_port = ironic.node.get(node.uuid).driver_info.get(('ipmi_port'))
    ipmi_uri = ipmi_address + ':' + str(ipmi_port)
    # if node is already in ironic, then update hostname for these nodes; eles delete it.
    if ipmi_uri in ipmi_hostname:
        node_in_ironic[ipmi_uri] = BaremetalHost(ipmi_address, ipmi_port, node.uuid)
        node_in_ironic[ipmi_uri].provision_state = node.provision_state
        node_in_ironic[ipmi_uri].set_hostname(ipmi_hostname[ipmi_uri])
        node_hostname_in_ironic[ipmi_hostname[ipmi_uri]] = node.uuid
    else:
        ironic.node.delete(node.uuid)


def create_node(hostname):
    ipmi_address = hostname_ipmi[hostname]['ipmi_address']
    ipmi_port = hostname_ipmi[hostname]['ipmi_port']
    ipmi_username = hostname_ipmi[hostname]['ipmi_username']
    ipmi_password = hostname_ipmi[hostname]['ipmi_password']

    # create if not in ironic
    if hostname not in node_hostname_in_ironic:
        fields = dict(driver='ipmi',
                      name=hostname,
                      driver_info=[
                          "ipmi_address=%s" % ipmi_address,
                          "ipmi_port=%s" % ipmi_port,
                          "ipmi_username=%s" % ipmi_username,
                          "ipmi_password=%s" % ipmi_password
                      ])
        fields = utils.args_array_to_dict(fields, 'driver_info')
        logging.info('Adding node {hostname} with ipmi_address{ipmi_address} and ipmi_port {ipmi_port} '
                     'to ironic.'.format(hostname=hostname,
                                         ipmi_address=ipmi_address, ipmi_port=ipmi_port))
        new_node = ironic.node.create(**fields)
        node_id = new_node.uuid
    else:
        logging.info('{hostname}({ipmi_address}:{ipmi_port}) is already in ironic, '
                     'automatically update its '
                     'driver_info'.format(hostname=hostname,
                                          ipmi_address=ipmi_address, ipmi_port=ipmi_port))
        patch = []
        node_id = node_hostname_in_ironic[hostname]
        node_info = ironic.node.get(node_id)
        if node_info.driver_info.get('ipmi_address'):
            patch.append({"op": "replace", "path": "/driver_info/ipmi_address", "value": ipmi_address})
        else:
            patch.append({"op": "add", "path": "/driver_info/ipmi_address", "value": ipmi_address})

        if node_info.driver_info.get('ipmi_port'):
            patch.append({"op": "replace", "path": "/driver_info/ipmi_port", "value": ipmi_port})
        else:
            patch.append({"op": "add", "path": "/driver_info/ipmi_port", "value": ipmi_port})

        if node_info.driver_info.get('ipmi_username'):
            patch.append({"op": "replace", "path": "/driver_info/ipmi_username", "value": ipmi_username})
        else:
            patch.append({"op": "add", "path": "/driver_info/ipmi_username", "value": ipmi_username})

        if node_info.driver_info.get('ipmi_password'):
            patch.append({"op": "replace", "path": "/driver_info/ipmi_password", "value": ipmi_password})
        else:
            patch.append({"op": "add", "path": "/driver_info/ipmi_password", "value": ipmi_password})

        ironic.node.update(node_id, patch)

    # Add node info to node extra
    extra_patch = []
    node_extra_info = hostname_ipmi[hostname]
    for key, value in node_extra_info.items():
        extra_patch.append({"op": "add", "path": "/extra/" + key, "value": value})
    ironic.node.update(node_id, extra_patch)


def main():
    load_csv()
    cpu_count = multiprocessing.cpu_count()

    nodes = ironic.node.list()

    if len(nodes):
        logging.info('Found {count} node(s) in ironic, please check these '
                     'host(s) below manually:'.format(count=len(nodes)))
        # exclude node when name is None
        node_info_pool = ThreadPool(int(cpu_count / 2))
        node_info_pool.map(update_node_info, nodes)
        node_info_pool.close()
        node_info_pool.join()
        logging.info('node(s) with ipmi_address: {ipmi_address}'.format(
            ipmi_address=' '.join(node_in_ironic.keys())))

    # create nodes not in ironic
    hostnames = hostname_ipmi.keys()
    if hostnames:
        logging.info('Creating node(s) to ironic...')
        create_pool = ThreadPool(int(cpu_count / 2))
        create_pool.map(create_node, hostnames)
        create_pool.close()
        create_pool.join()
        logging.info('Done.')
    else:
        logging.error('Skip creating because of node not found in servers.csv')

    # Manage node after enroll
    nodes_to_manage = ironic.node.list(provision_state="enroll", fields=["name", "uuid"])
    for node in nodes_to_manage:
        ironic.node.set_provision_state(node.uuid, state='manage')

    nodes_still_enroll = ironic.node.list(provision_state="enroll", fields=["name", "uuid"])
    if len(nodes_still_enroll) > 0:
        logging.error('still have {count} nodes in enroll provision_state,'
                      'manage nodes failed'.format(count=len(nodes_still_enroll)))
        exit(1)


if __name__ == '__main__':
    main()
