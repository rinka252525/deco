import json
from discord.ext import commands

bot = commands.Bot(command_prefix='!')

# データファイルのパス
ABILITY_FILE = 'ability.json'
STATS_FILE = 'stats.json'
CURRENT_TEAMS_FILE = 'current_teams.json'


def load_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        return {}


def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def update_player_stats(player, won, ability_data, stats_data):
    # 初期化
    if player not in stats_data:
        stats_data[player] = {"wins": 0, "games": 0}

    # 戦績更新
    stats_data[player]["games"] += 1
    if won:
        stats_data[player]["wins"] += 1

    # 能力変動値の決定
    games_played = stats_data[player]["games"]
    delta = 10 if games_played <= 5 else 2
    delta = delta if won else -delta

    # 能力更新
    if player in ability_data:
        for lane in ability_data[player]:
            ability_data[player][lane] = max(0, min(120, ability_data[player][lane] + delta))


@bot.command()
async def winA(ctx):
    await handle_win(ctx, winner_team_name='A', loser_team_name='B')


@bot.command()
async def winB(ctx):
    await handle_win(ctx, winner_team_name='B', loser_team_name='A')


async def handle_win(ctx, winner_team_name, loser_team_name):
    # データ読み込み
    teams_data = load_json(CURRENT_TEAMS_FILE)
    ability_data = load_json(ABILITY_FILE)
    stats_data = load_json(STATS_FILE)

    if not teams_data:
        await ctx.send("チーム情報が見つかりません。まず `!make_teams` を実行してください。")
        return

    try:
        winner_team = teams_data[winner_team_name]
        loser_team = teams_data[loser_team_name]
    except KeyError:
        await ctx.send("チーム情報が不正です。")
        return

    # 勝者と敗者の能力更新
    for lane, player in winner_team.items():
        update_player_stats(player, True, ability_data, stats_data)

    for lane, player in loser_team.items():
        update_player_stats(player, False, ability_data, stats_data)

    # 保存
    save_json(ABILITY_FILE, ability_data)
    save_json(STATS_FILE, stats_data)

    await ctx.send(f"✅ チーム{winner_team_name}が勝利として記録されました。\n各能力値・戦績を更新しました！")
