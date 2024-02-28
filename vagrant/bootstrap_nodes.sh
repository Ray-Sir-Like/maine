#!/bin/bash

dnf clean all && dnf makecache

# cephadm need lvm2 and python3
dnf install python3-libselinux -y

# network need to dhcp address for vagrant
dnf install dhcp-client -y
