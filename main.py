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
last_teams = {"team_a": {}, "team_b": {}}

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
async def show_ability(ctx):
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
    lanes_str = f"{lane1.upper()} / {lane2.upper()}" if lane1 != lane2 else lane1.upper()
    await ctx.send(f"{member.display_name} が [{lanes_str}] で参加登録しました。")








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
    global last_teams

    # 参加者数チェック
    if guild_id not in participants or len(participants[guild_id]) < 10:
        await ctx.send("参加者が10人未満です。")
        return

    member_ids = list(participants[guild_id].keys())
    server_data = get_server_data(guild_id)

    # 能力値未登録者チェック
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
            role_map = {}
            valid_team1 = True

            # チーム1のロール割り当て
            for uid, lane in zip(team1_ids, team1_roles):
                prefs = participants[guild_id].get(uid, [])
                if prefs and lane not in prefs and 'fill' not in prefs:
                    valid_team1 = False
                    break
                role_map[uid] = lane

            if not valid_team1:
                continue

            # チーム2のロール割り当てとスコア評価
            try:
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

    # 最終チーム保存
    last_teams = load_json(team_file)
    if not last_teams:
        last_teams = {}
    last_teams[str(ctx.guild.id)] = {
        "team_a": {str(uid): role_map[uid] for uid in team1_ids},
        "team_b": {str(uid): role_map[uid] for uid in team2_ids},
        "guild_id": str(ctx.guild.id)
    }
    save_json(team_file, last_teams)

    # 表示用名前も保存
    team1_sorted = sorted([(ctx.guild.get_member(uid), role_map[uid]) for uid in team1_ids], key=lambda x: lanes.index(x[1]))
    team2_sorted = sorted([(ctx.guild.get_member(uid), role_map[uid]) for uid in team2_ids], key=lambda x: lanes.index(x[1]))

    teams = {
        'A': [m.display_name for m, _ in team1_sorted if m],
        'B': [m.display_name for m, _ in team2_sorted if m]
    }
    save_json("teams_display.json", teams)

    team1_total = sum(server_data[str(uid)][role_map[uid]] for uid in team1_ids)
    team2_total = sum(server_data[str(uid)][role_map[uid]] for uid in team2_ids)

    # メッセージ表示
    msg = "**チームが決まりました！**\n"
    msg += f"**Team A**（合計: {team1_total}）\n"
    for member, lane in team1_sorted:
        val = server_data[str(member.id)][lane]
        msg += f"{member.display_name}（{lane.upper()} - {val}）\n"

    msg += f"\n**Team B**（合計: {team2_total}) \n"
    for member, lane in team2_sorted:
        val = server_data[str(member.id)][lane]
        msg += f"{member.display_name}（{lane.upper()} - {val}）\n"

    if best_score >= 1000:
        msg += "\n⚠️ 条件を完全には満たすチームは見つかりませんでしたが、最善の組み合わせを選びました。\n"
        msg += "\n".join(f"⚠️ {w}" for w in warnings)

    await ctx.send(msg)



@bot.command()
async def show_teams(ctx):
    guild_id = str(ctx.guild.id)  # 先に定義する
    last_teams = load_json(team_file)

    if not last_teams or guild_id not in last_teams or "team_a" not in last_teams[guild_id]:
        await ctx.send("保存されたチームが見つかりません。")
        return

    server_data = get_server_data(guild_id)
    lane_order = ['top', 'jg', 'mid', 'adc', 'sup']

    def format_team(team, name):
        msg = f"**{name}**\n"
        sorted_items = sorted(team.items(), key=lambda item: lane_order.index(item[1]) if item[1] in lane_order else 999)
        total = 0
        for uid, lane in sorted_items:
            member = ctx.guild.get_member(int(uid))
            if not member:
                continue
            val = server_data.get(uid, {}).get(lane, 0)
            total += val
            msg += f"{member.display_name}（{lane.upper()} - {val}）\n"
        msg += f"**合計: {total}**\n"
        return msg

    msg = format_team(last_teams[guild_id]["team_a"], "Team A")
    msg += "\n" + format_team(last_teams[guild_id]["team_b"], "Team B")

    await ctx.send(msg)


        
@bot.command()
async def swap(ctx, member1: discord.Member, member2: discord.Member):
    guild_id = str(ctx.guild.id)
    last_teams = load_json(team_file)

    if not last_teams or guild_id not in last_teams:
        await ctx.send("直近のチームデータが存在しません。")
        return

    teams = last_teams[guild_id]
    team_a = teams.get("team_a", {})
    team_b = teams.get("team_b", {})

    uid1, uid2 = str(member1.id), str(member2.id)

    def find_team_and_lane(uid):
        if uid in team_a:
            return "A", team_a[uid]
        elif uid in team_b:
            return "B", team_b[uid]
        return None, None

    team1, lane1 = find_team_and_lane(uid1)
    team2, lane2 = find_team_and_lane(uid2)

    if team1 is None or team2 is None:
        await ctx.send("どちらかのユーザーが現在のチームに含まれていません。")
        return

    if team1 == team2:
        # 同じチーム内 → レーンだけ交換
        if team1 == "A":
            team_a[uid1], team_a[uid2] = lane2, lane1
        else:
            team_b[uid1], team_b[uid2] = lane2, lane1
        await ctx.send("同じチーム内のレーンを交換しました。")
    else:
        # 異なるチーム → メンバーだけを入れ替え、レーンは元のまま維持
        if team1 == "A":
            team_a.pop(uid1)
            team_b.pop(uid2)
            team_a[uid2] = lane1  # user2 が user1 のレーンを担当
            team_b[uid1] = lane2  # user1 が user2 のレーンを担当
        else:
            team_b.pop(uid1)
            team_a.pop(uid2)
            team_b[uid2] = lane1
            team_a[uid1] = lane2
        await ctx.send("異なるチーム間のメンバーをレーンを維持したまま交換しました。")

    save_data(team_file, last_teams)
    await ctx.invoke(bot.get_command("show_teams"))






@bot.command()
async def win(ctx, winner: str):
    ability_file = 'abilities.json'
    team_file = 'last_teams.json'
    history_file = 'history.json'

    winner = winner.upper()
    if winner not in ["A", "B"]:
        await ctx.send("勝者は A または B で指定してください。")
        return

    guild_id = str(ctx.guild.id)
    last_teams_data = load_data(team_file)

    if guild_id not in last_teams_data or "team_a" not in last_teams_data[guild_id] or "team_b" not in last_teams_data[guild_id]:
        await ctx.send("直近のチームデータが見つかりません。")
        return

    # abilities.json を読み込む
    ability_data = load_data(ability_file)
    if guild_id not in ability_data:
        await ctx.send("能力値データが見つかりません。")
        return
    guild_abilities = ability_data[guild_id]

    # 履歴データ
    history_data = load_data(history_file)

    # 勝者・敗者を取得
    winner_key = "team_a" if winner == 'A' else "team_b"
    loser_key = "team_b" if winner == 'A' else "team_a"

    team_win = last_teams_data[guild_id][winner_key]
    team_lose = last_teams_data[guild_id][loser_key]

    def update_ability(uid, lane, is_winner, match_count):
        delta = 10 if match_count < 5 else 2
        current_ability = guild_abilities[uid].get(lane, 60)
        if is_winner:
            guild_abilities[uid][lane] = min(120, current_ability + delta)
        else:
            guild_abilities[uid][lane] = max(0, current_ability - delta)

    def update_history(uid, lane, is_winner):
        if uid not in history_data:
            history_data[uid] = {"total_win": 0, "total_lose": 0, "lanes": {}}
        if lane not in history_data[uid]["lanes"]:
            history_data[uid]["lanes"][lane] = {"win": 0, "lose": 0}
        if is_winner:
            history_data[uid]["total_win"] += 1
            history_data[uid]["lanes"][lane]["win"] += 1
        else:
            history_data[uid]["total_lose"] += 1
            history_data[uid]["lanes"][lane]["lose"] += 1

    # 勝者と敗者チームの処理
    for team, is_winner in [(team_win, True), (team_lose, False)]:
        for uid, lane in team.items():
            if uid not in guild_abilities or lane not in guild_abilities[uid]:
                continue
            match_count = history_data.get(uid, {}).get("total_win", 0) + history_data.get(uid, {}).get("total_lose", 0)
            update_ability(uid, lane, is_winner, match_count)
            update_history(uid, lane, is_winner)

    # 保存
    save_data(ability_file, ability_data)
    save_data(history_file, history_data)

    await ctx.send(f"チーム{winner} の勝利を記録しました。能力値と戦績を更新しました。")










@bot.command()
async def show_custom(ctx, member: discord.Member = None):
    history_data = load_data("history.json")
    member = member or ctx.author
    uid = str(member.id)

    if uid not in history_data:
        await ctx.send(f"{member.display_name} のカスタム戦績は記録されていません。")
        return

    user_history = history_data[uid]
    total_win = user_history.get("total_win", 0)
    total_lose = user_history.get("total_lose", 0)
    total_games = total_win + total_lose

    msg = f"**📘 {member.display_name} のカスタム戦績**\n"
    msg += f"🔹 合計: {total_games}戦 {total_win}勝 {total_lose}敗　勝率 {round((total_win / total_games) * 100, 1) if total_games else 0}%\n"

    lanes = ["top", "jg", "mid", "adc", "sup"]
    for lane in lanes:
        lane_data = user_history.get("lanes", {}).get(lane, {"win": 0, "lose": 0})
        win = lane_data["win"]
        lose = lane_data["lose"]
        total = win + lose
        rate = f"{round((win / total) * 100, 1)}%" if total else "0%"
        msg += f"　- {lane}: {total}戦 {win}勝 {lose}敗　勝率 {rate}\n"

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



@bot.command(name="help_bb")
async def help_command(ctx):
    await ctx.send("""
🐉 BaronBrainコマンド一覧 🐉

!ability @user 10 10 10 10 10 - 能力値登録
!delete_ability @user - 能力値削除
!show_ability - 能力値確認

!join top mid / fill fill - レーン希望で参加（2つ or fill）
!leave @user - 参加リストから削除
!participants_list - 参加者リスト
!reset - 参加者すべて削除

!make_teams 20 50 - チーム分け（VC不要・参加者10人）
!swap @user @user - レーン交換
!win A / B - 勝利チーム報告 → 能力値変動

!ranking - 各レーンの能力値ランキング
!show_custom @user - 各個人のカスタム勝率

""")

bot.run(os.environ['DISCORD_BOT_TOKEN'])
