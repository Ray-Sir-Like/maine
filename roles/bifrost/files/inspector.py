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


def main():
    nodes = ironic.node.list()
    for node in nodes:
        state = node.provision_state
        if state == 'manageable' or state == 'inspect failed':
            inspector_client.introspect(node.uuid)


if __name__ == '__main__':
    main()
