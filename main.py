import discord
from discord.ext import commands
import json
import os
import random
import asyncio

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

# 永続データ保存ファイル
DATA_FILE = "player_data.json"
bot_active = True


# データの読み書き
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


players_data = load_data()


# Bot 起動
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')


@bot.command()
async def hello(ctx):
    global bot_active
    bot_active = True
    await ctx.send("✅ Botが応答可能になりました。")


@bot.command()
async def bye(ctx):
    global bot_active
    bot_active = False
    await ctx.send("💤 Botは現在おやすみ中です。`!hello`で再開できます。")


@bot.command()
async def register(ctx, name: str, top: int, jg: int, mid: int, adc: int,
                   sup: int):
    if not bot_active:
        return
    is_update = name in players_data
    players_data[name] = {
        "top": top,
        "jg": jg,
        "mid": mid,
        "adc": adc,
        "sup": sup
    }
    save_data(players_data)
    if is_update:
        await ctx.send(f"【更新】{name} の能力値を更新しました。")
    else:
        await ctx.send(f"✅ {name} を登録しました。")


@bot.command()
async def list_players(ctx):
    if not bot_active:
        return
    if not players_data:
        await ctx.send("❌ 登録者がいません。")
        return
    sorted_players = sorted(players_data.items(),
                            key=lambda x: sum(x[1].values()),
                            reverse=True)
    msg = "**📋 登録者一覧（合計値順）**\n"
    for name, stats in sorted_players:
        total = sum(stats.values())
        stat_str = ", ".join([f"{k}:{v}" for k, v in stats.items()])
        msg += f"🔹 {name}：{stat_str}｜合計:{total}\n"
    await ctx.send(msg)

    @bot.command()
    async def team_split(ctx, *, exclude: str = ""):
        if not bot_active:
            return

        exclude_names = [
            name.strip() for name in exclude.split(",") if name.strip()
        ]

        # ボイスチャンネル参加者から名前取得
        if ctx.author.voice is None or ctx.author.voice.channel is None:
            await ctx.send("ボイスチャンネルに参加してから実行してください。")
            return

        members = ctx.author.voice.channel.members
        selected_names = [
            member.display_name for member in members
            if member.display_name not in exclude_names
        ]

        # 登録済みかつ最大10人に制限
        registered = [name for name in selected_names if name in players_data]
        if len(registered) < 10:
            await ctx.send(f"登録済みのメンバーが10人未満です（現在 {len(registered)} 人）。")
            return
        elif len(registered) > 10:
            await ctx.send(
                "登録済みのメンバーが11人以上です。`!team_split 名前1,名前2,...`で除外してください。")
            return

        # ↓以下にチーム分け処理（省略）を続けてください

    from itertools import permutations

    roles = ["top", "jg", "mid", "adc", "sup"]
    best_team = None
    min_diff = float("inf")

    for combo in permutations(eligible_names, 10):
        team1 = combo[:5]
        team2 = combo[5:]

        def role_assign(team):
            return {role: team[i] for i, role in enumerate(roles)}

        t1_roles = role_assign(team1)
        t2_roles = role_assign(team2)

        role_diffs = [
            abs(players_data[t1_roles[r]][r] - players_data[t2_roles[r]][r])
            for r in roles
        ]
        if any(diff > 20 for diff in role_diffs):
            continue

        t1_total = sum(players_data[name][r] for name in team1 for r in roles)
        t2_total = sum(players_data[name][r] for name in team2 for r in roles)
        total_diff = abs(t1_total - t2_total)

        if total_diff <= 50 and total_diff < min_diff:
            min_diff = total_diff
            best_team = (t1_roles, t2_roles)

    if best_team:
        t1, t2 = best_team
        msg = "**✅ チーム分け完了！**\n\n**🔵 Team A**\n"
        for r in roles:
            msg += f"{r.upper()}: {t1[r]} ({players_data[t1[r]][r]})\n"
        msg += "\n**🔴 Team B**\n"
        for r in roles:
            msg += f"{r.upper()}: {t2[r]} ({players_data[t2[r]][r]})\n"
        await ctx.send(msg)
    else:
        await ctx.send("❌ 条件を満たすチーム構成が見つかりませんでした。")


# UptimeRobot用 Webサーバー起動
from keep_alive import keep_alive

keep_alive()

# トークン起動（.env使用）
import dotenv

dotenv.load_dotenv()
bot.run(os.getenv("DISCORD_TOKEN"))
try:
    client.run(TOKEN)
except:
    os.system("kill 1")
