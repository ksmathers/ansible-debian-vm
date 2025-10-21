PROXMOX_NODE=${1:-victor.ank.com}
ssh root@$PROXMOX_NODE "qm list"
