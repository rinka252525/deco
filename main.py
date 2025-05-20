import discord
from discord.ext import commands, tasks
import asyncio
from flask import Flask
from threading import Thread


# IntentsとBotの初期化
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

# データ構造
ability_data = {}
active = True

# Flaskアプリで常駐
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 起動・停止
@bot.command()
async def hello(ctx):
    global active
    active = True
    await ctx.send("Botが起動しました。")

@bot.command()
async def bye(ctx):
    global active
    active = False
    await ctx.send("Botが反応を停止します。")

# 能力登録
@bot.command()
async def register_ability(ctx, member: discord.Member, top: int, jg: int, mid: int, adc: int, sup: int):
    if not active:
        return

    guild_id = str(ctx.guild.id)
    user_id = str(member.id)

    if guild_id not in ability_data:
        ability_data[guild_id] = {}

    ability_data[guild_id][user_id] = {
        "name": member.display_name,
        "top": top,
        "jg": jg,
        "mid": mid,
        "adc": adc,
        "sup": sup
    }
    await ctx.send(f"{member.display_name} の能力値を登録/更新しました。")

# 能力表示
@bot.command()
async def show_abilities(ctx):
    if not active:
        return

    guild_id = str(ctx.guild.id)
    if guild_id not in ability_data or not ability_data[guild_id]:
        await ctx.send("このサーバーには登録データがありません。")
        return

    msg = "登録されている能力値一覧：\n"
    for data in ability_data[guild_id].values():
        total = data['top'] + data['jg'] + data['mid'] + data['adc'] + data['sup']
        msg += (f"{data['name']}: top={data['top']} jg={data['jg']} mid={data['mid']} adc={data['adc']} sup={data['sup']} "
                f"| 合計={total}\n")
    await ctx.send(f"```{msg}```")

# チーム分け
from itertools import permutations
import random

@bot.command()
async def team_split(ctx, *excluded: discord.Member):
    if not active:
        return

    voice_state = ctx.author.voice
    if voice_state is None or voice_state.channel is None:
        await ctx.send("ボイスチャンネルに参加してから実行してください。")
        return

    members = [m for m in voice_state.channel.members if m.bot is False and m not in excluded]
    if len(members) < 10:
        await ctx.send("VCに10人以上のプレイヤーが必要です。")
        return

    members = members[:10]
    guild_id = str(ctx.guild.id)

    user_data = []
    for m in members:
        user_id = str(m.id)
        if guild_id in ability_data and user_id in ability_data[guild_id]:
            user_data.append((m, ability_data[guild_id][user_id]))
        else:
            await ctx.send(f"{m.display_name} の能力値が登録されていません。")
            return

    roles = ["top", "jg", "mid", "adc", "sup"]

    for perm in permutations(user_data, 10):
        team1 = perm[:5]
        team2 = perm[5:]

        valid = True
        lane_diff = []
        total1 = 0
        total2 = 0

        for i, role in enumerate(roles):
            p1 = team1[i][1][role]
            p2 = team2[i][1][role]
            diff = abs(p1 - p2)
            if diff > 20:
                valid = False
                break
            lane_diff.append(diff)
            total1 += p1
            total2 += p2

        if valid and abs(total1 - total2) <= 50:
            result = "【チーム分け】\n"
            result += "--- Team A ---\n"
            for i, role in enumerate(roles):
                result += f"{role.upper()}: {team1[i][0].display_name} ({team1[i][1][role]})\n"
            result += f"合計: {total1}\n"

            result += "--- Team B ---\n"
            for i, role in enumerate(roles):
                result += f"{role.upper()}: {team2[i][0].display_name} ({team2[i][1][role]})\n"
            result += f"合計: {total2}\n"

            await ctx.send(f"```{result}```")
            return

    await ctx.send("条件に合うチーム分けが見つかりませんでした。")

# 実行
keep_alive()
bot.run(TOKEN)
