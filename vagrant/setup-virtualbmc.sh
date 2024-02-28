#!/bin/bash -xe
set -o errexit

OLD_VBMCS=$(vbmc list | awk 'NR>3{print $2}')

echo Removing old vbmcs
for OLD_VBMC in ${OLD_VBMCS}; do
    vbmc stop ${OLD_VBMC}
    sleep 2
    vbmc delete ${OLD_VBMC}
done

echo creating new vbmcs
VAGRANT_VMS=$(virsh list | grep vagrant | grep -v seed | awk '{print $2}')
for VM in ${VAGRANT_VMS}; do
    if [[ $VM == *"compute1"* ]]; then
        VBMC_PORT=65041
    elif [[ $VM == *"compute2"* ]]; then
        VBMC_PORT=65042
    elif [[ $VM == *"compute3"* ]]; then
        VBMC_PORT=65043
    elif [[ $VM == *"compute4"* ]]; then
        VBMC_PORT=65044
    elif [[ $VM == *"compute5"* ]]; then
        VBMC_PORT=65045
    elif [[ $VM == *"compute6"* ]]; then
        VBMC_PORT=65046
    fi

    if [[ $VM == *"control1"* ]]; then
        VBMC_PORT=64041
    elif [[ $VM == *"control2"* ]]; then
        VBMC_PORT=64042
    elif [[ $VM == *"control3"* ]]; then
        VBMC_PORT=64043
    elif [[ $VM == *"ci"* ]]; then
        VBMC_PORT=64040
    fi
    vbmc add $VM --port $VBMC_PORT --username root --password ustack
    sleep 2
    vbmc stop $VM
    sleep 2
    vbmc start $VM
done

vbmc list
