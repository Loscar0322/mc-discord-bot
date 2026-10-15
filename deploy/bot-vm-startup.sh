#!/bin/bash
# mc-bot VM 的開機腳本：裝 Docker、加 1GB swap（e2-micro 只有 1GB 記憶體）
# 每次開機都會跑，所以每一步都先檢查是否已完成
set -e

if [ ! -f /swapfile ]; then
  fallocate -l 1G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
swapon -a || true

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker
