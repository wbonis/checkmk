@echo off
set CMK_VERSION="2.3.0p6"
echo ^<^<^<windows_intel_bonding^>^>^>


wmic /namespace:\\root\IntelNCS2 path IANET_TeamOfAdapters get Caption,Name,RedundancyStatus

echo ###

wmic /namespace:\\root\IntelNCS2 path IANET_TeamedMemberAdapter get AdapterFunction,AdapterStatus,GroupComponent,PartComponent

echo ###

wmic /namespace:\\root\IntelNCS2 path IANET_PhysicalEthernetAdapter get AdapterStatus,Caption,DeviceID

