#!/bin/bash -xe
set -o errexit

: ${OPT_PATTERN:='set=smoke'}
: ${OPT_CONCURRENCY:=2}
: ${OPT_PIP_URL:='https://mirror01.ustack.com/pypi/simple'}
: ${OPT_INITIALIZE:=1}
: ${OPT_TEST:=1}
: ${OPT_HA_TEST:=0}
: ${OPT_PIP_EXEC:=python3 -m pip}

OPT_PYTHON_VERSION=$(ssh ci "docker exec -u root rally python3 -c 'import sys; print(str(sys.version_info[0])+\".\"+str(sys.version_info[1]))'")

function usage {
    echo "Basic options:"
    echo "  -p, --pattern"
    echo "                      patterns of running openstack tempest"
    echo "  -c, --concurrency"
    echo "                      workers of running openstack tempest"
    echo "  -i, --initialize"
    echo "                      whether or not enable initialize openstack for ci"
    echo "                      1 for yes, 0 for no, default is 1"
    echo "  -t, --test"
    echo "                      whether or not enable running tempest"
    echo "                      1 for yes, 0 for no, default is 1"
    echo "  -h, --help          print this help and exit"
}

cat <<EOBANNER
----------------------------------------------------------------------------
|                                ,   .   ,                                 |
|                                )-_'''_-(                                 |
|                               ./ o\ /o \.                                |
|                              . \__/ \__/ .                               |
|                              ...   V   ...                               |
|                              ... - - - ...                               |
|                               .   - -   .                                |
|                                \`-.....-´                                |
|                                         _____                            |
|                           | |  | |     / ____|                           |
|                           | |  | | ___ \ \___                            |
|                           | |  | |/ _ \ \__  |                           |
|                           | |__| | |_| |___| |                           |
|                            \____/ \___/ \____/                           |
|                                                                          |
|                                                                          |
----------------------------------------------------------------------------

EOBANNER

EXTRAS_OPTS=()
while [ "x$1" != "x" ]; do
    case "$1" in
        --pattern|-p)
            OPT_PATTERN=$2
            shift
            ;;
        --concurrency|-c)
            OPT_CONCURRENCY=$2
            shift
            ;;
        --initialize|-i)
            OPT_INITIALIZE=$2
            shift
            ;;
        --test|-t)
            OPT_TEST=$2
            shift
            ;;
        --ha)
            OPT_HA_TEST=$2
            shift
            ;;
        --help)
            usage
            exit
            ;;

        --) shift
            break
            ;;

        *)
            EXTRAS_OPTS+=("$1" "$2")
            shift
            ;;
    esac

    shift
done

collect_deployment_configs () {
    deployed_services=`ssh control2 "source admin-openrc && openstack service list -f value -c Name"`
}

prepare_tempest () {
# Know issues:
# Temporary remove watcher and congress due to bug, see:
# https://review.opendev.org/702586 Fix skipping of tests
# https://review.opendev.org/702587 Fix skipping of tests
    ssh ci << EOF
#!/bin/bash -xe
set -o errexit

dnf update systemd -y

. admin-openrc

# NOTE(Xing Zhang): python clients in wallaby conflicts with antelope that
# installed from pip
docker exec -u root rally dnf remove python3-distlib -y

# dependency
docker exec -u root rally $OPT_PIP_EXEC install pip -i ${OPT_PIP_URL} --upgrade
docker exec -u root rally $OPT_PIP_EXEC config set global.index-url ${OPT_PIP_URL}
docker exec -u root rally $OPT_PIP_EXEC config set global.constraint https://git-mirror.ustack.com/cgit/openstack/requirements/plain/upper-constraints.txt?h=stable/zed
docker exec -u root rally $OPT_PIP_EXEC install wheel -U

docker exec -u root rally dnf install crudini gcc gcc-c++ nc ipmitool -y

# tempest > 27 need commit: eba9341bf980992f1659fe1aa89063cf604c3470
docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/rally-openstack.git -U --force-reinstall

docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/tempest.git@8def25cbb5885e91899793f8575d3919816a0d12

# HACK(guozijian): invalid interpolation
docker exec -u root rally sed "s/^    conf_object = configparser.ConfigParser()$/    conf_object = configparser.RawConfigParser()/" -i /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/rally/verification/utils.py
docker exec -u root rally sed "s/^        self.conf = configparser.ConfigParser(allow_no_value=True)/        self.conf = configparser.RawConfigParser(allow_no_value=True)/" -i /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/rally_openstack/verification/tempest/config.py

#HACK(wangdaoyuan): up timeout
docker exec -u root rally sed "s/^    def __init__(self, host, username, password=None, timeout=300, pkey=None,$/    def __init__(self, host, username, password=None, timeout=600, pkey=None,/" -i /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/tempest/lib/common/ssh.py

# tempest plugin
if [[ "$deployed_services" =~ "cinder" ]]; then
    docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/cinder-tempest-plugin.git@wallaby-last
fi

if [[ "$deployed_services" =~ "cloudkitty" ]]; then
    docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/cloudkitty-tempest-plugin.git@wallaby-last
    docker exec -u root rally sed -i "s/302/204/g" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/cloudkitty_tempest_plugin/services/client.py
    docker exec -u root rally rm -rf /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/cloudkitty_tempest_plugin/services/__pycache__
    docker exec -u root rally rm -rf /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/cloudkitty_tempest_plugin/services/*.pyc
fi

if [[ "$deployed_services" =~ "designate" ]]; then
    docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/designate-tempest-plugin.git@wallaby-last
fi

if [[ "$deployed_services" =~ "heat" ]]; then
    docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/heat-tempest-plugin.git@wallaby-last
    # setting default timeout in heat stack
    docker exec -u root rally sed -i "s/default: 120/default: 300/g" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/heat_tempest_plugin/tests/scenario/templates/lb_member.yaml
    docker exec -u root rally sed -i "s/default: \[\"8.8.8.8\", \"8.8.4.4\"\]/default: \[\"10.0.218.41\", \"10.0.218.42\", \"10.0.218.43\"\]/g" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/heat_tempest_plugin/tests/scenario/templates/test_server_signal.yaml
    docker exec -u root rally sed -i "/region_name/a\        insecure: True" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/heat_tempest_plugin/tests/scenario/templates/remote_nested_root.yaml
fi

if [[ "$deployed_services" =~ "keystone" ]]; then
    docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/keystone-tempest-plugin.git@wallaby-last
fi

if [[ "$deployed_services" =~ "senlin" ]]; then
    docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/senlin-tempest-plugin.git@wallaby-last
    docker exec -u root rally sed -i "s/\"flavor\": \"1\"/\"flavor\": \"rally_flavor\"/g" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/senlin_tempest_plugin/common/constants.py
    docker exec -u root rally sed -i "s/\"image\": \"cirros-0.4.0-x86_64-disk\"/\"image\": \"CentOS 7\"/g" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/senlin_tempest_plugin/common/constants.py
    docker exec -u root rally sed -i "s/\"network\": \"private\"/\"network\": \"rally-net\"/g" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/senlin_tempest_plugin/common/constants.py
    docker exec -u root rally sed -i "s/\"subnet\": \"private-subnet\"/\"subnet\": \"rally-subnet\"/g" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/senlin_tempest_plugin/common/constants.py
    docker exec -u root rally sed -i "s/\"number\": 20/\"number\": 5/g" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/senlin_tempest_plugin/tests/api/clusters/test_cluster_resize.py
    docker exec -u root rally sed -i "s/wait_timeout=10/wait_timeout=240/g" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/senlin_tempest_plugin/tests/functional/test_deletion_policy.py
    docker exec -u root rally sed -i "102i \        import time;time.sleep(5)" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/senlin_tempest_plugin/tests/functional/test_deletion_policy.py
    docker exec -u root rally sed -i "s/metadata={'simulated_wait_time': 10}//g" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/senlin_tempest_plugin/tests/api/clusters/test_cluster_scale_out.py
    docker exec -u root rally sed -i "s/REBUILD/REBOOT/g" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/senlin_tempest_plugin/tests/api/nodes/test_node_recover.py
    docker exec -u root rally bash -c 'sed -i "s/new_flavor/rally_flavor_alt/" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/senlin_tempest_plugin/tests/api/nodes/*.py'
    docker exec -u root rally bash -c 'sed -i "s/new_image/CentOS 7/" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/senlin_tempest_plugin/tests/api/nodes/*.py'
    docker exec -u root rally bash -c 'sed -i "s/new_flavor/rally_flavor_alt/" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/senlin_tempest_plugin/tests/api/clusters/*.py'
    docker exec -u root rally bash -c 'sed -i "s/new_image/CentOS 7/" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/senlin_tempest_plugin/tests/api/clusters/*.py'
fi

if [[ "$deployed_services" =~ "ironic" ]]; then
    docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/ironic-tempest-plugin.git@wallaby-last
fi

if [[ "$deployed_services" =~ "barbican" ]]; then
    docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/barbican-tempest-plugin.git@e5ed4b9f1e6b2843c48b0df56a71cdb185004ef7
fi

if [[ "$deployed_services" =~ "manila" ]]; then
    docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/manila-tempest-plugin.git@7a43ca04127cfe7f13a0a7d2ec5dd43b04d7a88c
fi

if [[ "$deployed_services" =~ "mistral" ]]; then
    docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/mistral-tempest-plugin.git@wallaby-last
fi

if [[ "$deployed_services" =~ "neutron" ]]; then
    docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/neutron-tempest-plugin.git@wallaby-last

    # HACK: https://review.opendev.org/#/c/743682/
    docker exec -u root rally sed "/        # Delete firewall_group/a\        import time;time.sleep(10)\n        self.firewall_groups_client.update_firewall_group(fwg_id,ports=\[\])\n        import time;time.sleep(10)" -i /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/neutron_tempest_plugin/fwaas/api/test_fwaasv2_extensions.py
fi

if [[ "$deployed_services" =~ "octavia" ]]; then
    docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/octavia-tempest-plugin.git@wallaby-last
    docker exec -u root rally sed -i "/master_amp\[const.COMPUTE_ID\])/a\        time.sleep(60)" /var/lib/kolla/venv/lib/python$OPT_PYTHON_VERSION/site-packages/octavia_tempest_plugin/tests/act_stdby_scenario/v2/test_active_standby.py
fi

if [[ "$deployed_services" =~ "zaqar" ]]; then
    docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/zaqar-tempest-plugin.git@wallaby-last
fi

if [[ "$deployed_services" =~ "masakari" ]]; then
    docker exec -u root rally $OPT_PIP_EXEC install git+https://git.ustack.com/openstack/masakari-tempest-plugin.git@master
fi

if [[ "$deployed_services" =~ "aodh" || "$deployed_services" =~ "ceilometer" ]]; then
    docker exec -u root rally $OPT_PIP_EXEC install git+https://git-mirror.ustack.com/openstack/telemetry-tempest-plugin.git@wallaby-last
fi

# install unitedstack-tempest-plugin
docker exec -u root rally $OPT_PIP_EXEC install git+https://git.ustack.com/openstack/unitedstack-tempest-plugin@master

# sync all hacker
docker exec -u root rally sync
sync

EOF
}

initialize_openstack_for_ci () {
    ssh control2 << EOF
#!/bin/bash -xe
set -o errexit

. admin-openrc
# create openstack network for rally
openstack network create --share rally-net
openstack subnet create --subnet-range 10.0.100.0/24 --ip-version 4 --network rally-net rally-subnet

# create heat-net network for heat-tempest-plugin
openstack network create heat-net
openstack subnet create --subnet-range 10.0.200.0/24 --ip-version 4 --network heat-net heat-subnet
openstack router create heat-router
openstack router set heat-router --external-gateway public
openstack router add subnet heat-router heat-subnet

# create openstack flavor for rally
openstack flavor create --ram 512 --vcpus 1 --disk 4 rally_flavor
openstack flavor create --ram 1024 --vcpus 2 --disk 4 rally_flavor_alt

# create heat flavor for heat-tempest-plugin
openstack flavor create --ram 512 --vcpus 1 --disk 4 rally_heat_min
openstack flavor create --ram 1024 --vcpus 2 --disk 4 rally_heat

# Update image min_size
openstack image set --min-disk 3 "CentOS 7"

EOF
}

run_test () {
    ssh ci << EOF
#!/bin/bash -xe
set -o errexit

# 拷贝 openrc 文件到容器
docker cp admin-openrc rally:/var/lib/rally/

# 修改 openrc 文件的权限
docker exec -u root rally chown rally:rally /var/lib/rally/admin-openrc

# Note(Yao Ning): Don't use internal tls now
#docker exec -u root rally sed -i 's#/etc/kolla/haproxy/haproxy-internal.pem#/etc/pki/ca-trust/source/anchors/kolla-customca-haproxy.crt#g' /var/lib/rally/admin-openrc

# 创建 .ssh 目录给 mistral 测试使用
docker exec rally mkdir -p /var/lib/rally/.ssh/

# 运行测试
docker exec rally bash -x /var/log/kolla/rally/run.sh --detailed --skip-list /var/log/kolla/rally/skip-list.yaml --concurrency ${OPT_CONCURRENCY} --pattern ${OPT_PATTERN}

EOF

}

run_ha_test () {
    ssh ci << EOF
#!/bin/bash -xe
set -o errexit

docker exec rally rally verify start --id remote --detailed --pattern "masakari_tempest_plugin.tests"

EOF

}

collect_deployment_configs
prepare_tempest
if [[ ${OPT_INITIALIZE} -eq 1 ]]; then
    initialize_openstack_for_ci
fi
if [[ ${OPT_TEST} -eq 1 ]]; then
    run_test
fi
if [[ ${OPT_HA_TEST} -eq 1 ]];then
    run_ha_test
fi
