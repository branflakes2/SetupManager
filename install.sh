#!/bin/bash

#verify efiboot
#if
ls /sys/firmware/efi/efivars
#doesn't give output then fail

#check for internet
#if
ping 1.1.1.1 -c 1
#fails then
#setup internet?

timedatectl set-ntp true

$disk="/dev/sda" #get device
#get swap size
#get total number of sectors

mkfat $device 1
mkswap $device 2 
mkfs.ext4 $device 3

mount $device 3 /mnt
mount $device 2 /mnt/boot

pacstrap /mnt base-devel
arch-chroot /mnt
