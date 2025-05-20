import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
from flask import Flask
from threading import Thread
from tabulate import tabulate
import unicodedata


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)
app = Flask('')

active = True
DATA_FILE = 'ability_data.json'

# --- Utility Functions ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_server_data(guild_id):
    data = load_data()
    return data.setdefault(str(guild_id), {})

def set_server_data(guild_id, server_data):
    data = load_data()
    data[str(guild_id)] = server_data
    save_data(data)

# --- Bot Commands ---
@bot.command()
async def hello(ctx):
    global active
    active = True
    await ctx.send("Botが起動しました！")

@bot.command()
async def bye(ctx):
    global active
    active = False
    await ctx.send("Botが休止しました！")

@bot.command()
async def ability(ctx, member: discord.Member, top: int, jg: int, mid: int, adc: int, sup: int):
    if not active:
        return
    server_data = get_server_data(ctx.guild.id)
    server_data[str(member.id)] = {'mention': member.mention, 'top': top, 'jg': jg, 'mid': mid, 'adc': adc, 'sup': sup}
    set_server_data(ctx.guild.id, server_data)
    await ctx.send(f"{member.mention} の能力値を登録/更新しました。")

@bot.command()
async def delete_ability(ctx, member: discord.Member):
    if not active:
        return
    server_data = get_server_data(ctx.guild.id)
    if str(member.id) in server_data:
        del server_data[str(member.id)]
        set_server_data(ctx.guild.id, server_data)
        await ctx.send(f"{member.mention} の能力値を削除しました。")
    else:
        await ctx.send(f"{member.mention} のデータは存在しません。")



def get_display_width(text):
    """文字列の見た目の幅を取得（全角2、半角1としてカウント）"""
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in text)

def pad_display_name(name, width):
    """指定幅に合わせてパディング"""
    current_width = get_display_width(name)
    padding = width - current_width
    return name + ' ' * padding

@bot.command()
async def show(ctx):
    if not active:
        return

    server_data = get_server_data(ctx.guild.id)
    if not server_data:
        await ctx.send("データがありません。")
        return

    # 合計値でソート
    sorted_data = sorted(
        server_data.items(),
        key=lambda item: (
            item[1]['top'] + item[1]['jg'] + item[1]['mid'] + item[1]['adc'] + item[1]['sup']
        ),
        reverse=True
    )

    table = []
    for uid_str, values in sorted_data:
        uid = int(uid_str)
        member = ctx.guild.get_member(uid)
        name = member.display_name if member else "不明なユーザー"
        total = values['top'] + values['jg'] + values['mid'] + values['adc'] + values['sup']
        table.append([
            total, name, values['top'], values['jg'],
            values['mid'], values['adc'], values['sup']
        ])

    headers = ["Total", "Name", "Top", "Jg", "Mid", "Adc", "Sup"]
    msg = "```\n" + tabulate(table, headers=headers, tablefmt="plain") + "\n```"
    await ctx.send(msg)









@bot.command()
async def make_teams(ctx, exclude: commands.Greedy[discord.Member] = None):
    if not active:
        return
    voice_state = ctx.author.voice
    if not voice_state or not voice_state.channel:
        await ctx.send("VCに参加している必要があります。")
        return
    channel = voice_state.channel
    members = [m for m in channel.members if not m.bot and (exclude is None or m not in exclude)]

    if len(members) < 10:
        await ctx.send("VC内に十分なプレイヤーがいません。")
        return

    selected = members[:10]
    server_data = get_server_data(ctx.guild.id)

    player_data = []
    for m in selected:
        if str(m.id) in server_data:
            player_data.append((m, server_data[str(m.id)]))
        else:
            await ctx.send(f"{m.mention} の能力値が未登録です。")
            return

    from itertools import permutations

    def valid_teams(data):
        for perm in permutations(data, 10):
            team1 = perm[:5]
            team2 = perm[5:]
            lanes = ['top', 'jg', 'mid', 'adc', 'sup']
            ok = True
            for i in range(5):
                diff = abs(team1[i][1][lanes[i]] - team2[i][1][lanes[i]])
                if diff > 20:
                    ok = False
                    break
            if not ok:
                continue
            sum1 = sum(v[1][lanes[i]] for i, v in enumerate(team1))
            sum2 = sum(v[1][lanes[i]] for i, v in enumerate(team2))
            if abs(sum1 - sum2) <= 50:
                return team1, team2
        return None

    result = valid_teams(player_data)
    if result:
        team1, team2 = result
        lanes = ['top', 'jg', 'mid', 'adc', 'sup']
        msg = "**Team A**\n"
        for i in range(5):
            msg += f"{lanes[i]}: {team1[i][0].mention} ({team1[i][1][lanes[i]]})\n"
        msg += "\n**Team B**\n"
        for i in range(5):
            msg += f"{lanes[i]}: {team2[i][0].mention} ({team2[i][1][lanes[i]]})\n"
        await ctx.send(msg)
    else:
        await ctx.send("条件に合うチーム分けが見つかりませんでした。")

# --- Flask Keep Alive ---
@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Main ---
keep_alive()
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
