import discord
from discord.ext import commands
import json
import os
from itertools import permutations
import re

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "abilities.json"
participants = {}  # {guild_id: {user_id: [lane1, lane2]}} または ['fill']
last_teams = {}

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_server_data(guild_id):
    data = load_data()
    return data.setdefault(str(guild_id), {})

def update_server_data(guild_id, server_data):
    data = load_data()
    data[str(guild_id)] = server_data
    save_data(data)

@bot.command()
async def hello(ctx):
    await ctx.send("こんにちは！Botは稼働中です。")

@bot.command()
async def bye(ctx):
    await ctx.send("Botを一時停止します。")

@bot.command()
async def ability(ctx, member: discord.Member, top: int, jg: int, mid: int, adc: int, sup: int):
    server_data = get_server_data(ctx.guild.id)
    server_data[str(member.id)] = {"top": top, "jg": jg, "mid": mid, "adc": adc, "sup": sup}
    update_server_data(ctx.guild.id, server_data)
    await ctx.send(f"{member.display_name} の能力値を登録しました。")

@bot.command()
async def delete_ability(ctx, member: discord.Member):
    server_data = get_server_data(ctx.guild.id)
    if str(member.id) in server_data:
        del server_data[str(member.id)]
        update_server_data(ctx.guild.id, server_data)
        await ctx.send(f"{member.display_name} の能力値を削除しました。")
    else:
        await ctx.send("そのユーザーのデータは存在しません。")

@bot.command()
async def show(ctx):
    server_data = get_server_data(ctx.guild.id)
    if not server_data:
        await ctx.send("登録されているデータがありません。")
        return

    msg = "**登録された能力値一覧**\n"
    for uid, stats in server_data.items():
        member = ctx.guild.get_member(int(uid))
        if not member:
            continue
        total = sum(stats.values())
        msg += f"{member.display_name}: Top {stats['top']}, Jg {stats['jg']}, Mid {stats['mid']}, Adc {stats['adc']}, Sup {stats['sup']} | 合計: {total}\n"
    await ctx.send(msg)

@bot.command()
async def join(ctx, *lanes):
    gid = ctx.guild.id
    if gid not in participants:
        participants[gid] = {}
    
    if not lanes:
        await ctx.send("希望レーンを2つ、または`fill`を指定してください（例：`!join top jg` または `!join fill`）")
        return

    if lanes[0].lower() == 'fill':
        participants[gid][ctx.author.id] = ['fill']
        await ctx.send(f"{ctx.author.display_name} をどのレーンでもOKとして登録しました。")
    elif len(lanes) == 2 and all(lane in ['top', 'jg', 'mid', 'adc', 'sup'] for lane in lanes):
        participants[gid][ctx.author.id] = list(lanes)
        await ctx.send(f"{ctx.author.display_name} を希望レーン {lanes[0]}, {lanes[1]} として登録しました。")
    else:
        await ctx.send("正しいレーンを2つ指定してください（top, jg, mid, adc, sup）")

@bot.command()
async def leave(ctx, member: discord.Member = None):
    target = member or ctx.author
    gid = ctx.guild.id
    if gid in participants and target.id in participants[gid]:
        del participants[gid][target.id]
        await ctx.send(f"{target.display_name} を参加リストから削除しました。")
    else:
        await ctx.send("そのユーザーは登録されていません。")

@bot.command()
async def make_teams(ctx, *, args=None):
    gid = ctx.guild.id
    if gid not in participants or len(participants[gid]) < 10:
        await ctx.send("十分な参加者がいません（最低10人必要）")
        return

    lane_threshold = 40
    team_threshold = 50

    if args:
        lane_match = re.search(r'lane_diff=(\d+)', args)
        team_match = re.search(r'team_diff=(\d+)', args)
        if lane_match:
            lane_threshold = int(lane_match.group(1))
        if team_match:
            team_threshold = int(team_match.group(1))

    server_data = get_server_data(ctx.guild.id)
    raw_participants = list(participants[gid].items())
    lanes = ['top', 'jg', 'mid', 'adc', 'sup']

    def generate_teams():
        for perm in permutations(raw_participants, 10):
            role_map = {}
            used = set()
            fill_pool = []

            for user_id, prefs in perm:
                if prefs == ['fill']:
                    fill_pool.append(user_id)

            for lane in lanes:
                for user_id, prefs in perm:
                    if user_id in used:
                        continue
                    if prefs != ['fill'] and lane in prefs:
                        role_map[lane] = user_id
                        used.add(user_id)
                        break
                else:
                    if fill_pool:
                        uid = fill_pool.pop()
                        role_map[lane] = uid
                        used.add(uid)

            if len(role_map) < 5:
                continue

            team1 = [(uid, server_data.get(str(uid), {})) for uid in list(role_map.values())[:5]]
            team2 = [(uid, server_data.get(str(uid), {})) for uid in list(role_map.values())[5:]]

            lane_diffs = [abs(team1[i][1].get(lanes[i], 0) - team2[i][1].get(lanes[i], 0)) for i in range(5)]
            total1 = sum(p[1].get(lanes[i], 0) for i, p in enumerate(team1))
            total2 = sum(p[1].get(lanes[i], 0) for i, p in enumerate(team2))
            total_diff = abs(total1 - total2)

            if all(diff <= lane_threshold for diff in lane_diffs) and total_diff <= team_threshold:
                return team1, team2, lane_diffs, total_diff
        return None

    result = generate_teams()

    if result:
        team1, team2, lane_diffs, total_diff = result
        last_teams[gid] = {"team1": [(ctx.guild.get_member(uid), data) for uid, data in team1],
                           "team2": [(ctx.guild.get_member(uid), data) for uid, data in team2]}

        msg = f"**✅ Team A** (lane_diff≤{lane_threshold}, team_diff≤{team_threshold})\n"
        for i in range(5):
            msg += f"{lanes[i]}: {team1[i][0]} ({team1[i][1].get(lanes[i], 0)})\n"
        msg += f"\n**✅ Team B**\n"
        for i in range(5):
            msg += f"{lanes[i]}: {team2[i][0]} ({team2[i][1].get(lanes[i], 0)})\n"
        await ctx.send(msg)
    else:
        await ctx.send(f"⚠ 条件を満たすチームが見つかりませんでした（lane_diff≤{lane_threshold}, team_diff≤{team_threshold}）\n可能な限り最小差で再編成してください。")

@bot.command()
async def win(ctx, team: str):
    if ctx.guild.id not in last_teams:
        await ctx.send("前回のチーム分けが見つかりません。先に !make_teams を行ってください。")
        return
    if team not in ["A", "B"]:
        await ctx.send("勝ったチームは A か B を指定してください。（例: !win A）")
        return

    teams = last_teams[ctx.guild.id]
    winner = teams['team1'] if team == "A" else teams['team2']
    loser = teams['team2'] if team == "A" else teams['team1']
    server_data = get_server_data(ctx.guild.id)
    lanes = ['top', 'jg', 'mid', 'adc', 'sup']

    for i in range(5):
        win_id = str(winner[i][0].id)
        lose_id = str(loser[i][0].id)
        lane = lanes[i]
        server_data[win_id][lane] += 2
        server_data[lose_id][lane] = max(0, server_data[lose_id][lane] - 2)

    update_server_data(ctx.guild.id, server_data)
    await ctx.send("勝敗結果を反映しました！")

@bot.command()
async def ranking(ctx):
    server_data = get_server_data(ctx.guild.id)
    if not server_data:
        await ctx.send("データが存在しません。")
        return

    lanes = ['top', 'jg', 'mid', 'adc', 'sup']
    msg = "**📊 各レーンの現在の能力値**\n"
    for lane in lanes:
        msg += f"\n🔹 {lane.capitalize()}\n"
        sorted_players = sorted(server_data.items(), key=lambda item: item[1].get(lane, 0), reverse=True)
        for uid, stats in sorted_players:
            member = ctx.guild.get_member(int(uid))
            if member:
                msg += f"{member.display_name}: {stats.get(lane, 0)}\n"
    await ctx.send(msg)

@bot.command(name="help_lolgap2")
async def help_command(ctx):
    await ctx.send("""
📘 Botコマンド一覧

!join top mid / !join fill - レーン希望で参加（2つまで or fill）
!leave @user - 参加リストから削除
!make_teams lane_diff=20 team_diff=50 - チーム分け（VC不要・参加者10人）
!ability @user 10 10 10 10 10 - 能力値登録
!delete_ability @user - 能力値削除
!show - 能力一覧
!ranking - 各レーン順位
!win A / B - 勝利チーム報告
""")

bot.run(os.environ['DISCORD_BOT_TOKEN'])
