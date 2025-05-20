import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
from flask import Flask
from threading import Thread
import unicodedata
from tabulate import tabulate


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)
app = Flask('')

active = True
DATA_FILE = 'ability_data.json'
# ファイルの先頭付近に追加（グローバル変数）
last_teams = {}  # guild_id をキーにしてチーム情報を保存


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
    await ctx.send("Botが起動しました！おはよ～")

@bot.command()
async def bye(ctx):
    global active
    active = False
    await ctx.send("Botが休止しました！おやすみ～")

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
        await ctx.send(f"{member.mention} のデータは存在しません；；")





def get_display_width(text):
    """文字列の見た目の幅を取得（全角2、半角1としてカウント）"""
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in text)

def pad_display_name(name, target_width):
    """指定幅に合わせて空白を追加"""
    current_width = get_display_width(name)
    padding = target_width - current_width
    return name + ' ' * max(0, padding)

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

    # 表の作成
    table = []
    name_column_width = 16  # 表示名の目標幅（全角換算）

    for uid_str, values in sorted_data:
        uid = int(uid_str)
        member = ctx.guild.get_member(uid)
        raw_name = member.display_name if member else "不明なユーザー"
        name = pad_display_name(raw_name, name_column_width)

        total = values['top'] + values['jg'] + values['mid'] + values['adc'] + values['sup']
        table.append([
            f"{total:>5}", name,
            f"{values['top']:>3}", f"{values['jg']:>3}", f"{values['mid']:>4}",
            f"{values['adc']:>4}", f"{values['sup']:>4}"
        ])

    headers = ["Total", "Name", "Top", "Jg", "Mid", "Adc", "Sup"]
    msg = "```\n" + tabulate(table, headers=headers, tablefmt="plain") + "\n```"
    await ctx.send(msg)











@bot.command()
async def make_teams(ctx, *, exclude: commands.Greedy[discord.Member] = []):
    if not active:
        return

    voice_state = ctx.author.voice
    if not voice_state or not voice_state.channel:
        await ctx.send("VCに人が足りませんよ！")
        return

    channel = voice_state.channel
    # 除外指定がある場合、そのメンバーを除外
    members = [m for m in channel.members if not m.bot and m not in exclude]

    if len(members) < 10:
        await ctx.send("VC内に十分なプレイヤーがいません。（除外後）")
        return

    # VC内から10人を選ぶ（ランダムでもいいが、先頭10人を選んでいる）
    selected = members[:10]
    server_data = get_server_data(ctx.guild.id)

    player_data = []
    for m in selected:
        if str(m.id) in server_data:
            player_data.append((m, server_data[str(m.id)]))
        else:
            await ctx.send(f"{m.mention} の能力値が未登録です！!ability で登録できますよ！")
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
                    if result:
        team1, team2 = result

        # チームデータ保存（勝敗更新用）
        last_teams[ctx.guild.id] = {
            'team1': team1,
            'team2': team2
        }
        return None

    result = valid_teams(player_data)
    if result:
        team1, team2 = result
        lanes = ['top', 'jg', 'mid', 'adc', 'sup']
        msg = "**✅ Team A**\n"
        for i in range(5):
            msg += f"{lanes[i]}: {team1[i][0].mention} ({team1[i][1][lanes[i]]})\n"
        msg += "\n**✅ Team B**\n"
        for i in range(5):
            msg += f"{lanes[i]}: {team2[i][0].mention} ({team2[i][1][lanes[i]]})\n"
        await ctx.send(msg)
    else:
        await ctx.send("⚠ 条件に合うチーム分けが見つかりませんでした。ごめんなさい。")

@bot.command()
async def win(ctx, team: str):
    if not active:
        return

    if ctx.guild.id not in last_teams:
        await ctx.send("直前のチーム分けデータがありません。まず !make_teams を実行してください。")
        return

    if team not in ['A', 'B']:
        await ctx.send("勝ったチームは 'A' または 'B' で指定してください。例: `!win A`")
        return

    server_data = get_server_data(ctx.guild.id)
    teams = last_teams[ctx.guild.id]
    lanes = ['top', 'jg', 'mid', 'adc', 'sup']

    win_team = teams['team1'] if team == 'A' else teams['team2']
    lose_team = teams['team2'] if team == 'A' else teams['team1']

    for i in range(5):
        lane = lanes[i]

        # 勝者の能力値 +2（最大120）
        win_member = win_team[i][0]
        win_uid = str(win_member.id)
        server_data[win_uid][lane] = min(server_data[win_uid][lane] + 2, 120)

        # 敗者の能力値 -2（最小0）
        lose_member = lose_team[i][0]
        lose_uid = str(lose_member.id)
        server_data[lose_uid][lane] = max(server_data[lose_uid][lane] - 2, 0)

    set_server_data(ctx.guild.id, server_data)
    await ctx.send(f"✅ Team {team} の勝利を記録しました！能力値を更新しました。")


@bot.command(name="help_lolgap2")
async def help_command(ctx):
    help_text = """
📘 Botコマンド一覧

!hello
　→ Botが起動しているか確認します。

!bye
　→ Botを一時停止します。

!ability @ユーザー Top Jg Mid Adc Sup
　→ 指定したユーザーの能力値を登録または更新します。
　例: !ability @deco 20 15 30 25 10

!delete_ability @ユーザー
　→ 指定したユーザーの能力値を削除します。

!show
　→ 登録済みメンバーの能力値を一覧表示します（ソート付き）。

!make_teams [@除外したいユーザー ...]
　→ VC内の10人を対象にチーム分けを行います。
　　レーンごとの能力差が20以内、チーム合計が50以内の組み合わせを探します。
　　11人以上いる場合、除外したいメンバーを指定してください。
　例: !make_teams @deco
 
 !win A/B
  →能力値を勝ったチーム+2、負けたチームは-2されます。
 """
    await ctx.send(help_text)


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
