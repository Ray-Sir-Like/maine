def check_ovs = {
    sshagent(credentials : ['d83398f6-9b5e-437e-bea3-60601e7ffdc1']) {
        sh ("""#!/bin/bash
ssh -o StrictHostKeyChecking=no -l root ${params.NODE} /bin/bash << EOS
#!/bin/bash -xe
set -o errexit

ssh -i /root/maine/vagrant/vagrantkey seed -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '
echo "Open vSwitch version on node:"
clush -g all rpm -qa | grep openvswitch
echo "Open vSwitch version in container:"
clush -g all sudo docker exec neutron_openvswitch_agent rpm -qa | grep openvswitch
echo "Checking ovs-vswitchd status on node:"
clush -g all sudo systemctl status ovs-vswitchd | grep Active
echo "Checking ovsdb-server status on node:"
clush -g all sudo systemctl status ovsdb-server | grep Active
'

EOS""")
    }
}

pipeline {
    agent any

    parameters {
        string(name: 'NODE', defaultValue: '10.0.220.24', description: 'IP of node to run testing')
        string(name: 'VERSION', defaultValue: '5.1.0', description: 'Last version of USOP to deploy')
        string(name: 'NEWVERSION', defaultValue: 'rocky', description: 'New version to upgrade')
        string(name: 'NEWAGGRESSIVEVERSION', defaultValue: 'train', description: 'New aggressive version to upgrade')
        string(name: 'ANSIBLEVERSION', defaultValue: '2.8.6', description: 'Version of ansible to deploy')
        string(name: 'MAINEVERSION', defaultValue: '3.1.8', description: 'Last version of maine to install')
        string(name: 'CEPHANSIBLEVERSION', defaultValue: '4.0.14', description: 'Last version of ceph-ansible to install')
        string(name: 'KOLLAANSIBLEVERSION', defaultValue: '7.1.2-0.0b7.1.el7', description: 'Last version of kolla-ansible to install')
    }
    options {
        timestamps()
        ansiColor('xterm')
        disableConcurrentBuilds()
        timeout(activity: true, time: 240)
        buildDiscarder logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '7', numToKeepStr: '10')
    }
    stages {
        stage('Environment') {
            steps {
                echo 'Preparing environment...'
                dingTalk accessToken: 'fd9c1957f6bddbd49f5342ceb16965caf3b728dc4c51bf8bcd8c2fe162354d37', imageUrl: '', jenkinsUrl: "${BUILD_URL}", message: "任务 ${JOB_NAME}： 第 ${BUILD_NUMBER} 次构建开始...", notifyPeople: ''
                sshagent(credentials : ['d83398f6-9b5e-437e-bea3-60601e7ffdc1']) {
                    sh ("""#!/bin/bash
ssh -o StrictHostKeyChecking=no -l root ${params.NODE} /bin/bash << EOS
#!/bin/bash -xe
set -o errexit

yum install -y ansible

# disable ksm for performance
systemctl stop ksmtuned || true
systemctl disable ksmtuned || true

if [ -d maine ]
then
pushd maine/vagrant
vagrant destroy -f || true
vagrant box remove centos/7 --all -f || true
virsh vol-list --pool default | grep /var/lib/libvirt/images/ | awk '{print \\\$1}' | xargs -t -i virsh vol-delete {} --pool default

echo '127.0.0.1   localhost localhost.localdomain localhost4 localhost4.localdomain4' > /etc/hosts
echo '::1         localhost localhost.localdomain localhost6 localhost6.localdomain6' >> /etc/hosts
popd
fi

rm -rf maine
git clone https://git.ustack.com/devops/maine

cd maine/vagrant
cp vagrant_variables.yml.example vagrant_variables.yml

sed -i 's/    maine /    maine-${params.MAINEVERSION}-1.el7 ansible-${params.ANSIBLEVERSION} kolla-ansible-${params.KOLLAANSIBLEVERSION} ceph-ansible-${params.CEPHANSIBLEVERSION} /g' bootstrap_seed.sh

vagrant up

iptables -t nat -F PREROUTING
ANSIBLE_HOST_KEY_CHECKING=false ansible-playbook -i vagrant-inventory.ini portforwarding.yml -b

EOS""")
                }
            }
        }
        stage('Deploy') {
            steps {
                echo 'Deploying...'
                sshagent(credentials : ['d83398f6-9b5e-437e-bea3-60601e7ffdc1']) {
                    sh ("""#!/bin/bash
ssh -o StrictHostKeyChecking=no -l root ${params.NODE} /bin/bash << EOS
#!/bin/bash -xe
set -o errexit

ssh -i /root/maine/vagrant/vagrantkey seed -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null << EOF
#!/bin/bash -xe
set -o errexit

# Remove devel repos
# TODO(Yao Ning): Cannot support non production version now
ansible all -i /etc/maine/ustack-hosts -m shell -a "rm -f /etc/yum.repos.d/ustack-rocky-devel.repo" -b
ansible all -i /etc/maine/ustack-hosts -m shell -a "yum clean all" -b
ansible all -i /etc/maine/ustack-hosts -m shell -a "yum makecache" -b

sed -i 's/openstack_release:.*/openstack_release: "${params.VERSION}"/g' /etc/maine/globals.yml
echo 'enable_rally: yes' >> /etc/maine/kolla-extra-globals.yml
# 持久化 rally 配置，避免升级后配置丢失
echo 'rally_extra_volumes:' >> /etc/maine/kolla-extra-globals.yml
echo '  - "rally_config:/var/lib/rally/.rally/"' >> /etc/maine/kolla-extra-globals.yml

sysctl -w net.ipv4.ip_forward=1

# TODO(Xing Zhang): Remove this after maine deploy upgrade to 3.1.9+
echo 'enable_porsche: no' >> /etc/maine/kolla-extra-globals.yml

git clone https://git.ustack.com/devops/maine -b ${params.MAINEVERSION}
cd maine
bash -xe quickstart.sh -m full -H ${params.NODE}

EOF
EOS""")
                }
            }
        }
        stage('Pre Test') {
            steps {
                echo 'Testing before upgrade..'
                sshagent(credentials : ['d83398f6-9b5e-437e-bea3-60601e7ffdc1']) {
                    sh ("""#!/bin/bash
ssh -o StrictHostKeyChecking=no -l root ${params.NODE} /bin/bash << EOS
#!/bin/bash -xe
set -o errexit

ssh -i /root/maine/vagrant/vagrantkey ci -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null << EOF
#!/bin/bash -xe
set -o errexit

# 修改 /var/lib/rally/.rally 目录的权限
docker exec -u root rally chown rally:rally /var/lib/rally/.rally

EOF


ssh -i /root/maine/vagrant/vagrantkey seed -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null << EOF
#!/bin/bash -xe
set -o errexit

# 运行测试
bash -x /root/sync/rally_ci.sh -p "\\"\\[.*\\bsmoke|scenario|integration\\b.*\\]\\""

EOF

ssh -i /root/maine/vagrant/vagrantkey ci -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null << EOF
#!/bin/bash -xe
set -o errexit

# 将测试报告重命名，避免后续测试失败获取到该报告
mv /var/log/kolla/rally/ci_result.html /var/log/kolla/rally/pre_ci_result.html
EOF

scp -i /root/maine/vagrant/vagrantkey -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ci:/var/log/kolla/rally/pre_ci_result.html /root/maine
EOS

# NOTE(Xing Zhang): fetch report from node to jenkins
cat > ci-inventory << EOF
[ci]
${params.NODE} ansible_user=root
EOF

ANSIBLE_HOST_KEY_CHECKING=false ansible ci -i ci-inventory -m fetch -a "src=/root/maine/pre_ci_result.html dest=`pwd`/ flat=yes"
"""
)
                }
                echo 'Checking ovsdb-server and ovs-vswitchd status after deploy rally testing...'
                script {
                    check_ovs ()
                }
                publishHTML([allowMissing: false, alwaysLinkToLastBuild: true, keepAll: true, reportDir: '.', reportFiles: 'pre_ci_result.html', reportName: 'Rally Pre HTML Report', reportTitles: ''])
            }
        }
        stage('Upgrade') {
            steps {
                echo 'Upgrading...'
                sshagent(credentials : ['d83398f6-9b5e-437e-bea3-60601e7ffdc1']) {
                    sh ("""#!/bin/bash
ssh -o StrictHostKeyChecking=no -l root ${params.NODE} /bin/bash << EOS
#!/bin/bash -xe
set -o errexit

ssh -i /root/maine/vagrant/vagrantkey seed -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null << EOF
#!/bin/bash -xe
set -o errexit

#TODO(YAO NING): Only support upgrade to master
ansible all -i /etc/maine/ustack-hosts -m shell -a "curl -o /etc/yum.repos.d/ustack-rocky-devel.repo http://repo.ustack.com/repofiles/ustack-rocky-devel.repo" -b
ansible all -i /etc/maine/ustack-hosts -m shell -a "yum clean all" -b
ansible all -i /etc/maine/ustack-hosts -m shell -a "yum makecache" -b

yum update -y maine kolla-ansible

# update inventory
if [ -f "/data/filename" ];then
    sed -e "s/^ansible_ssh/#&/" \
        -e "s/\\(#\\)\\(control[1-9]\\)/\\2/" \
        -e "s/\\(#\\)\\(compute[1-9]\\)/\\2/" \
        -e "s/\\(#\\)\\(ci\\)/\\2/" \
        -i /etc/maine/ustack-hosts.rpmnew
    rm -f /etc/maine/ustack-hosts
    cp /etc/maine/ustack-hosts.rpmnew /etc/maine/ustack-hosts
fi

# 更新 kolla 组件的 password.yml
mv /etc/kolla/passwords.yml /tmp/kolla-passwords.yml.old
cp /usr/share/kolla-ansible/etc_examples/kolla/passwords.yml /tmp/kolla-passwords.yml.new
kolla-genpwd -p /tmp/kolla-passwords.yml.new
kolla-mergepwd --old /tmp/kolla-passwords.yml.old --new /tmp/kolla-passwords.yml.new --final /etc/kolla/passwords.yml

# 更新 maine 组件的 password.yml
mv /etc/maine/passwords.yml /tmp/maine-passwords.yml.old
cp /usr/share/maine-ansible/etc_examples/maine/passwords.yml /tmp/maine-passwords.yml.new
maine-genpwd -p /tmp/maine-passwords.yml.new
kolla-mergepwd --old /tmp/maine-passwords.yml.old --new /tmp/maine-passwords.yml.new --final /etc/maine/passwords.yml

sed -i 's/openstack_release:.*/openstack_release: "${params.NEWVERSION}"/g' /etc/maine/globals.yml
sed -i 's/openstack_aggressive_release:.*/openstack_aggressive_release: "${params.NEWAGGRESSIVEVERSION}"/g' /etc/maine/globals.yml
sed -i 's/rally_tag:.*/rally_tag: train/g' /etc/maine/kolla-extra-globals.yml
echo 'rally_install_type: source' >> /etc/maine/kolla-extra-globals.yml
echo 'bifrost_network_interface: eth0' >> /etc/maine/globals.yml

cd /usr/share/maine-ansible
maine-ansible prechecks
maine-ansible pull
maine-ansible upgrade
maine-ansible post-deploy

EOF

EOS""")
                }
            }
        }
        stage('Post Test') {
            steps {
                echo 'Testing after upgrade..'
                timeout(time: 180) {
                    sshagent(credentials : ['d83398f6-9b5e-437e-bea3-60601e7ffdc1']) {
                        sh ("""#!/bin/bash
ssh -o StrictHostKeyChecking=no -l root ${params.NODE} /bin/bash << EOS
#!/bin/bash -xe
set -o errexit

ssh -i /root/maine/vagrant/vagrantkey seed -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null << EOF
#!/bin/bash -xe
set -o errexit

# add -i 0 for only running test without initialize_openstack_for_ci
bash -x /root/sync/rally_ci.sh -p "\\"\\[.*\\bsmoke|scenario|integration\\b.*\\]\\"" -i 0

EOF

scp -i /root/maine/vagrant/vagrantkey -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ci:/var/log/kolla/rally/ci_result.html /root/maine
EOS

# NOTE(Xing Zhang): fetch report from node to jenkins
cat > ci-inventory << EOF
[ci]
${params.NODE} ansible_user=root
EOF

ANSIBLE_HOST_KEY_CHECKING=false ansible ci -i ci-inventory -m fetch -a "src=/root/maine/ci_result.html dest=`pwd`/ flat=yes"
""")
                    }
                }
                echo 'Checking ovsdb-server and ovs-vswitchd status after upgrade rally testing...'
                script {
                    check_ovs ()
                }
                publishHTML([allowMissing: false, alwaysLinkToLastBuild: true, keepAll: true, reportDir: '.', reportFiles: 'ci_result.html', reportName: 'Rally Post HTML Report', reportTitles: ''])
            }
        }

        stage('Reconfigure') {
            steps {
                echo 'Reconfiguring...'
                timeout(time: 120) {
                    sshagent(credentials : ['d83398f6-9b5e-437e-bea3-60601e7ffdc1']) {
                        sh ("""#!/bin/bash
ssh -o StrictHostKeyChecking=no -l root ${params.NODE} /bin/bash << EOS
#!/bin/bash -xe
set -o errexit

ssh -i /root/maine/vagrant/vagrantkey seed -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null << EOF
#!/bin/bash -xe
set -o errexit

echo 'openstack_logging_debug: False' >> /etc/maine/kolla-extra-globals.yml
echo 'openstack_service_workers: 3' >> /etc/maine/kolla-extra-globals.yml

cd /usr/share/maine-ansible
maine-ansible reconfigure

EOF

EOS
""")
                    }
                }
                echo 'checking failure...'
                timeout(time: 120) {
                    sshagent(credentials : ['d83398f6-9b5e-437e-bea3-60601e7ffdc1']) {
                        sh ("""#!/bin/bash
ssh -o StrictHostKeyChecking=no -l root ${params.NODE} /bin/bash << EOS
#!/bin/bash -xe
set -o errexit

ssh -i /root/maine/vagrant/vagrantkey seed -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null << EOF
#!/bin/bash -xe
set -o errexit

clush -g all sudo docker ps -a --format \"{{.Names}}\" --filter status=created --filter status=restarting --filter status=paused --filter status=exited --filter status=dead

EOF

EOS
""")
                    }
                }
            }
        }
    }

    post {
        success {
            dingTalk accessToken: 'fd9c1957f6bddbd49f5342ceb16965caf3b728dc4c51bf8bcd8c2fe162354d37', imageUrl: '', jenkinsUrl: "${BUILD_URL}",
            message: "任务 ${JOB_NAME} 第 ${BUILD_NUMBER} 次构建成功！访问地址为：http://${params.NODE} 用户名：admin 密码：ustack", notifyPeople: ''
            echo "部署成功，访问地址为：http://${params.NODE} 用户名：admin 密码：ustack"

            deleteDir()
        }
        failure {
            dingTalk accessToken: 'fd9c1957f6bddbd49f5342ceb16965caf3b728dc4c51bf8bcd8c2fe162354d37', jenkinsUrl: "${BUILD_URL}",
            message: "构建失败，请及时查看问题原因！", notifyPeople: ''

            deleteDir()
        }
        aborted {
            dingTalk accessToken: 'fd9c1957f6bddbd49f5342ceb16965caf3b728dc4c51bf8bcd8c2fe162354d37', jenkinsUrl: "${BUILD_URL}",
            message: "构建失败，已被终止！", notifyPeople: ''

            deleteDir()
        }
    }
}
