#!/usr/bin/env python
#
# Copyright 2018-2020 UnitedStack (Beijing) CO.,LTD.
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

import logging

from ironicclient import client

import ironic_inspector_client as inspector_client

from keystoneauth1 import session as ks_session
from keystoneauth1 import token_endpoint

kwargs = {'endpoint': 'http://localhost:7385'}
ironic = client.get_client(1, **kwargs)

auth = token_endpoint.Token(endpoint='http://localhost:7050',
                            token='fake=token')
session = ks_session.Session(auth)
inspector_client = inspector_client.ClientV1(session=session)

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


node_state_in_ironic = {}
# set baremetal hosts info from ironic
for node in ironic.node.list():
    node_state_in_ironic[node.uuid] = node.provision_state


def main():
    node_introspect_unfinished_num = 0
    node_introspect_finished = list()
    node_introspect_errors = dict()
    has_error = False

    # Don't provide introspect error nodes, inspect node again
    introspect_statuses = inspector_client.list_statuses()
    for status in introspect_statuses:
        if status['state'] == 'finished':
            node_introspect_finished.append(status['uuid'])
        if status['state'] != 'finished':
            node_introspect_unfinished_num += 1
        if status['state'] == 'error':
            node_introspect_errors[status['uuid']] = status['state']

    # provide nodes
    for node_uuid in node_introspect_finished:
        if node_uuid not in node_state_in_ironic:
            logging.warn('introspect node {uuid} does not '
                         'exist in ironic'.format(uuid=node_uuid))
            continue

        node_state = node_state_in_ironic[node_uuid]
        # if node in clean failed state, setting it to manageable first
        if node_state == 'clean failed':
            ironic.node.set_provision_state(
                node_uuid, state='manage')
            ironic.node.set_maintenance(
                node_uuid, state='false')
            ironic.node.wait_for_provision_state(
                node_uuid, 'manageable', timeout=10)
            ironic.node.set_provision_state(
                node_uuid, state='provide')

        if node_state == 'manageable':
            ironic.node.set_provision_state(
                node_uuid, state='provide')

    if len(node_introspect_errors) > 0:
        has_error = True
        for (uuid, error) in node_introspect_errors.items():
            logging.error('Node {uuid} introspection failed, '
                          'reason: {reason}'.format(uuid=uuid,
                                                    reason=error))

    if node_introspect_unfinished_num > 0:
        has_error = True
        logging.warning('Still {count} nodes do not finish '
                        'introspect. Please wait for '
                        'them'.format(count=node_introspect_unfinished_num))

    if has_error:
        exit(1)


if __name__ == '__main__':
    main()
