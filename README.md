# mc-discord-bot

Minecraft 伺服器（itzg/minecraft-server）加上 Discord 狀態通知機器人。

機器人用 Minecraft 狀態查詢（mcstatus）偵測伺服器上線、離線，以及玩家加入、離開，並發到指定的 Discord 頻道。

## 功能

- **通知**：伺服器上線、離線，玩家加入、離開
- **`/status` 指令**：即時查看在線人數、玩家名單、版本、延遲、連線位址
- **即時狀態訊息**：機器人會在頻道發一則狀態訊息並釘選，每次查詢後自動更新；重啟後會沿用同一則
- **狀態列**：機器人名稱下方顯示「3/20 人在線」，伺服器離線時顯示「伺服器離線」

## Discord 權限

機器人需要：查看頻道、發送訊息、嵌入連結、讀取訊息歷史、管理訊息（用來釘選狀態訊息，沒有的話訊息照樣會更新，只是不會釘選）。
邀請機器人時請勾選 `bot` 和 `applications.commands` 兩個 scope，`/status` 才會出現。

想把狀態訊息放在獨立頻道（避免被加入、離開通知洗掉），在 `.env` 設 `STATUS_CHANNEL_ID`。

## 使用方式

1. `cp .env.example .env`，填入 Discord bot token、頻道 ID、連線位址等。
2. 把 CurseForge API key 放進 `cf_api_key.txt`。
3. `docker compose up -d`

`.env`、`cf_api_key.txt`、`data/` 已列在 `.gitignore`，不會被提交。
