import discord
from discord.ext import commands
import asyncio
import random
import json
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

active = True
ability_data = {}  # server_id -> { user_id: {"top": int, "jg": int, ...} }

DATA_FILE = 'abilities.json'

# Load data from file
def load_data():
    global ability_data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            ability_data = json.load(f)

# Save data to file
def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(ability_data, f, indent=2)

@bot.event
async def on_ready():
    load_data()
    print(f'Logged in as {bot.user}')

@bot.command()
async def hello(ctx):
    global active
    active = True
    await ctx.send("Bot is now active!")

@bot.command()
async def bye(ctx):
    global active
    active = False
    await ctx.send("Bot is now inactive. Use !hello to reactivate.")

@bot.command()
async def register_ability(ctx, member: discord.Member, top: int, jg: int, mid: int, adc: int, sup: int):
    if not active:
        return
    server_id = str(ctx.guild.id)
    user_id = str(member.id)

    if server_id not in ability_data:
        ability_data[server_id] = {}

    ability_data[server_id][user_id] = {
        "name": member.display_name,
        "top": top,
        "jg": jg,
        "mid": mid,
        "adc": adc,
        "sup": sup
    }
    save_data()
    await ctx.send(f"{member.mention} の能力値を登録/更新しました。")

@bot.command()
async def show_abilities(ctx):
    if not active:
        return
    server_id = str(ctx.guild.id)
    if server_id not in ability_data or not ability_data[server_id]:
        await ctx.send("まだ能力値が登録されていません。")
        return

    embed = discord.Embed(title="登録済み能力値", color=0x00ff00)
    for uid, info in ability_data[server_id].items():
        total = info['top'] + info['jg'] + info['mid'] + info['adc'] + info['sup']
        embed.add_field(
            name=info['name'],
            value=f"Top: {info['top']}, JG: {info['jg']}, Mid: {info['mid']}, ADC: {info['adc']}, Sup: {info['sup']}, 合計: {total}",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command()
async def team_split(ctx, vc_name: str, *excluded: discord.Member):
    if not active:
        return
    server_id = str(ctx.guild.id)
    voice_channel = discord.utils.get(ctx.guild.voice_channels, name=vc_name)
    if not voice_channel:
        await ctx.send("指定されたVCが見つかりません。")
        return

    members = [m for m in voice_channel.members if m not in excluded]
    if len(members) < 10:
        await ctx.send("10人以上のメンバーが必要です。")
        return

    selected = members[:10]
    user_data = ability_data.get(server_id, {})

    candidates = []
    for m in selected:
        if str(m.id) in user_data:
            data = user_data[str(m.id)]
            data['id'] = m.id
            candidates.append(data)

    if len(candidates) < 10:
        await ctx.send("10人分の能力値が登録されていません。")
        return

    roles = ['top', 'jg', 'mid', 'adc', 'sup']

    def is_valid(team1, team2):
        for r in roles:
            if abs(team1[r][1] - team2[r][1]) > 20:
                return False
        total1 = sum(v for _, v in team1.values())
        total2 = sum(v for _, v in team2.values())
        return abs(total1 - total2) <= 50

    from itertools import permutations
    for perm in permutations(candidates, 10):
        t1 = perm[:5]
        t2 = perm[5:]
        team1 = {}
        team2 = {}
        used1 = set()
        used2 = set()
        for role in roles:
            for p in t1:
                if role not in used1:
                    team1[role] = (p['name'], p[role])
                    used1.add(role)
                    break
            for p in t2:
                if role not in used2:
                    team2[role] = (p['name'], p[role])
                    used2.add(role)
                    break
        if len(team1) == 5 and len(team2) == 5 and is_valid(team1, team2):
            msg = "**チーム分け結果**\n"
            msg += "\n**Team A**\n" + "\n".join(f"{r.upper()}: {team1[r][0]} ({team1[r][1]})" for r in roles)
            msg += "\n\n**Team B**\n" + "\n".join(f"{r.upper()}: {team2[r][0]} ({team2[r][1]})" for r in roles)
            await ctx.send(msg)
            return

    await ctx.send("条件を満たすチーム分けが見つかりませんでした。")

# Flask for uptime (Render/UptimeRobot)
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

# Start the bot (tokenはRenderの環境変数に設定)
import os
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
