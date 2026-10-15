# 建立 mc-bot 免費 VM（只跑 Discord 機器人）

目標：機器人 24 小時開在免費的 e2-micro，Minecraft VM 不玩時可以關機。

| 項目 | 設定 |
| --- | --- |
| 名稱 | `mc-bot` |
| 機型 | e2-micro（2 vCPU 共用／1 GB） |
| 區域 | `us-west1-b`（免費額度只限 us-west1／us-central1／us-east1） |
| 系統 | Debian 12 |
| 磁碟 | 30 GB **pd-standard**（免費額度只含標準永久磁碟） |
| 服務帳戶 | 專用的 `mc-bot`，目前**不給任何權限**（之後做 `/start` `/stop` 再加自訂角色） |
| 防火牆 | 不用新增；機器人只往外連 Discord 和 Minecraft VM |

費用：一個帳單帳戶每月一台 e2-micro 與 30 GB 標準磁碟免費。外部 IP 與網路流量的收費規則以 [Google 官方免費額度說明](https://cloud.google.com/free) 為準，建議先設預算提醒。

## 1. 建立 VM（Cloud Shell）

在 GCP Console 右上角開 Cloud Shell，貼上：

```bash
gcloud config set project mcserver-511615

# 機器人專用服務帳戶（不給角色，比預設的 Compute 服務帳戶安全）
gcloud iam service-accounts create mc-bot --display-name="mc-bot VM"

# 建立開機腳本（裝 Docker、加 swap）
cat > bot-vm-startup.sh <<'EOS'
#!/bin/bash
set -e
if [ ! -f /swapfile ]; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
swapon -a || true
command -v docker >/dev/null 2>&1 || curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
EOS

gcloud compute instances create mc-bot \
  --zone=us-west1-b \
  --machine-type=e2-micro \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=30GB --boot-disk-type=pd-standard \
  --service-account=mc-bot@mcserver-511615.iam.gserviceaccount.com \
  --scopes=cloud-platform \
  --metadata-from-file=startup-script=bot-vm-startup.sh
```

開機腳本和 repo 裡的 `deploy/bot-vm-startup.sh` 內容相同。等 2～3 分鐘讓它裝好 Docker。

## 2. 放上機器人檔案（VM 的 SSH）

Console →「VM 執行個體」→ `mc-bot` 右邊按 **SSH**。

1. 確認 Docker 裝好了：`sudo docker version`（沒有的話再等一下）。
2. 建資料夾：`mkdir -p ~/mc-bot && cd ~/mc-bot`
3. 用 SSH 視窗右上角的「**上傳檔案**」，上傳 repo 裡的 `bot.py` 和 `docker-compose.bot.yml`（從 GitHub 網頁下載）。上傳的檔案會在家目錄，搬進來：

   ```bash
   mv ~/bot.py ~/mc-bot/bot.py
   mv ~/docker-compose.bot.yml ~/mc-bot/docker-compose.yml
   ```

## 3. 放 token（只在 VM 上，不要貼到任何對話）

```bash
cd ~/mc-bot
nano .env
```

內容（值不要加引號或空格）：

```
DISCORD_BOT_TOKEN=重新產生的機器人token
DISCORD_CHANNEL_ID=頻道ID
SERVER_ADDRESS=Minecraft的固定IP:25565
```

存檔（Ctrl+O、Enter、Ctrl+X）後鎖權限：`chmod 600 .env`

> 舊 token 曾貼在對話中，建議先到 Discord Developer Portal → Bot → Reset Token，用新的。換 token 後 Minecraft VM 上的舊機器人會自動失效。

## 4. 啟動

```bash
cd ~/mc-bot
sudo docker compose up -d
sudo docker compose logs -f bot
```

看到 `Logged in as ...` 就成功了（Ctrl+C 離開日誌）。Minecraft 沒開時會顯示 `query failed`，正常。

## 5. 關掉 Minecraft VM 上的舊機器人

避免同一件事通知兩次。在 `minecraft-server` 的 SSH：

```bash
cd ~/minecraft
sudo docker compose stop bot && sudo docker compose rm -f bot
```

之後把 repo 新版的 `docker-compose.yml` 換上去（`bot` 已設成預設不啟動），`docker compose up -d` 就不會再把它叫起來。

## 常用指令（mc-bot 上，在 `~/mc-bot/`）

- 看日誌：`sudo docker compose logs -f bot`
- 更新 bot.py 後重啟：`sudo docker compose restart bot`
- 改 `.env` 後：`sudo docker compose up -d --force-recreate`
