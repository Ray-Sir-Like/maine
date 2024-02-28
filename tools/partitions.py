#!/usr/bin/env python
# Copyright (c) 2018 UnitedStack (Beijing) Technology Co., Ltd.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import guestfs
import os

# remove old generated drive
try:
    os.unlink("/opt/ironic-baremetal-partitioned.qcow2")
except Exception:
    print("Previous image was not found, nothing to delete.")

g = guestfs.GuestFS(python_return_dict=True)

# import old and new images
print("Creating new repartitioned image")
g.add_drive_opts("/opt/ironic-baremetal.qcow2", format="qcow2", readonly=1)
g.disk_create(
    "/opt/ironic-baremetal-partitioned.qcow2",
    "qcow2",
    10.2 * 1024 * 1024 * 1024,
)  # 10.1G
g.add_drive_opts(
    "/opt/ironic-baremetal-partitioned.qcow2", format="qcow2", readonly=0
)
g.launch()

# create the partitions for new image
print("Creating the initial partitions")
g.part_init("/dev/sdb", "mbr")
# 1G boot
g.part_add("/dev/sdb", "primary", 2048, 2099199)
g.part_add("/dev/sdb", "primary", 2099200, -1)

g.pvcreate("/dev/sdb2")
g.vgcreate("vg", ["/dev/sdb2"])
g.lvcreate("root", "vg", 9 * 1024)
g.part_set_bootable("/dev/sdb", 1, True)

# add filesystems to volumes
print("Adding filesystems")
ids = {}
keys = ["root"]
volumes = ["/dev/vg/root"]

count = 0
for volume in volumes:
    g.mkfs("ext4", volume)
    ids[keys[count]] = g.vfs_uuid(volume)


# create filesystem on boot and swap
g.mkfs("ext4", "/dev/sdb1")

# mount drives and copy content
print("Start copying content")
g.mkmountpoint("/old")
g.mkmountpoint("/root")
g.mkmountpoint("/boot")
g.mount("/dev/sda1", "/old")

g.mount("/dev/sdb1", "/boot")
g.mount(volumes[0], "/root")

# copy content to root
results = g.ls("/old/")
for result in results:
    if result not in ("boot"):
        print("Copying %s to root" % result)
        g.cp_a("/old/%s" % result, "/root/")

# copy extra content
folders_to_copy = ["boot"]
for folder in folders_to_copy:
    results = g.ls("/old/%s/" % folder)
    for result in results:
        print("Copying %s to %s" % (result, folder))
        g.cp_a("/old/%s/%s" % (folder, result), "/%s/" % folder)

# create /etc/fstab file
print("Generating fstab content")
fstab_content = """
UUID={boot_id} /boot ext4 defaults 0 2
UUID={root_id} / ext4 defaults 0 1
""".format(
    boot_id=g.vfs_uuid("/dev/sdb1"), root_id=ids["root"]
)

g.write("/root/etc/fstab", fstab_content)


# unmount filesystems
g.umount("/root")
g.umount("/boot")
g.umount("/old")

# mount in the right directories to install bootloader
print("Installing bootloader")
g.mount(volumes[0], "/")
g.mkdir("/boot")
g.mount("/dev/sdb1", "/boot")


# do a selinux relabel
g.selinux_relabel(
    "/etc/selinux/targeted/contexts/files/file_contexts", "/", force=True
)

# set rootfs label
# Change the current GRUB_DEVICE
# from LABEL=(cloud)img-rootfs to /dev/mapper/...
# TODO(Xing Zhang): Fix E501 line too long (86 > 79 characters)
g.sh(
    'sed -i -e "s?^GRUB_DEVICE=.*?GRUB_DEVICE=/dev/mapper/vg-root?" /etc/default/grub'
)

g.sh("grub2-install --target=i386-pc /dev/sdb")
g.sh("grub2-mkconfig -o /boot/grub2/grub.cfg")


# create dracut.conf file
dracut_content = """
add_dracutmodules+="lvm crypt"
"""
g.write("/etc/dracut.conf", dracut_content)

# update initramfs to include lvm and crypt
kernels = g.ls("/lib/modules")
for kernel in kernels:
    print("Updating dracut to include modules in kernel %s" % kernel)
    g.sh("dracut -f /boot/initramfs-%s.img %s --force" % (kernel, kernel))
g.umount("/boot")
g.umount("/")

# close images
print("Finishing image")
g.shutdown()
g.close()
