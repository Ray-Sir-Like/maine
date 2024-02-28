#!/usr/bin/env python

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
import hmac
import os
import sys

from cryptography import fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography import x509
from cryptography.x509.oid import NameOID
from hashlib import md5
from oslo_utils import uuidutils
import passlib.pwd
import yaml

# NOTE(SamYaple): Update the search path to prefer PROJECT_ROOT as the source
#                 of packages to import if we are using local tools instead of
#                 pip installed kolla tools
PROJECT_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def generate_RSA(bits=4096):
    new_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=bits,
        backend=default_backend()
    )
    private_key = new_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()
    public_key = new_key.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH
    ).decode()
    return private_key, public_key


def generate_selfcert(bits=2048):
    new_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=bits,
        backend=default_backend()
    )
    key = new_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"CN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"BJ"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"BJ"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"TFCloud"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"UUS"),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject,
    ).issuer_name(
        issuer,
    ).public_key(
        new_key.public_key(),
    ).serial_number(
        x509.random_serial_number(),
    ).not_valid_before(
        datetime.datetime.utcnow(),
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=36500),
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName(u"localhost")]),
        critical=False,
    ).sign(
        new_key,
        hashes.SHA256(),
        default_backend(),
    ).public_bytes(
        serialization.Encoding.PEM,
    ).decode()
    return key, cert


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-p', '--passwords', type=str,
        default=os.path.abspath('/etc/maine/passwords.yml'),
        help=('Path to the passwords.yml file'))

    args = parser.parse_args()
    passwords_file = os.path.expanduser(args.passwords)

    # These keys should be random uuids
    uuid_keys = ['ceph_cluster_fsid',
                 'rbd_secret_uuid',
                 'cinder_rbd_secret_uuid',
                 'gnocchi_project_id',
                 'gnocchi_resource_id',
                 'gnocchi_user_id',
                 'designate_pool_id',
                 'octavia_amp_flavor_id',
                 'karbor_openstack_infra_id']

    # SSH key pair
    ssh_keys = ['kolla_ssh_key', 'nova_ssh_key',
                'keystone_ssh_key', 'octavia_ssh_key',
                'bifrost_ssh_key', 'juggernaut_ssh_key']

    # If these keys are None, leave them as None
    blank_keys = ['docker_registry_password']

    # HMAC-MD5 keys
    hmac_md5_keys = ['designate_rndc_key',
                     'osprofiler_secret']

    # Fernet keys
    fernet_keys = ['barbican_crypto_key', 'swallow_crypto_key']

    # length of password
    length = 40

    # self-signed certificate
    self_certs = ['lulu_selfcert']

    # Pacemaker remote authkey
    pcs_remote_keys = ['pacemaker_remote_authkey']

    with open(passwords_file, 'r') as f:
        passwords = yaml.safe_load(f.read())

    for k, v in passwords.items():
        if (k in ssh_keys
                and (v is None
                     or v.get('public_key') is None
                     and v.get('private_key') is None)):
            private_key, public_key = generate_RSA()
            passwords[k] = {
                'private_key': private_key,
                'public_key': public_key
            }
            continue
        if (k in self_certs
                and (v is None
                     or v.get('key') is None
                     and v.get('cert') is None)):
            key, cert = generate_selfcert()
            passwords[k] = {
                'key': key,
                'cert': cert
            }
            continue
        if k in pcs_remote_keys and v is None:
            passwords[k] = passlib.pwd.genword(length=4096)
            continue
        if v is None:
            if k in blank_keys and v is None:
                continue
            if k in uuid_keys:
                passwords[k] = uuidutils.generate_uuid()
            elif k in hmac_md5_keys:
                passwords[k] = (hmac.new(
                    uuidutils.generate_uuid().encode(), ''.encode(), md5)
                    .hexdigest())
            elif k in fernet_keys:
                passwords[k] = fernet.Fernet.generate_key()
            else:
                passwords[k] = passlib.pwd.genword(length=length)

    with open(passwords_file, 'w') as f:
        f.write(yaml.safe_dump(passwords, default_flow_style=False))


if __name__ == '__main__':
    main()
