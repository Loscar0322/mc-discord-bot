"""Minecraft 伺服器狀態通知機器人（查詢版）

不需要讀伺服器日誌，改用 Minecraft 的狀態查詢（多人遊戲清單用的那個），
所以機器人可以跑在任何地方，例如 GCP 免費 VM。

功能：
- 通知：伺服器上線（附連線位址）、伺服器離線、玩家加入、玩家離開
- /status 指令：即時查詢在線人數、玩家名單、版本、延遲
- 即時狀態訊息：在頻道釘選一則訊息，每次查詢後自動更新
- 機器人狀態列：顯示「3/20 人在線」或「伺服器離線」
"""

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import discord
from discord import app_commands
from mcstatus import JavaServer

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
# 放即時狀態訊息的頻道；沒設就跟通知同一個頻道
STATUS_CHANNEL_ID = int(os.environ.get("STATUS_CHANNEL_ID") or CHANNEL_ID)
SERVER_ADDRESS = os.environ["SERVER_ADDRESS"].strip()   # 顯示給玩家的位址，例如 固定IP:25565
# 機器人實際查詢的位址；同一份 compose 時用容器名稱 mc:25565，沒設就用 SERVER_ADDRESS
QUERY_ADDRESS = os.environ.get("QUERY_ADDRESS", SERVER_ADDRESS).strip()
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "30"))
# 連續查詢失敗幾次才判定離線，避免網路抖一下就誤報
OFFLINE_AFTER = int(os.environ.get("OFFLINE_AFTER", "3"))

# 用來在釘選訊息裡認出「這是機器人自己的狀態訊息」，重啟後沿用同一則
STATUS_FOOTER = "Minecraft 伺服器狀態"
MAX_NAMES_SHOWN = 30

intents = discord.Intents.none()
intents.guilds = True   # 斜線指令和讀取頻道需要；不是特權 intent
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
channel = None


@dataclass
class ServerState:
    online: bool | None = None     # None = 還不知道（機器人剛啟動）
    count: int = 0
    maximum: int = 0
    names: list[str] = field(default_factory=list)   # 可能只是部分名單
    names_complete: bool = True
    version: str = ""
    motd: str = ""
    latency_ms: float = 0.0
    checked_at: float = 0.0


state = ServerState()


async def send(text):
    global channel
    try:
        if channel is None:
            channel = await client.fetch_channel(CHANNEL_ID)
        await channel.send(text)
    except Exception as e:
        print("send failed:", e, flush=True)


async def query():
    """回傳線上狀態（ServerState，online=True）；查不到就丟出例外。"""
    server = await JavaServer.async_lookup(QUERY_ADDRESS, timeout=5)
    status = await server.async_status()
    players = status.players
    sample = players.sample or []
    return ServerState(
        online=True,
        count=players.online,
        maximum=players.max,
        names=sorted(p.name for p in sample),
        # 名單只回傳一部分玩家；只有名單完整時才拿來判斷加入/離開
        names_complete=len(sample) == players.online,
        version=status.version.name,
        motd=status.motd.to_plain().strip(),
        latency_ms=status.latency,
        checked_at=time.time(),
    )


def build_embed(s: ServerState) -> discord.Embed:
    if s.online is None:
        embed = discord.Embed(title="⏳ 正在查詢伺服器狀態…", color=discord.Color.light_grey())
    elif not s.online:
        embed = discord.Embed(title="🛑 伺服器離線", color=discord.Color.red())
        embed.add_field(name="連線位址", value=f"`{SERVER_ADDRESS}`", inline=False)
    else:
        embed = discord.Embed(title="✅ 伺服器在線", color=discord.Color.green())
        if s.motd:
            embed.description = s.motd
        embed.add_field(name="在線人數", value=f"{s.count}/{s.maximum}")
        embed.add_field(name="版本", value=s.version or "未知")
        embed.add_field(name="延遲", value=f"{s.latency_ms:.0f} ms")
        embed.add_field(name="連線位址", value=f"`{SERVER_ADDRESS}`", inline=False)
        if s.count:
            shown = s.names[:MAX_NAMES_SHOWN]
            text = "、".join(discord.utils.escape_markdown(n) for n in shown) or "（伺服器沒有提供名單）"
            hidden = s.count - len(shown)
            if hidden > 0 and shown:
                text += f" 等，另有 {hidden} 人"
            embed.add_field(name="玩家", value=text, inline=False)
    embed.set_footer(text=STATUS_FOOTER)
    if s.checked_at:
        embed.timestamp = datetime.fromtimestamp(s.checked_at, tz=timezone.utc)
    return embed


# ---------- 機器人狀態列 ----------

_last_presence = None


async def update_presence(s: ServerState):
    global _last_presence
    if s.online:
        key = ("on", s.count, s.maximum)
        activity = discord.Game(f"{s.count}/{s.maximum} 人在線")
        status = discord.Status.online
    elif s.online is False:
        key = ("off",)
        activity = discord.Game("伺服器離線")
        status = discord.Status.dnd
    else:
        return
    if key == _last_presence:   # 沒變就不更新，避免被 Discord 限流
        return
    try:
        await client.change_presence(status=status, activity=activity)
        _last_presence = key
    except Exception as e:
        print("presence update failed:", e, flush=True)


# ---------- 即時狀態訊息 ----------

status_message = None


async def find_or_create_status_message():
    """找出之前釘選的狀態訊息；找不到就發一則新的並釘選。"""
    status_channel = await client.fetch_channel(STATUS_CHANNEL_ID)
    try:
        for msg in await status_channel.pins():
            if msg.author.id == client.user.id and msg.embeds \
                    and msg.embeds[0].footer.text == STATUS_FOOTER:
                return msg
    except Exception as e:
        print("read pins failed:", e, flush=True)

    msg = await status_channel.send(embed=build_embed(state))
    try:
        await msg.pin()
    except Exception as e:
        print("pin failed (機器人需要「管理訊息」權限):", e, flush=True)
    return msg


async def update_status_message(s: ServerState):
    global status_message
    try:
        if status_message is None:
            status_message = await find_or_create_status_message()
        await status_message.edit(embed=build_embed(s))
    except discord.NotFound:
        status_message = None   # 訊息被刪掉了，下次重發
    except Exception as e:
        print("status message update failed:", e, flush=True)


# ---------- /status 指令 ----------

@tree.command(name="status", description="查看 Minecraft 伺服器目前狀態")
async def status_command(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        s = await query()
    except Exception:
        s = ServerState(online=False, checked_at=time.time())
    await interaction.followup.send(embed=build_embed(s))


# ---------- 輪詢 ----------

async def watch():
    global state
    await client.wait_until_ready()
    fails = 0
    last_names = set()

    while not client.is_closed():
        try:
            new = await query()
            fails = 0
            names = set(new.names) if new.names_complete else None

            if state.online is not True:
                if state.online is False:  # 從離線變上線才通知，剛啟動時不通知
                    msg = f"✅ Minecraft 伺服器已啟動，可以進來玩了！（{new.count}/{new.maximum}）"
                    msg += f"\n📍 連線位址：`{SERVER_ADDRESS}`"
                    await send(msg)
                last_names = names or set()
            elif names is not None:
                for n in sorted(names - last_names):
                    await send(f"🟢 **{n}** 加入了遊戲（{new.count}/{new.maximum}）")
                for n in sorted(last_names - names):
                    await send(f"🔴 **{n}** 離開了遊戲（{new.count}/{new.maximum}）")
                last_names = names
            state = new

        except Exception as e:
            fails += 1
            print(f"query failed ({fails}):", e, flush=True)
            if fails >= OFFLINE_AFTER and state.online is not False:
                if state.online is True:
                    await send("🛑 Minecraft 伺服器已離線")
                state = ServerState(online=False)
                last_names = set()
            if state.online is False:
                state.checked_at = time.time()

        await update_presence(state)
        await update_status_message(state)
        await asyncio.sleep(POLL_SECONDS)


@client.event
async def setup_hook():
    asyncio.create_task(watch())


@client.event
async def on_ready():
    print(f"Logged in as {client.user}", flush=True)
    # 同步到通知頻道所在的伺服器，指令會立刻出現（全域同步可能要等一小時）
    try:
        ch = await client.fetch_channel(CHANNEL_ID)
        tree.copy_global_to(guild=ch.guild)
        synced = await tree.sync(guild=ch.guild)
        print(f"synced {len(synced)} command(s) to {ch.guild.id}", flush=True)
    except Exception as e:
        print("command sync failed:", e, flush=True)


client.run(TOKEN)