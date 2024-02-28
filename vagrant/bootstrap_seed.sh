#!/bin/bash

ifup eth1

dnf clean all && dnf makecache
dnf install \
    git \
    python3-libselinux \
    vim \
    tmux \
    bash-completion -y

# network need to dhcp address for vagrant
dnf install dhcp-client -y

git clone https://git.ustack.com/devops/maine -b master /root/sync
