# mc-discord-bot

Minecraft 伺服器（itzg/minecraft-server）加上 Discord 狀態通知機器人。

機器人用 Minecraft 狀態查詢（mcstatus）偵測伺服器上線、離線，以及玩家加入、離開，並發到指定的 Discord 頻道。

## 使用方式

1. `cp .env.example .env`，填入 Discord bot token、頻道 ID、連線位址等。
2. 把 CurseForge API key 放進 `cf_api_key.txt`。
3. `docker compose up -d`

`.env`、`cf_api_key.txt`、`data/` 已列在 `.gitignore`，不會被提交。

## 機器人獨立 VM

機器人可以跑在另一台免費 e2-micro，讓 Minecraft VM 不玩時關機。步驟見 [deploy/bot-vm.md](deploy/bot-vm.md)。
