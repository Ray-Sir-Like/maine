#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2014-2015 Red Hat, Inc.
# Copyright 2019 Zijian Guo <guozijian@unitedstack.com>
# Copyright 2019 UnitedStack
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

from __future__ import print_function


ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'unitedstack'
}


DOCUMENTATION = '''
---
module: uos_net_config
author: "Zijian Guo <guozijian@unitedstack.com>"
short_description: Manage Networking
requirements: [ openvswitch, os-net-config ]
version_added: "1.0"
description:
    - Manage the network configuration.
options:
    network_config:
        description:
            - Network topology.
            - You can use host vars to replace the IP address variable.
        type: list
        required: True
    provider:
        description:
            - The provider to use.
        type: str
        required: False
        choices: ['ifcfg', 'eni', 'iproute']
    root_dir:
        description:
            - The root directory of the filesystem.
        type: str
        required: False
    detailed_exit_codes:
        description:
            - Enable detailed exit codes.
            - If enabled an exit code of '2' means that files were modified.
            - Disabled by default.
        type: bool
        required: False
    exit_on_validation_errors:
        description:
            - Exit with an error if configuration file validation fails.
        type: bool
        required: False
    debug:
        description:
            - Print debugging output.
        type: bool
        required: False
    verbose:
        description:
            - Print verbose output.
        type: bool
        required: False
    noop:
        description:
            - Return the configuration commands, without applying them.
        type: bool
        required: False
    no_activate:
        description:
            - Install the configuration but don't start/stop interfaces.
        type: bool
        required: False
    cleanup:
        description:
            - Cleanup unconfigured interfaces.
        type: bool
        required: False

'''

EXAMPLES = '''
---
network_config:
  - type: interface
    mtu: "{{ pxe_mtu }}"
    name: eth1
    addresses:
      - ip_netmask: "{{ pxe_address }}/24"
  - type: ovs_bridge
    name: br-ex
    mtu: "{{ service_mtu }}"
    members:
      - type: linux_bond
        name: bond0
        bonding_options: "mode=1 miimon=100"
        mtu: "{{ service_mtu }}"
        members:
          - type: interface
            name: eth2
            mtu: "{{ service_mtu }}"
          - type: interface
            name: eth3
            mtu: "{{ service_mtu }}"
      - type: vlan
        vlan_id: 2003
        mtu: "{{ service_mtu }}"
        addresses:
          - ip_netmask: "{{ vlan2003 }}/24"
      - type: vlan
        vlan_id: 2004
        mtu: "{{ service_mtu }}"
        addresses:
          - ip_netmask: "{{ vlan2004 }}/24"
      - type: vlan
        vlan_id: 2005
        mtu: "{{ service_mtu }}"
        addresses:
          - ip_netmask: "{{ vlan2005 }}/24"
      - type: vlan
        vlan_id: 2006
        mtu: "{{ service_mtu }}"
        addresses:
          - ip_netmask: "{{ vlan2006 }}/24"
        routes:
          - ip_netmask: 0.0.0.0/0
            next_hop: "{{ gateway }}"
            default: true
      - type: vlan
        vlan_id: 2007
        mtu: "{{ service_mtu }}"
        addresses:
          - ip_netmask: "{{ vlan2007 }}/24"
      - type: vlan
        vlan_id: 2009
        mtu: "{{ service_mtu }}"
        addresses:
          - ip_netmask: "{{ vlan2009 }}/24"

'''

from ansible.module_utils.basic import AnsibleModule
import fileinput
import glob
import json
import logging
import os

from os_net_config import impl_eni
from os_net_config import impl_ifcfg
from os_net_config import impl_iproute
from os_net_config import objects
from os_net_config import utils
from os_net_config import validator
import sys

logger = logging.getLogger(__name__)

STR_PREFIX = "# This file is autogenerated by "
OSC_STRING = STR_PREFIX + "os-net-config"
UOSC_STRING = STR_PREFIX + "uos_net_config, It is recommended not to modify it"

IFCFG_GLOBS = [
    '/etc/network/interfaces',
    '/etc/sysconfig/network-scripts/ifcfg-*'
]


def check_configure_sriov(obj):
    configure_sriov = False
    for member in obj.members:
        if isinstance(member, objects.SriovPF):
            configure_sriov = True
        elif hasattr(member, "members") and member.members is not None:
            configure_sriov = check_configure_sriov(member)
    return configure_sriov


def replace_osc_string(file_glob, src, dest):
    files = glob.glob(file_glob)
    if len(files) > 0:
        for f in files:
            for line in fileinput.FileInput(f, inplace=1):
                line = line.replace(src, dest)
                sys.stdout.write(line)


class UOSNetConfig(object):
    def __init__(self, module):
        self.module = module
        self.network_config = json.loads(module.params['network_config'])
        self.provider = module.params['provider']
        self.root_dir = module.params['root_dir']
        self.log_file = module.params['log_file']
        self.detailed_exit_codes = module.params['detailed_exit_codes']
        self.exit_on_validation_errors = \
            module.params['exit_on_validation_errors']
        self.debug = module.params['debug']
        self.verbose = module.params['verbose']
        self.noop = module.params['noop']
        self.no_activate = module.params['no_activate']
        self._cleanup = module.params['cleanup']

    @property
    def cleanup(self):
        return self._cleanup

    def configure_logger(self, verbose=False, debug=False):
        LOG_FORMAT = '[%(asctime)s] [%(levelname)s] %(message)s'
        DATE_FORMAT = '%Y/%m/%d %I:%M:%S %p'
        log_level = logging.WARN

        if debug:
            log_level = logging.DEBUG
        elif verbose:
            log_level = logging.INFO

        logging.basicConfig(
            format=LOG_FORMAT,
            datefmt=DATE_FORMAT,
            level=log_level,
            filename=self.log_file,
            filemode='w')

    def apply(self):
        self.configure_logger(self.verbose, self.debug)
        logger.info('Using config: %s' % self.network_config)
        iface_array = []
        configure_sriov = False
        provider = None

        if self.provider:
            if self.provider == 'ifcfg':
                provider = impl_ifcfg.IfcfgNetConfig(noop=self.noop,
                                                     root_dir=self.root_dir)
            elif self.provider == 'eni':
                provider = impl_eni.ENINetConfig(noop=self.noop,
                                                 root_dir=self.root_dir)
            elif self.provider == 'iproute':
                provider = impl_iproute.IPRouteNetConfig(
                    noop=self.noop,
                    root_dir=self.root_dir
                )
            else:
                logger.error('Invalid provider specified.')
                return 1
        else:
            ifcfg_dir = "/etc/sysconfig/network-scripts/"
            if os.path.exists('%s%s' % (self.root_dir, ifcfg_dir)):
                provider = impl_ifcfg.IfcfgNetConfig(noop=self.noop,
                                                     root_dir=self.root_dir)
            elif os.path.exists('%s/etc/network/' % self.root_dir):
                provider = impl_eni.ENINetConfig(noop=self.noop,
                                                 root_dir=self.root_dir)
            else:
                logger.error('Unable to set provider for this \
                operating system.')
                return 1

        iface_array = self.network_config

        if not isinstance(iface_array, list):
            logger.error(
                'No interfaces defined in config: %s' % self.network_config
            )
            return 1

        validation_errors = validator.validate_config(iface_array)
        if validation_errors:
            if self.exit_on_validation_errors:
                logger.error('\n'.join(validation_errors))
                return 1
            else:
                logger.warning('\n'.join(validation_errors))

        # Look for the presence of SriovPF types in the first parse of the json
        # if SriovPFs exists then PF devices needs to be configured so that the
        # VF devices are created.
        # The VFs will not be available now and an exception
        # SriovVfNotFoundException will be raised while fetching the device
        # name.
        # After the first parse the SR-IOV PF devices would be configured and
        # the VF devices would be created.
        # In the second parse, all other objects shall be added
        for iface_json in iface_array:
            try:
                obj = objects.object_from_json(iface_json)
            except utils.SriovVfNotFoundException:
                continue
            if isinstance(obj, objects.SriovPF):
                configure_sriov = True
                provider.add_object(obj)
            elif hasattr(obj, 'members') and obj.members is not None:
                if check_configure_sriov(obj):
                    configure_sriov = True
                    provider.add_object(obj)

        if configure_sriov:
            # Apply the ifcfgs for PFs now, so that NM_CONTROLLED=no is applied
            # for each of the PFs before configuring the numvfs for the PF
            # device.
            # This step allows the network manager to unmanage the created VFs.
            # In the second parse, when these ifcfgs for PFs are encountered,
            # os-net-config skips the ifup <ifcfg-pfs>, since the ifcfgs for
            # PFs wouldn't have changed.
            pf_files_changed = provider.apply(cleanup=self.cleanup,
                                              activate=not self.no_activate)
            if not self.noop:
                utils.configure_sriov_pfs()

        for iface_json in iface_array:
            # All objects other than the sriov_pf will be added here.
            # The VFs are expected to be available now and an exception
            # SriovVfNotFoundException shall be raised if not available.
            try:
                obj = objects.object_from_json(iface_json)
            except utils.SriovVfNotFoundException:
                if not self.noop:
                    raise
            if not isinstance(obj, objects.SriovPF):
                provider.add_object(obj)

        if configure_sriov and not self.noop:
            utils.configure_sriov_vfs()

        files_changed = provider.apply(cleanup=self.cleanup,
                                       activate=not self.no_activate)

        logger.info("files_changed: %s" % [k for k, v in files_changed.items()])

        if self.noop:
            if configure_sriov:
                files_changed.update(pf_files_changed)
            for location, data in files_changed.items():
                print("File: %s\n" % location)
                print(data)
                print("----")

        if self.detailed_exit_codes and len(files_changed) > 0:
            return 2

        return 0


def main():
    module = AnsibleModule(
        argument_spec=dict(
            network_config=dict(required=True, type='str'),
            provider=dict(
                required=False,
                choices=['ifcfg', 'eni', 'iproute'],
                type='str'),
            root_dir=dict(required=False, default='', type='str'),
            log_file=dict(
                required=False,
                default='/var/log/uos_net_config.log',
                type='str'),
            detailed_exit_codes=dict(
                required=False,
                default=True,
                type='bool'),
            exit_on_validation_errors=dict(
                required=False,
                default=False,
                type='bool'),
            debug=dict(required=False, default=False, type='bool'),
            verbose=dict(required=False, default=False, type='bool'),
            noop=dict(required=False, default=False, type='bool'),
            no_activate=dict(required=False, default=False, type='bool'),
            cleanup=dict(required=False, default=False, type='bool'),
        ),
        supports_check_mode=True
    )

    result = {
        'changed': False,
        'rc': 0,
        'stdout': '',
        'stderr': ''
    }

    for ig in IFCFG_GLOBS:
        replace_osc_string(ig, UOSC_STRING, OSC_STRING)

    config = UOSNetConfig(module)
    rc = config.apply()

    for ig in IFCFG_GLOBS:
        replace_osc_string(ig, OSC_STRING, UOSC_STRING)

    with open('/var/log/uos_net_config.log', 'r') as f:
        out = f.read()

    if config.cleanup:
        result['changed'] = True

    if rc == 2:
        (result['changed'], result['stdout']) = (True, out)
    elif rc == 1:
        (result['rc'], result['stderr']) = (rc, out)
    else:
        result['stdout'] = out

    module.exit_json(**result)


if __name__ == '__main__':
    main()
