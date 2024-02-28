#!/bin/bash -xe
set -o errexit

: ${OPT_IPADDR:=127.0.0.1}
: ${OPT_TYPE:=basic}
: ${OPT_UOS_RELEASE:=7.0.0}
: ${OPT_UDS_RELEASE:=3.0.0}
: ${OPT_NIGHTLY:=yes}
: ${OPT_OS_RELEASE:=`cat /etc/os-release | grep PRETTY_NAME | awk '{print $1}' | awk -F '"' '{print $2}'`}
: ${OPT_OS_VERSION:=`cat /etc/os-release | grep VERSION_ID | awk '{print $1}' | awk -F '"' '{print $2}' | awk -F '.' '{print $1}'`}
: ${OPT_ARCH:=`uname -r | awk -F '.' '{print $NF}'`}
: ${OPT_TLS:=no}
function usage {
    echo "Basic options:"
    echo "  -m, --mode [ basic | full | vmha ]"
    echo "                      basic will setup a basic UOS environment while full will setup a full one"
    echo "  -H, --host"
    echo "                      host ip for quickstart server"
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
        --host|-H)
            OPT_IPADDR=$2
            shift
            ;;
        --mode|-m)
            OPT_TYPE=$2
            shift
            ;;
        --uos|-r)
            OPT_UOS_RELEASE=$2
            shift
            ;;
        --uds|-c)
            OPT_UDS_RELEASE=$2
            shift
            ;;
        --os|-s)
            OPT_OS_RELEASE=$2
            shift
            ;;
        --arch|-a)
            OPT_ARCH=$2
            shift
            ;;
        --nightly|-n)
            OPT_NIGHTLY=$2
            shift
            ;;
        --tls|-t)
            OPT_TLS=$2
            shift
            ;;
        --help|-h)
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

prepare_seed () {
    if [ $OPT_NIGHTLY == 'yes' ];then
        PKG_UOS_RELEASE=nightly
        PKG_UDS_RELEASE=nightly
    else
        PKG_UOS_RELEASE=${OPT_UOS_RELEASE}
        PKG_UDS_RELEASE=${OPT_UDS_RELEASE}
    fi

    if [ $OPT_OS_RELEASE == 'openEuler' ];then
        resize2fs /dev/vda2
    else
        xfs_growfs /
    fi

    if [ $OPT_OS_RELEASE == 'CentOS' ];then
        os_release='centos'
    elif [ $OPT_OS_RELEASE == 'openEuler' ];then
        os_release='openeuler'
    fi
    mkdir -p /var/www/html/$os_release-$OPT_OS_VERSION/os/"$OPT_ARCH"
    rm -f /etc/yum.repos.d/*
    # Download os package
    if [ $OPT_OS_RELEASE == 'CentOS' ];then
        os_distro='c8s'

        curl -O http://repo.ustack.com/deploy-tools/os/"$OPT_ARCH"/CentOS-Stream-8-"$OPT_ARCH"-20221027-dvd1.iso
        mount -o loop CentOS-Stream-8-"$OPT_ARCH"-20221027-dvd1.iso /media
        cp -ar /media/AppStream /var/www/html/$os_release-$OPT_OS_VERSION/os/"$OPT_ARCH"/
        cp -ar /media/BaseOS /var/www/html/$os_release-$OPT_OS_VERSION/os/"$OPT_ARCH"/
        umount /media

        cat > /etc/yum.repos.d/ustack.repo << EOF
[ustack-local]
name=ustack-local
baseurl=file:///var/www/html/$os_release-$OPT_OS_VERSION/os/$OPT_ARCH/AppStream/
enabled=1
gpgcheck=0

[ustack-local-os]
name=ustack-local-os
baseurl=file:///var/www/html/$os_release-$OPT_OS_VERSION/os/$OPT_ARCH/BaseOS/
enabled=1
gpgcheck=0
EOF
    elif [ $OPT_OS_RELEASE == 'openEuler' ];then
        os_distro='oe2203'

        curl -O http://repo.ustack.com/deploy-tools/os/"$OPT_ARCH"/openEuler-22.03-LTS-SP1-x86_64-dvd.iso
        mount -o loop openEuler-22.03-LTS-SP1-x86_64-dvd.iso /media
        cp -ar /media/Packages /var/www/html/$os_release-$OPT_OS_VERSION/os/"$OPT_ARCH"/
        cp -ar /media/repodata /var/www/html/$os_release-$OPT_OS_VERSION/os/"$OPT_ARCH"/
        umount /media

        cat > /etc/yum.repos.d/ustack.repo << EOF
[ustack-local]
name=ustack-local
baseurl=file:///var/www/html/$os_release-$OPT_OS_VERSION/os/$OPT_ARCH/
enabled=1
gpgcheck=0
EOF
    else
        echo "Unsupported os distro release"
        exit 1
    fi

    # Install tar for unzip packages
    dnf makecache
    dnf install tar -y

    # Download uos package and registry
    curl -O http://repo.ustack.com/deploy-tools/uos/"$OPT_ARCH"/7/repo/uos7-packages-"$PKG_UOS_RELEASE"-"$os_distro"-"$OPT_ARCH".tar.gz
    curl -O http://repo.ustack.com/deploy-tools/uos/"$OPT_ARCH"/7/registry/uos7-registry-"$PKG_UOS_RELEASE"-"$os_distro"-"$OPT_ARCH".tar.gz

    # Download uds package and registry
    # FIXME(Yao Ning): uds package is rarely changed, always use nightly release here
    curl -O http://repo.ustack.com/deploy-tools/uds/"$OPT_ARCH"/3/repo/uds3-packages-"$PKG_UDS_RELEASE"-"$os_distro"-"$OPT_ARCH".tar.gz
    curl -O http://repo.ustack.com/deploy-tools/uds/"$OPT_ARCH"/3/registry/uds3-registry-"$PKG_UDS_RELEASE"-"$os_distro"-"$OPT_ARCH".tar.gz

    # Download binary package
    curl -O http://repo.ustack.com/deploy-tools/ubinary-"$OPT_ARCH".tar.gz
    cp ubinary-"$OPT_ARCH".tar.gz /var/www/html/

    tar -zxvf uos7-packages-"$PKG_UOS_RELEASE"-"$os_distro"-"$OPT_ARCH".tar.gz -C /var/www/html/
    tar -zxvf uos7-registry-"$PKG_UOS_RELEASE"-"$os_distro"-"$OPT_ARCH".tar.gz -C /var/lib/
    tar -zxvf uds3-packages-"$PKG_UDS_RELEASE"-"$os_distro"-"$OPT_ARCH".tar.gz -C /var/www/html/
    tar -zxvf uds3-registry-"$PKG_UDS_RELEASE"-"$os_distro"-"$OPT_ARCH".tar.gz -C /var/lib/
    tar -zvxf ubinary-"$OPT_ARCH".tar.gz -C /usr/local/bin/

    rm -f *.tar.gz
    rm -f *.iso

    setenforce permissive
    sed -i 's/SELINUX=enforcing/SELINUX=permissive/g' /etc/selinux/config

    # FIXME(Yao Ning): Need install httpd here, but c8s httpd is a module package, fixme later
    dnf install httpd -y

    sed -i "s/Listen 80/Listen 4100/g" /etc/httpd/conf/httpd.conf
    systemctl start  httpd && systemctl enable httpd


    cat > /etc/systemd/system/docker-distribution.service << EOF
[Unit]
Description=Registry server for Docker
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/registry serve /etc/docker-distribution/registry/config.yml
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

    mkdir -p /etc/docker-distribution/registry
    cat > /etc/docker-distribution/registry/config.yml << EOF
version: 0.1
log:
  fields:
    service: registry
storage:
    cache:
        layerinfo: inmemory
    filesystem:
        rootdirectory: /var/lib/registry
http:
    addr: :4000
EOF

    systemctl start docker-distribution && systemctl enable docker-distribution

    # seed need ip_forward
    sysctl -w net.ipv4.ip_forward=1
    echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf
}

prepare_os () {

    if [ $OPT_OS_RELEASE == 'CentOS' ];then
        os_release='centos'

    cat >> /etc/yum.repos.d/ustack.repo << EOF
[ustack-local-uos]
name=ustack-local-uos
baseurl=file:///var/www/html/$os_release-$OPT_OS_VERSION/uos7/$OPT_ARCH/
enabled=1
gpgcheck=0
EOF
    elif [ $OPT_OS_RELEASE == 'openEuler' ];then
        os_release='openeuler'

    cat >> /etc/yum.repos.d/ustack.repo << EOF
[ustack-local-uos]
name=ustack-local-uos
baseurl=file:///var/www/html/$os_release-$OPT_OS_VERSION/uos7/$OPT_ARCH/
enabled=1
gpgcheck=0
EOF
    fi

    dnf install maine -y

    # FIXME(Yao Ning): Should support ipmi_port
    cat > /etc/kolla/config/bifrost/servers.csv << EOF
hostname,ipmi_address,ipmi_port,ipmi_username,ipmi_password,pxe_address,gateway,vlan2003,vlan2004,vlan2005,vlan2006,vlan2007,vlan2009
ci,192.168.121.1,64040,root,ustack,10.10.10.29,10.0.6.254,10.0.3.29,10.0.4.29,10.0.5.29,10.0.6.29,10.0.7.29,10.0.9.29
control1,192.168.121.1,64041,root,ustack,10.10.10.10,10.0.6.254,10.0.3.31,10.0.4.31,10.0.5.31,10.0.6.31,10.0.7.31,10.0.9.31
control2,192.168.121.1,64042,root,ustack,10.10.10.11,10.0.6.254,10.0.3.32,10.0.4.32,10.0.5.32,10.0.6.32,10.0.7.32,10.0.9.32
control3,192.168.121.1,64043,root,ustack,10.10.10.12,10.0.6.254,10.0.3.33,10.0.4.33,10.0.5.33,10.0.6.33,10.0.7.33,10.0.9.33
compute1,192.168.121.1,65041,root,ustack,10.10.10.13,10.0.6.254,10.0.3.41,10.0.4.41,10.0.5.41,10.0.6.41,10.0.7.41,10.0.9.41
compute2,192.168.121.1,65042,root,ustack,10.10.10.14,10.0.6.254,10.0.3.42,10.0.4.42,10.0.5.42,10.0.6.42,10.0.7.42,10.0.9.42
compute3,192.168.121.1,65043,root,ustack,10.10.10.15,10.0.6.254,10.0.3.43,10.0.4.43,10.0.5.43,10.0.6.43,10.0.7.43,10.0.9.43
EOF

    if [ $OPT_NIGHTLY == 'yes' ];then
        sed -i "s/#openstack_release: null/openstack_release: wallaby/" /etc/maine/globals.yml
        sed -i "s/#ceph_release: null/ceph_release: pacific/" /etc/maine/globals.yml
    else
        sed -i "s/#openstack_release: null/openstack_release: $OPT_UOS_RELEASE/" /etc/maine/globals.yml
        sed -i "s/#ceph_release: null/ceph_release: $OPT_UDS_RELEASE/" /etc/maine/globals.yml
    fi

    sed -i "s/#seed_interface: null/seed_interface: eth0/" /etc/maine/globals.yml

    # Download baremetal os
    curl -O http://repo.ustack.com/deploy-tools/os/"$OPT_ARCH"/baremetal-os-uefi-"$os_distro"-"$OPT_ARCH".tar.gz
    tar -xvzf baremetal-os-uefi-"$os_distro"-"$OPT_ARCH".tar.gz -C /opt/
    rm -f baremetal-os-uefi-"$os_distro"-x86_64.tar.gz

    # bootstrap seed
    maine-ansible bootstrap-servers --limit deployment

#    maine-ansible bifrost-deploy
#    maine-ansible bifrost-enroll
#
#    # FIXME(Yao Ning): Enable it when support ipmi_port
#    for i in `docker exec bifrost_deploy bash -c "export OS_CLOUD=bifrost && openstack baremetal node list -c UUID -f value"`;do
#        # Note(Yao Ning): Use rand mac now, maybe actual mac is useful, but complicated
#        rand_mac=`openssl rand -hex 6 | sed 's/\(..\)/\1:/g; s/.$//'`
#        docker exec bifrost_deploy bash -c "export OS_CLOUD=bifrost && openstack baremetal port create $rand_mac --node $i"
#        docker exec bifrost_deploy bash -c "export OS_CLOUD=bifrost && openstack baremetal node set $i --instance-info image_source='http://localhost:7870/ironic-baremetal.qcow2'"
#        docker exec bifrost_deploy bash -c "export OS_CLOUD=bifrost && openstack baremetal node set $i --driver-info deploy_kernel='http://localhost:7870/black.kernel'"
#        docker exec bifrost_deploy bash -c "export OS_CLOUD=bifrost && openstack baremetal node set $i --driver-info deploy_ramdisk='http://localhost:7870/black.initramfs'"
#        docker exec bifrost_deploy bash -c "export OS_CLOUD=bifrost && openstack baremetal node adopt $i"
#    done

    maine-genhost -p pxe

    sed -e "s/^ansible_ssh/#&/" \
        -e "s/\(#\)\(control[1-9]\)/\2/" \
        -e "s/\(#\)\(compute[1-9]\)/\2/" \
        -e "s/\(#\)\(ci\)/\2/" \
        -i /etc/maine/ustack-hosts

    mv /etc/ansible/ansible.cfg /etc/ansible/ansible.cfg.bak
    cp /usr/share/maine-ansible/ansible.cfg /etc/ansible/ansible.cfg

    maine-ansible genpwds
    maine-ansible bootstrap-servers
}

prepare_network () {

    cat > /etc/maine/group_vars/baremetal.yml << EOF
---
pxe_mtu: 1500
service_mtu: 1500
network_config:
  - type: ovs_bridge
    name: br-ex
    mtu: "{{ service_mtu }}"
    members:
      - type: interface
        name: eth1
        mtu: "{{ service_mtu }}"
      - type: vlan
        vlan_id: 2009
        mtu: "{{ service_mtu }}"
        addresses:
          - ip_netmask: "{{ vlan2009 }}/24"
      - type: vlan
        vlan_id: 2006
        mtu: "{{ service_mtu }}"
        addresses:
          - ip_netmask: "{{ vlan2006 }}/24"
  - type: interface
    name: eth1.2005
    mtu: "{{ service_mtu }}"
    addresses:
      - ip_netmask: "{{ vlan2005 }}/24"
  - type: interface
    name: eth1.2007
    mtu: "{{ service_mtu }}"
    addresses:
      - ip_netmask: "{{ vlan2007 }}/24"
  - type: interface
    name: eth1.2003
    mtu: "{{ service_mtu }}"
    addresses:
      - ip_netmask: "{{ vlan2003 }}/24"
  - type: interface
    name: eth1.2004
    mtu: "{{ service_mtu }}"
    addresses:
      - ip_netmask: "{{ vlan2004 }}/24"
EOF

    # setting allowed latency for network
    echo 'ping_allowed_avg: 1.000' >> /etc/maine/globals.yml
    echo 'ping_allowed_max: 2.000' >> /etc/maine/globals.yml

    maine-ansible bootstrap-networks
}

prepare_configuration () {

    # setting nova.conf
    echo '[neutron]' >> /etc/kolla/config/nova.conf
    echo 'default_floating_pool = public' >> /etc/kolla/config/nova.conf
    sed -i 's/resize_confirm_window = 2/resize_confirm_window = 0/' /usr/share/maine-ansible/config/nova.conf

    # setting /etc/kolla/passwords.yml
    sed -i 's/keystone_admin_password.*/keystone_admin_password: ustack/' /etc/kolla/passwords.yml

    # setting kolla-extra-globals.yml
    echo 'dynamic_pool_size_mb: 1024' >> /etc/maine/kolla-extra-globals.yml
    echo 'nova_reserved_host_memory_mb: 4096' >> /etc/maine/kolla-extra-globals.yml
    echo 'osd_memory_target: "1G"' >> /etc/maine/kolla-extra-globals.yml
    sed -i "s/network_interface: null/network_interface: \"vlan2006\"/g" /etc/maine/kolla-extra-globals.yml
    sed -i "s/#api_interface: null/api_interface: \"eth1.2005\"/g" /etc/maine/kolla-extra-globals.yml
    sed -i "s/#tunnel_interface: null/tunnel_interface: \"eth1.2007\"/g" /etc/maine/kolla-extra-globals.yml
    sed -i "s/#storage_interface: null/storage_interface: \"vlan2006\"/g" /etc/maine/kolla-extra-globals.yml
    sed -i "s/#storage_mgmt_interface: null/storage_mgmt_interface: \"eth1.2004\"/g" /etc/maine/kolla-extra-globals.yml
    sed -i "s/neutron_external_interface: null/neutron_external_interface: \"eth1\"/g" /etc/maine/kolla-extra-globals.yml
    sed -i "s/kolla_internal_vip_address: null/kolla_internal_vip_address: \"10.0.5.30\"/g" /etc/maine/kolla-extra-globals.yml
    sed -i "s/kolla_external_vip_address: null/kolla_external_vip_address: \"10.0.6.30\"/g" /etc/maine/kolla-extra-globals.yml
    sed -i "s/#ceph_rgw_external_vip_address: null/ceph_rgw_external_vip_address: \"10.0.6.20\"/g" /etc/maine/kolla-extra-globals.yml

    # enable horizon for testing
    echo 'enable_horizon: "yes"' >> /etc/maine/kolla-extra-globals.yml

    # enbale external pdns
    echo 'enable_external_pdns_webconsole: true' >> /etc/maine/kolla-extra-globals.yml

    # enable ssd and hdd pools
    echo 'enable_cinder_ssd_backend: "yes"' >> /etc/maine/kolla-extra-globals.yml
    echo 'enable_cinder_hdd_backend: "yes"' >> /etc/maine/kolla-extra-globals.yml
    echo 'enable_cinder_hybrid_backend: "yes"' >> /etc/maine/kolla-extra-globals.yml
    echo 'enable_cinder_generic_backend: "no"' >> /etc/maine/kolla-extra-globals.yml

    # setting cinder.conf
    # rbd snapshot flatten for some test case
    echo '[backend_defaults]' >> /etc/kolla/config/cinder.conf
    echo 'rbd_flatten_volume_from_snapshot = true' >> /etc/kolla/config/cinder.conf

    # setting mtu
    echo 'neutron_global_physnet_mtu: 1500' >> /etc/maine/kolla-extra-globals.yml
    echo 'neutron_ml2_path_mtu: 0' >> /etc/maine/kolla-extra-globals.yml

    # disable container exporter (cadvisor) because of performance issues
    echo 'enable_cadvisor: "no"' >> /etc/maine/globals.yml

    # setting rally.conf
    echo '[DEFAULT]' >> /etc/kolla/config/rally.conf
    echo 'use_stderr = True' >> /etc/kolla/config/rally.conf

    # setting dns
    echo 'host_nameservers:' >> /etc/maine/globals.yml
    echo '  - 10.0.218.41' >> /etc/maine/globals.yml
    echo '  - 10.0.218.42' >> /etc/maine/globals.yml
    echo '  - 10.0.218.43' >> /etc/maine/globals.yml
    echo '  - 119.29.29.29' >> /etc/maine/globals.yml
    echo '  - 114.114.114.114' >> /etc/maine/globals.yml
    echo 'neutron_dnsmasq_dns_servers: 10.0.218.41,10.0.218.42,10.0.218.43' >> /etc/maine/kolla-extra-globals.yml

    # setting TLS
    if [ x"$OPT_TLS" == x"yes" ]; then
        echo "kolla_copy_ca_into_containers: yes" >> /etc/maine/kolla-extra-globals.yml

        # Disable internal TLS now, since user does not use it
        #echo "kolla_enable_tls_internal: yes" >> /etc/maine/kolla-extra-globals.yml
        #echo "kolla_internal_fqdn: vip.qs.in" >> /etc/maine/kolla-extra-globals.yml
        #echo "openstack_cacert: '/etc/pki/ca-trust/source/anchors/kolla-customca-haproxy-internal.crt'" >> /etc/maine/kolla-extra-globals.yml

        echo "kolla_enable_tls_external: yes" >> /etc/maine/kolla-extra-globals.yml
        echo "kolla_external_fqdn: qs14.ustack.com" >> /etc/maine/kolla-extra-globals.yml
        echo "ceph_rgw_external_fqdn: qs14.ustack.com" >> /etc/maine/kolla-extra-globals.yml

        echo "rabbitmq_enable_tls: yes" >> /etc/maine/kolla-extra-globals.yml

        maine-ansible certificates -e kolla_external_vip_address="${OPT_IPADDR}"
    else
        echo "kolla_external_fqdn: ${OPT_IPADDR}" >> /etc/maine/kolla-extra-globals.yml
        echo "ceph_rgw_external_fqdn: ${OPT_IPADDR}" >> /etc/maine/kolla-extra-globals.yml
    fi
}

enable_services () {
    # enable rally
    echo 'enable_rally: yes' >> /etc/maine/kolla-extra-globals.yml

    if [ x"$OPT_TYPE" == x"full" ]; then
        # enable s3
        echo 'enable_s3: "yes"' >> /etc/maine/globals.yml

        # enable malphite
        echo 'enable_malphite: "yes"' >> /etc/maine/globals.yml

        # enable manila
        echo 'enable_manila: "yes"' >> /etc/maine/kolla-extra-globals.yml
        # FIXME(Yao Ning): Don't enable nfs until stable/zed
        # echo 'enable_manila_backend_cephfs_nfs: "yes"'>> /etc/maine/kolla-extra-globals.yml
        ## manila need a default share type for manila-tempest-plugin after stable/train
        echo '[DEFAULT]' >> /etc/kolla/config/manila.conf
        echo 'default_share_type = cephfs' >> /etc/kolla/config/manila.conf

        # enable octavia
        echo 'enable_octavia: "yes"' >> /etc/maine/kolla-extra-globals.yml

        # enable cloudkitty
        echo 'enable_cloudkitty: "yes"' >> /etc/maine/kolla-extra-globals.yml

        # enable shadowfiend
        echo 'enable_shadowfiend: "yes"' >> /etc/maine/globals.yml

        # enable porsche
        echo 'enable_porsche: "yes"' >> /etc/maine/globals.yml

        # enable designate
        echo 'enable_designate: "yes"' >> /etc/maine/kolla-extra-globals.yml

        # enable senlin
        echo 'enable_senlin: "yes"' >> /etc/maine/kolla-extra-globals.yml

        # enable barbican
        echo 'enable_barbican: "yes"' >> /etc/maine/kolla-extra-globals.yml

        # enable zaqar
        echo 'enable_zaqar: "yes"' >> /etc/maine/globals.yml

        # enable hawkeyes
        echo 'enable_hawkeye: "yes"' >> /etc/maine/globals.yml
        echo 'enable_logging: "yes"' >> /etc/maine/globals.yml

        # enable nuntius
        echo 'enable_nuntius: True' >> /etc/maine/globals.yml
        echo 'enable_nuntius_dingtalk: True' >> /etc/maine/globals.yml
        echo 'nuntius_dingtalk_token: 497e93f7766f1133fdcd2770c79f1ed3dc802c427054887c3c5b1537e5de2b43' >> /etc/maine/globals.yml

        echo 'enable_nuntius_email: True' >> /etc/maine/globals.yml
        echo 'nuntius_email_to: []' >> /etc/maine/globals.yml

        # enable ironic
        echo 'enable_ironic: yes' >> /etc/maine/kolla-extra-globals.yml
        # echo 'enable_iscsid: no' >> /etc/maine/kolla-extra-globals.yml
        echo 'ironic_dnsmasq_dhcp_range: "192.168.5.100,192.168.5.110"' >> /etc/maine/kolla-extra-globals.yml

        # enable masakari
        echo 'enable_masakari: "yes"' >> /etc/maine/kolla-extra-globals.yml
        mkdir -p /etc/kolla/config/masakari
        echo '[validation]' >> /etc/kolla/config/masakari/masakari-monitors.conf
        echo 'monitoring_networks = internal,storage' >> /etc/kolla/config/masakari/masakari-monitors.conf
        echo 'ssh_key_filename = /etc/masakari-monitors/id_rsa' >> /etc/kolla/config/masakari/masakari-monitors.conf
        cp /root/.ssh/id_rsa /etc/kolla/config/masakari/
    fi
}

setup () {
    # extend_rootfs
    if [ $OPT_OS_RELEASE == 'openEuler' ];then
        clush -g all resize2fs /dev/vda2
    else
        clush -g all xfs_growfs /
    fi

    # Make sure vlan2006 is not tagged
    ansible -i /etc/maine/ustack-hosts baremetal -m command -a "ovs-vsctl -- set port vlan2006 tag=0"
    ansible -i /etc/maine/ustack-hosts baremetal -m shell -a "sed -i 's#tag=2006#tag=0#' /etc/sysconfig/network-scripts/ifcfg-vlan2006"

    # Download ironic images
    #mkdir -p /etc/kolla/config/ironic
    #cp /opt/ironic_images/ipa.initramfs /etc/kolla/config/ironic/ironic-agent.initramfs
    #cp /opt/ironic_images/ipa.kernel /etc/kolla/config/ironic/ironic-agent.kernel

    maine-ansible bootstrap-hosts
    maine-ansible deploy-ceph
    maine-ansible integrate-ceph
    if [ $OPT_OS_RELEASE == 'CentOS' ];then
    maine-ansible prechecks
    fi
    maine-ansible deploy

    # testing mariadb_backup and recovery works
    maine-ansible mariadb_backup
    maine-ansible mariadb_recovery

    # Expose the mq to the external network
    ansible -i /etc/maine/ustack-hosts control -m copy -a "content='listen rabbitmq\n    mode tcp\n    option tcplog\n    bind 10.0.6.30:5672\n    server control1 10.0.5.31:5672 check inter 2000 rise 2 fall 5\n    server control2 10.0.5.32:5672 check inter 2000 rise 2 fall 5 backup\n    server control3 10.0.5.33:5672 check inter 2000 rise 2 fall 5 backup\n' dest=/etc/kolla/haproxy/services.d/rabbitmq.cfg" -b
    ansible -i /etc/maine/ustack-hosts control -m command -a "docker restart haproxy" -b
}

initialize_openstack () {
    ssh control1 << EOF
#!/bin/bash -xe
set -o errexit

docker exec maine_toolbox bash -c "source /root/admin-openrc && IMAGE_LIST=CentOS---7---rally.raw ENABLE_EXT_NET=1 maine-init-runonce"

EOF
}

prepare_seed
prepare_os
prepare_network
prepare_configuration
enable_services
setup
initialize_openstack
