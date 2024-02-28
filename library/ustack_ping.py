#!/usr/bin/python

# Copyright 2019 unitedstack
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

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'UnitedStack'
}

DOCUMENTATION = '''
---
module: ustack_ping

short_description: This is ping network module

version_added: "2.4"

description:
    - "This is my longer description explaining ping network module"

options:
    name:
        description:
            - This is the message to send to the ping network module
        required: true
    new:
        description:
            - Control to demo if the result of this module is changed or not
        required: false

author:
    - Ning Yao
'''

EXAMPLES = '''
# Pass in a message
- name: Test with a ping
  ustack_ping:
    ipaddr: 10.0.81.11
    nic: storage
    count: 10
    interval: 0.2
    mtu: 9000
'''

RETURN = '''
message:
    min_lat: str
    avg_lat: str
    max_lat: str
    loss: str
'''

from ansible.module_utils.basic import AnsibleModule
from subprocess import PIPE
from subprocess import Popen


def run_ping(ipaddr, nic, count, interval, mtu):
    ping_cmd = ["ping", "-M", "do", "-c", str(count), "-i", str(interval),
                "-s", str(mtu-28), str(ipaddr)]
    if nic:
        ping_cmd.append("-I")
        ping_cmd.append(str(nic))

    process = Popen(ping_cmd, stdout=PIPE, stderr=PIPE, env={"LANG": "en_US.UTF-8"})
    output = process.communicate()[0]
    exit_code = process.returncode

    if exit_code > 0:
        return 0, 0, 0, 0, exit_code

    outputs = output.split(b'\n')
    latency = outputs[-2].split(b'=')[1].split(b'/')
    loss = outputs[-3].split(b',')[2].split(b'%')[0]

    return float(latency[0]), float(latency[0]), float(latency[0]), float(loss), exit_code


def main():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        ipaddr=dict(type='str', required=True),
        nic=dict(type='str', required=False, default=False),
        count=dict(type='int', required=False, default=10),
        interval=dict(type='float', required=False, default=0.2),
        mtu=dict(type='int', required=False, default=1500),
        allowed_avg=dict(type='float', required=False, default=0.200),
        allowed_max=dict(type='float', required=False, default=0.300),
        allowed_loss=dict(type='float', required=False, default=0.0))

    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=True,
        min_lat='',
        avg_lat='',
        max_lat='',
        loss=''
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    min_lat, avg_lat, max_lat, loss, exit_code = run_ping(
        module.params.get('ipaddr'),
        module.params.get('nic'),
        module.params.get('count'),
        module.params.get('interval'),
        module.params.get('mtu'))

    result['min_lat'] = min_lat
    result['avg_lat'] = avg_lat
    result['max_lat'] = max_lat
    result['loss'] = loss

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    # during the execution of the module, if there is an exception or a
    # conditional state that effectively causes a failure, run
    # AnsibleModule.fail_json() to pass in the message and the result
    if exit_code > 0:
        module.fail_json(msg='ping --> %s cannot reach'
                         % module.params.get('ipaddr'), **result)

    if result['loss'] > module.params.get('allowed_loss'):
        module.fail_json(msg='ping --> %s , package loss %s > %s'
                         % (module.params.get('ipaddr'),
                            str(result['loss']),
                            str(module.params.get('allowed_loss'))), **result)

    if result['avg_lat'] > module.params.get('allowed_avg'):
        module.fail_json(msg='ping --> %s , average latency %s > %s'
                         % (module.params.get('ipaddr'),
                            str(result['avg_lat']),
                            str(module.params.get('allowed_avg'))), **result)

    if result['max_lat'] > module.params.get('allowed_max'):
        module.fail_json(msg='ping --> %s , average latency %s > %s'
                         % (module.params.get('ipaddr'),
                            str(result['max_lat']),
                            str(module.params.get('allowed_max'))), **result)

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)


if __name__ == '__main__':
    main()
