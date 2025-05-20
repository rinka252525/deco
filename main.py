import discord
from discord.ext import commands
import json
import os
from itertools import permutations

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "abilities.json"
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
    await ctx.send("Botを一時停止します（実際には停止しません）。")

@bot.command()
async def ability(ctx, member: discord.Member, top: int, jg: int, mid: int, adc: int, sup: int):
    server_data = get_server_data(ctx.guild.id)
    server_data[str(member.id)] = {
        "top": top,
        "jg": jg,
        "mid": mid,
        "adc": adc,
        "sup": sup
    }
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
async def make_teams(ctx, *, exclude: commands.Greedy[discord.Member] = []):
    voice_state = ctx.author.voice
    if not voice_state or not voice_state.channel:
        await ctx.send("VCに人が足りませんよ！")
        return

    channel = voice_state.channel
    members = [m for m in channel.members if not m.bot and m not in exclude]

    if len(members) < 10:
        await ctx.send("VC内に十分なプレイヤーがいません。（除外後）")
        return

    selected = members[:10]
    server_data = get_server_data(ctx.guild.id)
    player_data = []
    for m in selected:
        if str(m.id) in server_data:
            player_data.append((m, server_data[str(m.id)]))
        else:
            await ctx.send(f"{m.mention} の能力値が未登録です！!ability で登録できますよ！")
            return

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

        last_teams[ctx.guild.id] = {
            'team1': team1,
            'team2': team2
        }

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
    if ctx.guild.id not in last_teams:
        await ctx.send("前回のチーム分けが見つかりません。先に !make_teams を行ってください。")
        return

    if team not in ["A", "B"]:
        await ctx.send("勝ったチームは A か B を指定してください。（例: !win A）")
        return

    teams = last_teams[ctx.guild.id]
    team1 = teams['team1']
    team2 = teams['team2']
    lanes = ['top', 'jg', 'mid', 'adc', 'sup']

    winner = team1 if team == "A" else team2
    loser = team2 if team == "A" else team1

    server_data = get_server_data(ctx.guild.id)

    for i in range(5):
        lane = lanes[i]
        win_id = str(winner[i][0].id)
        lose_id = str(loser[i][0].id)

        server_data[win_id][lane] += 2
        server_data[lose_id][lane] = max(0, server_data[lose_id][lane] - 2)

    update_server_data(ctx.guild.id, server_data)
    await ctx.send("勝敗結果を反映しました！")

@bot.command()
async def show_result(ctx):
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

!show_result
　→ 各レーンの現在の能力値を表示します（ランキング形式）。

!make_teams [@除外したいユーザー ...]
　→ VC内の10人を対象にチーム分けを行います。
　　レーンごとの能力差が20以内、チーム合計が50以内の組み合わせを探します。
　　11人以上いる場合、除外したいメンバーを指定してください。
　例: !make_teams @deco

!win A or B
　→ 勝利チームを指定し、そのレーンの能力値を +2 / -2 で更新します。
    """
    await ctx.send(help_text)

bot.run(os.environ['DISCORD_BOT_TOKEN'])
