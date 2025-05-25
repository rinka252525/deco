import discord
from discord.ext import commands
import json
import os
from itertools import permutations
import re
import random
from itertools import combinations, permutations

intents = discord.Intents.default()
intents = discord.Intents.all()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

lanes = ['top', 'jg', 'mid', 'adc', 'sup']

ability_file = 'abilities.json'
team_file = 'last_teams.json'
match_history_file = 'match_history.json'
participants = {}  # {guild_id: {user_id: [lane1, lane2]}} または ['fill']
history_file = 'history.json'
current_teams = {}
last_teams ={"team_a": {uid: lane}, "team_b": {uid: lane}}
# Ability data structure example:
# {
#   "guild_id": {
#       "user_id": {
#           "top": 100,
#           "jg": 80,
#           "mid": 90,
#           "adc": 85,
#           "sup": 95,
#           "matches": {"top": 3, "jg": 0, ...},
#           "custom_history": [
#               {"lane": "top", "result": "win", "change": 10},
#               {"lane": "mid", "result": "lose", "change": -10},
#           ]
#       }
#   }
# }
lanes = ['top', 'jg', 'mid', 'adc', 'sup']

# ファイル読み込み/保存用関数
def load_data(file):
    if os.path.exists(file):
        with open(file, 'r') as f:
            return json.load(f)
    return {}

def save_data(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)

# JSON読み書き関数
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def get_server_data(guild_id):
    data = load_data(ability_file)
    return data.setdefault(str(guild_id), {})

def update_server_data(guild_id, server_data):
    data = load_data(ability_file)
    data[str(guild_id)] = server_data
    save_data(ability_file, data)


@bot.command()
async def hello(ctx):
    await ctx.send("こんにちは！Botは稼働中です。")

@bot.command()
async def bye(ctx):
    await ctx.send("Botを一時停止します。")

# 能力登録
@bot.command()
async def ability(ctx, member: discord.Member, top: int, jg: int, mid: int, adc: int, sup: int):
    guild_id = str(ctx.guild.id)
    data = load_data(ability_file)

    if guild_id not in data:
        data[guild_id] = {}

    user_id = str(member.id)
    data[guild_id][user_id] = {
        'name': member.name,
        'top': top,
        'jg': jg,
        'mid': mid,
        'adc': adc,
        'sup': sup
    }

    save_data(ability_file, data)
    await ctx.send(f"{member.mention} の能力値を登録しました。")




@bot.command()
async def delete_ability(ctx, member: discord.Member):
    server_data = get_server_data(ctx.guild.id)
    if str(member.id) in server_data:
        del server_data[str(member.id)]
        update_server_data(ctx.guild.id, server_data)
        await ctx.send(f"{member.display_name} の能力値を削除しました。")
    else:
        await ctx.send("そのユーザーのデータは存在しません。")

# 能力一覧表示（合計順 + 詳細）
@bot.command()
async def show(ctx):
    data = load_data(ability_file)
    guild_id = str(ctx.guild.id)
    
    if guild_id not in data or not data[guild_id]:
        await ctx.send("まだ能力が登録されていません。")
        return

    sorted_data = sorted(
        data[guild_id].items(),
        key=lambda x: sum(x[1][lane] for lane in ['top', 'jg', 'mid', 'adc', 'sup']),
        reverse=True
    )
    msg = "**能力一覧（合計順）**\n"
    for user_id, info in sorted_data:
        total = sum(info[lane] for lane in ['top', 'jg', 'mid', 'adc', 'sup'])
        msg += f"<@{user_id}> top{info['top']} jg{info['jg']} mid{info['mid']} adc{info['adc']} sup{info['sup']} | 合計{total}\n"
    await ctx.send(msg)


# チーム分けユーティリティ
def calculate_total(team):
    return sum(sum(p[1].values()) for p in team)

def format_teams(team_a, team_b):
    def fmt(team):
        return '\n'.join([f"{name} ({' / '.join([f'{lane}:{score}' for lane, score in stats.items()])})" for name, stats in team])
    total_a = calculate_total(team_a)
    total_b = calculate_total(team_b)
    return f"**Team A** (Total: {total_a})\n{fmt(team_a)}\n\n**Team B** (Total: {total_b})\n{fmt(team_b)}"





@bot.command()
async def join(ctx, *args):
    global participants

    # メンバーの特定
    mentions = ctx.message.mentions
    if mentions:
        member = mentions[0]
        args = args[1:]  # 最初のメンションを除く
    else:
        member = ctx.author

    if len(args) != 2:
        await ctx.send("希望レーンを2つ指定してください。例：!join @user top mid または !join top mid")
        return

    lane1 = args[0].lower()
    lane2 = args[1].lower()
    preferred_lanes = [lane1, lane2]

    valid_lanes = ['top', 'jg', 'mid', 'adc', 'sup', 'fill']
    if lane1 not in valid_lanes or lane2 not in valid_lanes:
        await ctx.send(f"指定されたレーンが無効です。\n有効なレーン: {', '.join(valid_lanes)}")
        return

    guild_id = ctx.guild.id
    user_id = member.id

    if guild_id not in participants:
        participants[guild_id] = {}

    participants[guild_id][user_id] = preferred_lanes
    await ctx.send(f"{member.display_name} が {preferred_lanes} で参加登録しました。")








@bot.command()
async def leave(ctx, member: discord.Member = None):
    global participants
    guild_id = ctx.guild.id  # 修正: str() しない

    if member is None:
        member = ctx.author

    if guild_id not in participants or member.id not in participants[guild_id]:
        await ctx.send(f"{member.display_name} は参加していません。")
        return

    del participants[guild_id][member.id]
    await ctx.send(f"{member.display_name} の参加を解除しました。")





@bot.command()
async def participants_list(ctx):
    guild_id = ctx.guild.id  # 修正: str() しない

    if guild_id not in participants or not participants[guild_id]:
        await ctx.send("現在、参加者は登録されていません。")
        return

    msg = "**現在の参加者一覧：**\n"
    for uid, lanes in participants[guild_id].items():  # 修正: uid は int のままでOK
        member = ctx.guild.get_member(uid)
        if not member:
            continue
        lane1, lane2 = lanes
        msg += f"{member.display_name}：{lane1.upper()} / {lane2.upper()}\n"

    await ctx.send(msg)












@bot.command()
async def make_teams(ctx, lane_diff: int = 40, team_diff: int = 50):
    guild_id = ctx.guild.id
    lanes = ['top', 'jg', 'mid', 'adc', 'sup']

    # ギルドIDがparticipantsに存在しない、または参加者が10人未満の場合は中断
    if guild_id not in participants or len(participants[guild_id]) < 10:
        await ctx.send("参加者が10人未満です。")
        return

    member_ids = list(participants[guild_id].keys())
    server_data = get_server_data(guild_id)

    # 能力値未登録のメンバーがいる場合は中断
    if not all(str(mid) in server_data for mid in member_ids):
        unregistered_ids = [mid for mid in member_ids if str(mid) not in server_data]
        mention_list = ', '.join(f'<@{uid}>' for uid in unregistered_ids)
        await ctx.send(f"一部の参加者が能力値を登録していません：{mention_list}")
        return

    best_score = float('inf')
    best_result = None
    warnings = []

    for team1_ids in combinations(member_ids, 5):
        team2_ids = [uid for uid in member_ids if uid not in team1_ids]

        for team1_roles in permutations(lanes):
            try:
                role_map = {}
                assigned = set()

                # チーム1のロール割り当て
                for uid, lane in zip(team1_ids, team1_roles):
                    role_map[uid] = lane
                    assigned.add(lane)

                # チーム2のロール割り当て（希望レーン考慮）
                valid = False
                for team2_roles in permutations(lanes):
                    try_role_map = role_map.copy()
                    success = True
                    for uid, lane in zip(team2_ids, team2_roles):
                        prefs = participants[guild_id].get(uid, [])
                        if prefs and lane not in prefs and 'fill' not in prefs:
                            success = False
                            break
                        try_role_map[uid] = lane
                    if success:
                        role_map = try_role_map
                        valid = True
                        break

                if not valid or len(role_map) != 10:
                    continue

                # チームスコアと差分評価
                team1_score = 0
                team2_score = 0
                total_lane_diff = 0
                exceeded = False

                for lane in lanes:
                    uid1 = [u for u in team1_ids if role_map[u] == lane][0]
                    uid2 = [u for u in team2_ids if role_map[u] == lane][0]
                    val1 = server_data[str(uid1)][lane]
                    val2 = server_data[str(uid2)][lane]
                    team1_score += val1
                    team2_score += val2
                    diff = abs(val1 - val2)
                    total_lane_diff += diff
                    if diff > lane_diff:
                        exceeded = True

                team_diff_value = abs(team1_score - team2_score)
                if team_diff_value > team_diff:
                    exceeded = True

                score = total_lane_diff + team_diff_value
                if exceeded:
                    score += 1000

                if score < best_score:
                    best_score = score
                    best_result = (team1_ids, team2_ids, role_map)
                    warnings = []
                    if exceeded:
                        for lane in lanes:
                            uid1 = [u for u in team1_ids if role_map[u] == lane][0]
                            uid2 = [u for u in team2_ids if role_map[u] == lane][0]
                            val1 = server_data[str(uid1)][lane]
                            val2 = server_data[str(uid2)][lane]
                            diff = abs(val1 - val2)
                            if diff > lane_diff:
                                warnings.append(f"{lane} の能力差が {diff} あります。")
                        if team_diff_value > team_diff:
                            warnings.append(f"チーム合計の能力差が {team_diff_value} あります。")

            except Exception as e:
                print(f"make_teams exception: {e}")
                continue

    if not best_result:
        await ctx.send("チーム分けに失敗しました。条件を緩和するか、参加者の希望レーンや能力値を見直してください。")
        return

    team1_ids, team2_ids, role_map = best_result

    # 表示用フォーマット関数
    def team_description(team_ids):
        lines = []
        for uid in team_ids:
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            lane = role_map[uid]
            ability = server_data[str(uid)][lane]
            lines.append(f"{lane.upper()}: {name} ({ability})")
        return '\n'.join(lines)

    team_a_total = sum(server_data[str(uid)][role_map[uid]] for uid in team1_ids)
    team_b_total = sum(server_data[str(uid)][role_map[uid]] for uid in team2_ids)

   # msg = f"**Team A (Total: {team_a_total})**\n{team_description(team1_ids)}\n\n"
   # msg += f"**Team B (Total: {team_b_total})**\n{team_description(team2_ids)}\n"

    #if warnings:
        #msg += "\n⚠️ **警告**:\n" + "\n".join(warnings)

    #await ctx.send(msg)

    # チーム情報を保存
    global last_teams
    last_teams[str(guild_id)] = {
        "team_a": {uid: role_map[uid] for uid in team1_ids},
        "team_b": {uid: role_map[uid] for uid in team2_ids}
    }
    save_data(team_file, last_teams)

    # 名前付き情報も保存
    def sort_by_lane(team):
        return sorted(team, key=lambda x: lanes.index(x[1]))

    team1_named = [(ctx.guild.get_member(uid), role_map[uid]) for uid in team1_ids]
    team2_named = [(ctx.guild.get_member(uid), role_map[uid]) for uid in team2_ids]
    team1_sorted = sort_by_lane(team1_named)
    team2_sorted = sort_by_lane(team2_named)

    def calc_team_score(team):
        return sum(server_data[str(m.id)][lane] for m, lane in team if m)

    score1 = calc_team_score(team1_sorted)
    score2 = calc_team_score(team2_sorted)

    def format_team(team, score):
        lines = [f"**Total: {score}**"]
        for member, lane in team:
            if member:
                val = server_data[str(member.id)][lane]
                lines.append(f"{lane.upper()}: {member.display_name} ({val})")
        return "\n".join(lines)

    team_msg = "**チーム分け結果（再表示）**\n\n"
    team_msg += "__**Team A**__\n" + format_team(team1_sorted, score1) + "\n\n"
    team_msg += "__**Team B**__\n" + format_team(team2_sorted, score2)

    if warnings:
        team_msg += "\n⚠️ **警告**:\n" + "\n".join(warnings)

    await ctx.send(team_msg)

    # JSON保存
    teams = {
        'A': [m.display_name for m, _ in team1_sorted if m],
        'B': [m.display_name for m, _ in team2_sorted if m]
    }
    save_json(team_file, teams)

    with open("current_teams.json", "w", encoding="utf-8") as f:
        json.dump({
            'A': {lane: m.display_name for m, lane in team1_sorted if m},
            'B': {lane: m.display_name for m, lane in team2_sorted if m}
        }, f, indent=4, ensure_ascii=False)



# !swap @user1 @user2
@bot.command()
async def swap(ctx, member1: discord.Member, member2: discord.Member):
    guild_id = str(ctx.guild.id)
    last_teams = load_data(team_file)

    if guild_id not in last_teams or "team_a" not in last_teams[guild_id] or "team_b" not in last_teams[guild_id]:
        await ctx.send("直近のチームが存在しません。")
        return

    all_teams = {**last_teams[guild_id]['team_a'], **last_teams[guild_id]['team_b']}
    uid1 = str(member1.id)
    uid2 = str(member2.id)

    if uid1 not in all_teams or uid2 not in all_teams:
        await ctx.send("指定したメンバーがチームにいません。")
        return

    # レーンを入れ替える
    lane1 = all_teams[uid1]
    lane2 = all_teams[uid2]

    for team_key in ['team_a', 'team_b']:
        if uid1 in last_teams[guild_id][team_key]:
            last_teams[guild_id][team_key][uid2] = lane1
            del last_teams[guild_id][team_key][uid1]
        if uid2 in last_teams[guild_id][team_key]:
            last_teams[guild_id][team_key][uid1] = lane2
            del last_teams[guild_id][team_key][uid2]

    save_data(team_file, last_teams)

    await ctx.send(f"{member1.display_name} と {member2.display_name} のレーンを入れ替えました。")

# !win A または !win B
# 勝敗報告
@bot.command()
async def win(ctx, result: str):
    if result not in ['A', 'B']:
        await ctx.send("!win A または !win B の形式で入力してください。")
        return

    guild_id = str(ctx.guild.id)
    last_teams = load_data(team_file)
    if guild_id not in last_teams or 'team_a' not in last_teams[guild_id] or 'team_b' not in last_teams[guild_id]:
        await ctx.send("直近のチーム情報が見つかりません。")
        return

    abilities = load_data(ability_file)
    history = load_data(history_file)

    winners = last_teams[guild_id]['team_a'] if result == 'A' else last_teams[guild_id]['team_b']
    losers = last_teams[guild_id]['team_b'] if result == 'A' else last_teams[guild_id]['team_a']

    for team, is_win in [(winners, True), (losers, False)]:
        for uid, lane in team.items():
            if uid not in abilities:
                continue
            if uid not in history:
                history[uid] = {'count': 0}
            history[uid]['count'] += 1
            match_count = history[uid]['count']
            delta = 10 if match_count <= 5 else 2

            # 勝者: +, 敗者: -
            if lane in abilities[uid]:
                if is_win:
                    abilities[uid][lane] += delta
                else:
                    abilities[uid][lane] = max(0, abilities[uid][lane] - delta)

    save_data(ability_file, abilities)
    save_data(history_file, history)

    await ctx.send("勝敗を記録し、能力値を更新しました。")




@bot.command()
async def show_custom(ctx):
    server_data = get_server_data(ctx.guild.id)
    if not server_data:
        await ctx.send("データが存在しません。")
        return

    msg = "**📘 各プレイヤーのカスタム戦績**\n"
    for uid, stats in server_data.items():
        member = ctx.guild.get_member(int(uid))
        if not member:
            continue

        msg += f"\n🔹 {member.display_name}\n"
        history = stats.get("custom_history", [])
        if not history:
            msg += "　記録なし\n"
            continue

        lane_histories = {}
        for entry in history:
            lane_histories.setdefault(entry['lane'], []).append(entry)

        for lane, records in lane_histories.items():
            msg += f"　- {lane}: " + ", ".join([f"{r['result']}({r['change']:+})" for r in records]) + "\n"

    await ctx.send(msg)

# bot.run(...) は既に実行中のコードで保持
# 他のコマンドとの統合が必要な場合はお知らせください。


@bot.command()
async def ranking(ctx):
    server_data = get_server_data(ctx.guild.id)
    if not server_data:
        await ctx.send("データが存在しません。")
        return

    lanes = ['top', 'jg', 'mid', 'adc', 'sup']
    rankings = {lane: [] for lane in lanes}

    for uid, stats in server_data.items():
        member = ctx.guild.get_member(int(uid))
        if not member:
            continue
        for lane in lanes:
            rankings[lane].append((member.display_name, stats.get(lane, 0)))

    msg = "**🔝 レーン別ランキング**\n"
    for lane in lanes:
        msg += f"\n**{lane.upper()}**\n"
        sorted_ranks = sorted(rankings[lane], key=lambda x: x[1], reverse=True)
        for i, (name, score) in enumerate(sorted_ranks, 1):
            msg += f"{i}. {name} - {score}\n"

    await ctx.send(msg)


@bot.command()
async def reset(ctx):
    gid = ctx.guild.id
    if gid in participants:
        participants[gid].clear()
        await ctx.send("✅ 参加リストをリセットしました。")
    else:
        await ctx.send("参加リストはすでに空です。")

@bot.command()
async def history(ctx):
    history_data = load_json("history.json")
    ability_data = load_json("ability.json")

    if not history_data:
        await ctx.send("戦績データがまだありません。")
        return

    embed = discord.Embed(title="📊 プレイヤー戦績一覧", color=discord.Color.blue())
    for uid, stats in history_data.items():
        user = await bot.fetch_user(int(uid))
        name = user.display_name
        total_games = stats.get("games", 0)
        total_wins = stats.get("wins", 0)
        winrate = f"{(total_wins / total_games * 100):.1f}%" if total_games > 0 else "0%"
        text = f"総合成績: {total_wins}勝 / {total_games}戦（勝率: {winrate}）\n"

        # レーン別成績
        lane_stats = stats.get("lane", {})
        for lane, ldata in lane_stats.items():
            lw, lg = ldata["wins"], ldata["games"]
            lwr = f"{(lw / lg * 100):.1f}%" if lg > 0 else "0%"
            text += f"- {lane}: {lw}勝 / {lg}戦（{lwr}）\n"

        embed.add_field(name=name, value=text, inline=False)

    await ctx.send(embed=embed)


@bot.command(name="help_lolgap2")
async def help_command(ctx):
    await ctx.send("""
📘 Botコマンド一覧

!ability @user 10 10 10 10 10 - 能力値登録
!delete_ability @user - 能力値削除

!join top mid / !join fill - レーン希望で参加（2つまで or fill）
!leave @user - 参加リストから削除
!participants_list - 参加者リスト
!reset - 参加者すべて削除
!make_teams 20 50 - チーム分け（VC不要・参加者10人）
!swap @user @user - レーン交換

!show - 能力一覧
!ranking - 各レーンの能力値ランキング
!win A / B - 勝利チーム報告 → 能力値変動

!show_custom - 各個人のカスタム勝率
!history - カスタム結果
""")

bot.run(os.environ['DISCORD_BOT_TOKEN'])
