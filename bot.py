"""Minecraft 伺服器狀態通知機器人（查詢版）

不需要讀伺服器日誌，改用 Minecraft 的狀態查詢（多人遊戲清單用的那個），
所以機器人可以跑在任何地方，例如 GCP 免費 VM。

通知內容：伺服器上線（附連線位址）、伺服器離線、玩家加入、玩家離開。
"""

import asyncio
import os

import discord
from mcstatus import JavaServer

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
SERVER_ADDRESS = os.environ["SERVER_ADDRESS"].strip()   # 顯示給玩家的位址，例如 固定IP:25565
# 機器人實際查詢的位址；同一份 compose 時用容器名稱 mc:25565，沒設就用 SERVER_ADDRESS
QUERY_ADDRESS = os.environ.get("QUERY_ADDRESS", SERVER_ADDRESS).strip()
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "30"))
# 連續查詢失敗幾次才判定離線，避免網路抖一下就誤報
OFFLINE_AFTER = int(os.environ.get("OFFLINE_AFTER", "3"))

client = discord.Client(intents=discord.Intents.none())
channel = None


async def send(text):
    global channel
    try:
        if channel is None:
            channel = await client.fetch_channel(CHANNEL_ID)
        await channel.send(text)
    except Exception as e:
        print("send failed:", e, flush=True)


async def query():
    """回傳 (線上人數, 上限, 玩家名稱集合或 None)；查不到就丟出例外。"""
    server = await JavaServer.async_lookup(QUERY_ADDRESS, timeout=5)
    status = await server.async_status()
    players = status.players
    names = None
    sample = players.sample or []
    # 名單只回傳一部分玩家；只有名單完整時才拿來判斷加入/離開
    if len(sample) == players.online:
        names = {p.name for p in sample}
    return players.online, players.max, names


async def watch():
    await client.wait_until_ready()
    online = None          # None = 還不知道（機器人剛啟動）
    fails = 0
    last_names = set()

    while not client.is_closed():
        try:
            count, maximum, names = await query()
            fails = 0

            if online is not True:
                if online is False:  # 從離線變上線才通知，剛啟動時不通知
                    msg = f"✅ Minecraft 伺服器已啟動，可以進來玩了！（{count}/{maximum}）"
                    msg += f"\n📍 連線位址：`{SERVER_ADDRESS}`"
                    await send(msg)
                online = True
                last_names = names or set()
            elif names is not None:
                for n in sorted(names - last_names):
                    await send(f"🟢 **{n}** 加入了遊戲（{count}/{maximum}）")
                for n in sorted(last_names - names):
                    await send(f"🔴 **{n}** 離開了遊戲（{count}/{maximum}）")
                last_names = names

        except Exception as e:
            fails += 1
            print(f"query failed ({fails}):", e, flush=True)
            if fails >= OFFLINE_AFTER and online is not False:
                if online is True:
                    await send("🛑 Minecraft 伺服器已離線")
                online = False
                last_names = set()

        await asyncio.sleep(POLL_SECONDS)


@client.event
async def setup_hook():
    asyncio.create_task(watch())


@client.event
async def on_ready():
    print(f"Logged in as {client.user}", flush=True)


client.run(TOKEN)