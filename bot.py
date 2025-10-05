import discord
from discord.ext import commands
from discord import TextChannel, Embed
from discord import app_commands, ui, Interaction, ButtonStyle
import os
from datetime import datetime, timedelta
import asyncio
import re
from flask import Flask
from threading import Thread


app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()


# --- CONFIG ---
TEAM_ROLES = {
    1424259822508966039: "Aces",
    1424259891383631952: "Spartans",
    1424260027719356436: "Bears",
    1424260073307242506: "Mariners",
    1424260162709098598: "Vikings",
    1424260200772403241: "Tigers",
}

# Team emojis (name → emoji ID)
TEAM_EMOJIS = {
    "Aces": 1424262764100063322,
    "Spartans": 1424262886842437737,
    "Bears": 1424262842215038986,
    "Mariners": 1424262812938535036,
    "Vikings": 1424262774292222005,
    "Tigers": 1424262656252051507
}

# Team colors (name → hex)
TEAM_COLORS = {
    "Aces": 0x3498db,      # Blue
    "Spartans": 0xe74c3c,  # Red
    "Bears": 0x9b59b6,     # Purple
    "Mariners": 0x2ecc71,  # Green
    "Vikings": 0xf1c40f,   # Yellow
    "Tigers": 0xe67e22,    # Orange
}

BOD_CHANNEL_ID = 1424255177644576781
TRANSACTIONS_CHANNEL_ID = 1424256215302799431
SUSPENSIONS_CHANNEL_ID = 1424258741456601098
TRADE_ALERT_CHANNEL_ID = 1424264921729990657
SUSPENSION_ALERT_CHANNEL_ID = 1424264941111738419

VOTE_DURATION = 24
REQUIRED_CHECKS = 1

SUSPEND_ALLOWED_ROLES = {1424253958473384038, 1424260153485561986}
TRADE_ALLOWED_ROLES = {1424260472932274196, 1424260541265739880, 1424253958473384038, 1424260153485561986}
OFFER_ALLOWED_ROLES = {1424260472932274196, 1424260541265739880}
# 1424260472932274196 franchise owner, 1424260541265739880 general manager


GUILD_ID = 1424253499415199776  # <-- REPLACE with your server ID

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="?", intents=intents)



@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user} | Slash commands synced")


def has_any_role(member, allowed_roles):
    return any(role.id in allowed_roles for role in member.roles)


async def swap_team_roles(team1, team2, users1, users2):
    for member in users1:
        try:
            if team1 in member.roles:
                await member.remove_roles(team1, reason="Trade confirmed")
            await member.add_roles(team2, reason="Trade confirmed")
        except Exception as e:
            print(f"Couldn't update {member}: {e}")

    for member in users2:
        try:
            if team2 in member.roles:
                await member.remove_roles(team2, reason="Trade confirmed")
            await member.add_roles(team1, reason="Trade confirmed")
        except Exception as e:
            print(f"Couldn't update {member}: {e}")


async def parse_members(interaction, mention_string, max_users=3):
    pattern = r"<@!?(\d+)>"
    ids = re.findall(pattern, mention_string)
    if len(ids) > max_users:
        return None
    members = []
    for id in ids:
        member = await interaction.guild.fetch_member(int(id))
        if member:
            members.append(member)
    return members


async def track_votes(message, team1, team2, users1, users2, proposer):
    try:
        end_time = datetime.utcnow() + timedelta(hours=VOTE_DURATION)
        while datetime.utcnow() < end_time:
            await asyncio.sleep(10)
            msg = await message.channel.fetch_message(message.id)
            accept_reaction = discord.utils.get(msg.reactions, emoji="✅")
            accept_count = accept_reaction.count - 1 if accept_reaction else 0
            if accept_count >= REQUIRED_CHECKS:
                await swap_team_roles(team1, team2, users1, users2)

                tx_channel = bot.get_channel(TRANSACTIONS_CHANNEL_ID)
                if tx_channel:
                    embed = discord.Embed(
                        title="✅ Trade Accepted — OBL (Official Baseball League)",
                        color=discord.Color.green(),
                        timestamp=datetime.utcnow()
                    )

                    if message.guild.icon:
                        embed.set_thumbnail(url=message.guild.icon.url)

                    embed.add_field(
                        name=f"**{message.guild.name}** -- Transaction",
                        value=f"**Trade accepted!**\n\n<@&{team1.id}> receive: {', '.join(m.mention for m in users2) or 'No players'}\n<@&{team2.id}> receive: {', '.join(m.mention for m in users1) or 'No players'}",
                        inline=False
                    )

                    embed.add_field(
                        name=f"📋 {team1.name} roster:",
                        value=f"{len(team1.members)}/20",
                        inline=True
                    )
                    embed.add_field(
                        name=f"📋 {team2.name} roster:",
                        value=f"{len(team2.members)}/20",
                        inline=True
                    )

                    embed.add_field(
                        name="🧑‍🏫 Coach:",
                        value=f"{proposer.mention}",
                        inline=False
                    )

                    embed.set_footer(
                        text=f"{proposer} • {datetime.utcnow().strftime('%Y/%m/%d %H:%M')}",
                        icon_url=proposer.display_avatar.url if proposer.display_avatar else None
                    )

                    await tx_channel.send(embed=embed)

                await message.reply(embed=discord.Embed(title="✅ Trade Confirmed!", color=discord.Color.green()))
                return

        await message.reply(embed=discord.Embed(title="❌ Trade Denied / Expired", color=discord.Color.red()))
    except Exception as e:
        print(f"Error in track_votes: {e}")


@bot.tree.command(name="trade", description="Propose a trade between two teams.")
@app_commands.describe(
    team1="Select the first team",
    users1="Members from team 1 (max 3, separated by commas)",
    team2="Select the second team",
    users2="Members from team 2 (max 3, separated by commas)"
)
@app_commands.choices(
    team1=[app_commands.Choice(name=name, value=str(role_id)) for role_id, name in TEAM_ROLES.items()],
    team2=[app_commands.Choice(name=name, value=str(role_id)) for role_id, name in TEAM_ROLES.items()]
)
async def trade(interaction: discord.Interaction, team1: app_commands.Choice[str], users1: str, team2: app_commands.Choice[str], users2: str):
    if not has_any_role(interaction.user, TRADE_ALLOWED_ROLES):
        await interaction.response.send_message("❌ You don’t have permission to use this command.", ephemeral=True)
        return
    team1_role = interaction.guild.get_role(int(team1.value))
    team2_role = interaction.guild.get_role(int(team2.value))
    members1 = await parse_members(interaction, users1, max_users=3)
    members2 = await parse_members(interaction, users2, max_users=3)
    if not team1_role or not team2_role:
        await interaction.response.send_message("❌ Invalid team selection.", ephemeral=True)
        return
    if members1 is None or members2 is None:
        await interaction.response.send_message("❌ Too many members or invalid mentions.", ephemeral=True)
        return
    await interaction.response.send_message(f"✅ Vote sent to trade channel!", ephemeral=True)
    trade_channel = bot.get_channel(TRADE_ALERT_CHANNEL_ID)
    if trade_channel:
        embed = discord.Embed(
            title="⚾ Trade Proposal",
            description=f"**{team1_role.name}** ⇄ **{team2_role.name}**\nFrom {team1_role.name}: {', '.join(m.display_name for m in members1)}\nFrom {team2_role.name}: {', '.join(m.display_name for m in members2)}",
            color=discord.Color.blue()
        )
        message = await trade_channel.send(embed=embed)
        await message.add_reaction("✅")
        await message.add_reaction("❌")
        bot.loop.create_task(track_votes(message, team1_role, team2_role, members1, members2, interaction.user))


class OfferView(ui.View):
    def __init__(self, target_user: discord.Member, offering_member: discord.Member, team_role: discord.Role, guild: discord.Guild):
        super().__init__(timeout=None)
        self.target_user = target_user
        self.offering_member = offering_member
        self.team_role = team_role
        self.guild = guild

    @ui.button(label="Accept", style=ButtonStyle.green)
    async def accept(self, interaction: Interaction, button: ui.Button):
        if interaction.user != self.target_user:
            await interaction.response.send_message("❌ This offer isn’t for you.", ephemeral=True)
            return
        if not self.team_role:
            await interaction.response.send_message("❌ Team role not found.", ephemeral=True)
            return
        try:
            await self.target_user.add_roles(self.team_role, reason="Offer accepted")
            roster_count = len(self.team_role.members)
            tx_channel = bot.get_channel(TRANSACTIONS_CHANNEL_ID)
            if tx_channel:
                embed = discord.Embed(
                    title="✅ Offer Accepted — OBL (Official Baseball League)",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )

                if self.guild.icon:
                    embed.set_thumbnail(url=self.guild.icon.url)

                embed.add_field(
                    name=f"**{self.guild.name}** -- Transaction",
                    value=f"**Offer accepted!**\n\n{self.target_user.mention} has accepted the offer to <:{self.team_role.name}:{TEAM_EMOJIS.get(self.team_role.name)}> **{self.team_role.name}**",
                    inline=False
                )

                embed.add_field(
                    name=f"📋 Roster:",
                    value=f"{roster_count}/20",
                    inline=True
                )

                embed.add_field(
                    name="🧑‍🏫 Coach:",
                    value=f"{self.offering_member.mention}",
                    inline=True
                )

                embed.set_footer(
                    text=f"{self.offering_member} • {datetime.utcnow().strftime('%Y/%m/%d %H:%M')}",
                    icon_url=self.offering_member.display_avatar.url if self.offering_member.display_avatar else None
                )

                await tx_channel.send(embed=embed)

            await interaction.response.send_message(f"✅ You have joined **{self.team_role.name}**!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error adding role: {e}", ephemeral=True)

    @ui.button(label="Deny", style=ButtonStyle.red)
    async def deny(self, interaction: Interaction, button: ui.Button):
        if interaction.user != self.target_user:
            await interaction.response.send_message("❌ This offer isn’t for you.", ephemeral=True)
            return
        await interaction.response.send_message("❌ Offer denied.", ephemeral=True)


@bot.tree.command(name="offer", description="Offer a user to join your team.")
@app_commands.describe(user="User to offer a team invitation to")
async def offer(interaction: discord.Interaction, user: discord.Member):
    if not has_any_role(interaction.user, OFFER_ALLOWED_ROLES):
        await interaction.response.send_message("❌ You don’t have permission to send offers.", ephemeral=True)
        return

    # Check if the target user is already on a team
    for role_id in TEAM_ROLES:
        if user.get_role(role_id):
            team_name = TEAM_ROLES[role_id]
            await interaction.response.send_message(f"❌ ERROR: {user.display_name} is already on **{team_name}**.", ephemeral=True)
            return

    offering_roles = [role for role in interaction.user.roles if role.id in TEAM_ROLES]
    if not offering_roles:
        await interaction.response.send_message("❌ You don’t belong to a valid team.", ephemeral=True)
        return

    team_role = offering_roles[0]
    roster_count = len(team_role.members)
    team_name = team_role.name
    team_emoji_id = TEAM_EMOJIS.get(team_name)
    team_emoji = f"<:{team_name}:{team_emoji_id}>" if team_emoji_id else ""

    try:
        dm = await user.create_dm()
        view = OfferView(user, interaction.user, team_role, interaction.guild)
        await dm.send(f"{team_emoji} **{team_name}** has offered you to join their team!\nOffered by: {interaction.user.mention}\nRoster: {roster_count}/20", view=view)
        await interaction.response.send_message(f"✅ Offer sent to {user.display_name}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(f"❌ Could not DM {user.display_name}.", ephemeral=True)



# === NEW SUSPEND COMMAND ===
@bot.tree.command(name="suspend", description="Propose a suspension for a user.")
@app_commands.describe(
    user="User to suspend",
    reason="Reason for suspension",
    ban_length="Number of days banned",
    game_length="Number of games suspended",
    proof="Proof (optional)"
)
async def suspend(interaction: discord.Interaction, user: discord.Member, reason: str, ban_length: int, game_length: int, proof: str = "N/A"):
    if not has_any_role(interaction.user, SUSPEND_ALLOWED_ROLES):
        await interaction.response.send_message("❌ You don’t have permission to use this command.", ephemeral=True)
        return

    proposal_channel = bot.get_channel(SUSPENSION_ALERT_CHANNEL_ID)
    suspensions_channel = bot.get_channel(SUSPENSIONS_CHANNEL_ID)

    # Step 1: Proposal Embed
    proposal_embed = discord.Embed(
        title="🛑 Suspension Proposal 🛑",
        color=discord.Color.orange(),
        timestamp=datetime.utcnow()
    )
    proposal_embed.add_field(name="User", value=user.mention, inline=False)
    proposal_embed.add_field(name="Proposed by", value=interaction.user.mention, inline=False)
    proposal_embed.add_field(name="Reason", value=reason, inline=False)
    proposal_embed.add_field(name="Ban length", value=f"{ban_length} day(s)", inline=True)
    proposal_embed.add_field(name="Game length", value=f"{game_length} game(s)", inline=True)
    proposal_embed.add_field(name="Proof", value=proof if proof else "N/A", inline=False)
    proposal_embed.set_footer(
        text=datetime.utcnow().strftime("%m/%d/%Y • Today at %I:%M %p")
    )

    await interaction.response.send_message("✅ Suspension proposal sent.", ephemeral=True)

    # Send proposal
    message = await proposal_channel.send(embed=proposal_embed)
    await message.add_reaction("✅")

    # Step 2: Wait for votes
    def check(reaction, user_react):
        return str(reaction.emoji) == "✅" and not user_react.bot

    try:
        while True:
            reaction, voter = await bot.wait_for("reaction_add", timeout=60*60*VOTE_DURATION, check=check)
            if reaction.count - 1 >= REQUIRED_CHECKS:
                # Step 3: Send final suspension
                if suspensions_channel:
                    suspension_embed = discord.Embed(
                        title="🛑 Suspension 🛑",
                        description=f"{user.mention} has been suspended for **{reason}**",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    suspension_embed.add_field(name="Days banned", value=str(ban_length), inline=True)
                    suspension_embed.add_field(name="Games suspended", value=str(game_length), inline=True)
                    suspension_embed.set_footer(
                        text=datetime.utcnow().strftime("%m/%d/%Y • Today at %I:%M %p")
                    )

                    await suspensions_channel.send(embed=suspension_embed)
                await message.reply("✅ Suspension approved and recorded.")
                return
    except asyncio.TimeoutError:
        await message.reply("❌ Suspension proposal expired without enough votes.")


@bot.tree.command(name="release", description="Release a user from your team.")
@app_commands.describe(user="The user to release from your team")
async def release(interaction: discord.Interaction, user: discord.Member):
    # Roles allowed to release
    RELEASE_ALLOWED_ROLES = {1424260472932274196, 1424260541265739880}

    if not has_any_role(interaction.user, RELEASE_ALLOWED_ROLES):
        await interaction.response.send_message("❌ You don’t have permission to release users.", ephemeral=True)
        return

    # Get the team role of the invoker
    invoker_team_roles = [role for role in interaction.user.roles if role.id in TEAM_ROLES]
    if not invoker_team_roles:
        await interaction.response.send_message("❌ You don’t belong to a valid team.", ephemeral=True)
        return

    invoker_team_role = invoker_team_roles[0]

    # Get the team role of the target user
    target_team_roles = [role for role in user.roles if role.id in TEAM_ROLES]
    if not target_team_roles:
        await interaction.response.send_message(f"❌ {user.display_name} is not on any team.", ephemeral=True)
        return

    target_team_role = target_team_roles[0]

    # Check if both are on the same team
    if invoker_team_role != target_team_role:
        await interaction.response.send_message(f"❌ ERROR: {user.display_name} is not on your team!", ephemeral=True)
        return

    try:
        await user.remove_roles(target_team_role, reason=f"Released by {interaction.user}")
        await interaction.response.send_message(f"✅ {user.display_name} has been released from **{target_team_role.name}**.", ephemeral=True)

        tx_channel = bot.get_channel(TRANSACTIONS_CHANNEL_ID)
        if tx_channel:
            embed = discord.Embed(
                title="🛑 Player Released",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User Released", value=f"{user.mention}", inline=False)
            embed.add_field(name="Released By", value=f"{interaction.user.mention}", inline=False)
            embed.add_field(name="Team", value=f"{target_team_role.name}", inline=False)
            embed.set_footer(text=f"{datetime.utcnow().strftime('%m/%d/%Y %H:%M')}")

            await tx_channel.send(embed=embed)

    except Exception as e:
        await interaction.response.send_message(f"❌ Error releasing user: {e}", ephemeral=True)


class GameApprovalView(ui.View):
    def __init__(self, team1_role, team2_role, time):
        super().__init__(timeout=None)
        self.team1_role = team1_role
        self.team2_role = team2_role
        self.time = time
        self.approvals = set()
        self.proposal_msg = None

    @ui.button(label="Approve Game", style=ButtonStyle.green)
    async def approve_game(self, interaction: Interaction, button: ui.Button):
        franchise_owner_role_id = 1424260472932274196

        if not has_any_role(interaction.user, {franchise_owner_role_id}):
            await interaction.response.send_message("❌ You must be a Franchise Owner to approve.", ephemeral=True)
            return

        if not has_any_role(interaction.user, {self.team1_role.id, self.team2_role.id}):
            await interaction.response.send_message("❌ You must belong to one of the two teams to approve.", ephemeral=True)
            return

        self.approvals.add(interaction.user.id)
        await interaction.response.send_message(f"✅ {interaction.user.display_name} approved the game.", ephemeral=True)

        if len(self.approvals) < 2:
            return

        # Both approvals received — post game schedule
        game_channel = interaction.guild.get_channel(1424256585240281211)
        if not game_channel:
            return

        embed = discord.Embed(
            title=":stadium: Game Scheduled",
            description=f"**{self.team1_role.name}** vs **{self.team2_role.name}**\nTime: {self.time}",
            color=discord.Color.green()
        )
        embed.add_field(name="Teams", value=f"{self.team1_role.mention}    {self.team2_role.mention}", inline=False)
        embed.add_field(name="Umpire", value="Not claimed", inline=True)
        embed.add_field(name="Streamer", value="Not claimed", inline=True)
        embed.set_footer(text=datetime.utcnow().strftime("%m/%d/%Y %H:%M"))

        claim_view = GameClaimView(embed, game_channel)
        await game_channel.send(content=f"<@&1424261091965538405> <@&1424261576625754194>", embed=embed, view=claim_view)

        await self.proposal_msg.edit(embed=self.proposal_msg.embeds[0], view=None)


class GameClaimView(ui.View):
    def __init__(self, embed: discord.Embed, channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.embed = embed
        self.channel = channel

    @ui.button(label="Claim as Umpire", style=ButtonStyle.blurple)
    async def claim_umpire(self, interaction: Interaction, button: ui.Button):
        umpire_role_id = 1424261091965538405
        if not has_any_role(interaction.user, {umpire_role_id}):
            await interaction.response.send_message("❌ You don’t have permission to claim umpire.", ephemeral=True)
            return
        await self.update_embed(interaction, "Umpire", interaction.user.mention)

    @ui.button(label="Claim as Streamer", style=ButtonStyle.blurple)
    async def claim_streamer(self, interaction: Interaction, button: ui.Button):
        streamer_role_id = 1424261576625754194
        if not has_any_role(interaction.user, {streamer_role_id}):
            await interaction.response.send_message("❌ You don’t have permission to claim streamer.", ephemeral=True)
            return
        await self.update_embed(interaction, "Streamer", interaction.user.mention)

    async def update_embed(self, interaction: Interaction, role: str, mention: str):
        for i, field in enumerate(self.embed.fields):
            if field.name == role:
                self.embed.set_field_at(i, name=role, value=mention, inline=True)
        await interaction.message.edit(embed=self.embed)
        await interaction.response.send_message(f"✅ {mention} claimed {role}.", ephemeral=True)


@bot.tree.command(name="gametime", description="Schedule a game between two teams.")
@app_commands.describe(
    team1="First team",
    team2="Second team",
    time="Time of the game"
)
@app_commands.choices(
    team1=[app_commands.Choice(name=name, value=str(role_id)) for role_id, name in TEAM_ROLES.items()],
    team2=[app_commands.Choice(name=name, value=str(role_id)) for role_id, name in TEAM_ROLES.items()]
)
async def gametime(interaction: discord.Interaction, team1: app_commands.Choice[str], team2: app_commands.Choice[str], time: str):
    team1_role = interaction.guild.get_role(int(team1.value))
    team2_role = interaction.guild.get_role(int(team2.value))

    if not team1_role or not team2_role:
        await interaction.response.send_message("❌ Invalid team selection.", ephemeral=True)
        return

    proposal_channel = bot.get_channel(1424291240605782147)
    if not proposal_channel:
        await interaction.response.send_message("❌ Proposal channel not found.", ephemeral=True)
        return

    ping_roles = [f"<@&1424260472932274196>", f"<@&{team1_role.id}>", f"<@&{team2_role.id}>"]

    proposal_embed = discord.Embed(
        title="📅 Game Time Proposal",
        description=f"**{team1_role.name}** vs **{team2_role.name}**\nTime: {time}",
        color=discord.Color.blue()
    )
    proposal_embed.add_field(name="Team 1", value=team1_role.mention, inline=True)
    proposal_embed.add_field(name="Team 2", value=team2_role.mention, inline=True)
    proposal_embed.add_field(name="Status", value="Pending approval from both Franchise Owners", inline=False)

    view = GameApprovalView(team1_role, team2_role, time)
    msg = await proposal_channel.send(content=" ".join(ping_roles), embed=proposal_embed, view=view)
    view.proposal_msg = msg

    await interaction.response.send_message("✅ Game proposal sent!", ephemeral=True)



from discord import Embed, TextChannel, app_commands, Interaction, ui

class TypeModal(ui.Modal, title="Create a Custom Embed"):
    title_input = ui.TextInput(
        label="Embed Title",
        style=discord.TextStyle.short,
        placeholder="Enter your embed title",
        required=True
    )
    description_input = ui.TextInput(
        label="Embed Description",
        style=discord.TextStyle.paragraph,  # multi-line
        placeholder="Enter your embed description here...\nYou can add emojis, line breaks, markdown formatting!",
        required=True
    )

    def __init__(self, channel: TextChannel, author_id: int):
        super().__init__()
        self.channel = channel
        self.author_id = author_id

    async def on_submit(self, interaction: Interaction):
        allowed_users = {1064324709963022356, 1120832144630100102}

        if interaction.user.id not in allowed_users:
            await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
            return

        embed = Embed(
            title=self.title_input.value,
            description=self.description_input.value,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Sent by {interaction.user.display_name}")

        try:
            await self.channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Message sent to {self.channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to send message: {e}", ephemeral=True)


@bot.tree.command(name="type", description="Send a custom embedded message to a specific channel")
@app_commands.describe(channel="Select the channel to send the embed")
async def type_command(interaction: Interaction, channel: TextChannel):
    modal = TypeModal(channel, interaction.user.id)
    await interaction.response.send_modal(modal)



@bot.tree.command(name="roster", description="Show all members in a team's roster.")
@app_commands.describe(role="Select the team's role to view its roster")
async def roster(interaction: discord.Interaction, role: discord.Role):
    if role.id not in TEAM_ROLES:
        return await interaction.response.send_message(
            "❌ That role isn’t a valid team!", ephemeral=True
        )

    team_name = TEAM_ROLES[role.id]
    emoji_id = TEAM_EMOJIS.get(team_name)
    color = TEAM_COLORS.get(team_name, 0x2b2d31)

    emoji_str = f"<:team:{emoji_id}>" if emoji_id else "⚾"

    members = [member.mention for member in role.members]
    member_list = "\n".join(members) if members else "*No players currently on this roster.*"

    embed = discord.Embed(
        title=f"{emoji_str} {team_name} Roster",
        description=member_list,
        color=color
    )

    if role.guild.icon:
        embed.set_thumbnail(url=role.guild.icon.url)

    embed.set_footer(
        text=f"Total players: {len(role.members)}",
        icon_url=interaction.user.display_avatar.url
    )

    await interaction.response.send_message(embed=embed)




from discord import ui, app_commands
import discord

# === TEAM CONSTANTS ===
TEAM_ROLES = {
    1424259822508966039: "Aces",
    1424259891383631952: "Spartans",
    1424260027719356436: "Bears",
    1424260073307242506: "Mariners",
    1424260162709098598: "Vikings",
    1424260200772403241: "Tigers",
}

TEAM_EMOJIS = {
    "Aces": 1424262764100063322,
    "Spartans": 1424262886842437737,
    "Bears": 1424262842215038986,
    "Mariners": 1424262812938535036,
    "Vikings": 1424262774292222005,
    "Tigers": 1424262656252051507
}

TEAM_COLORS = {
    "Aces": 0x3498db,       # Blue
    "Spartans": 0xe74c3c,   # Red
    "Bears": 0x9b59b6,      # Purple
    "Mariners": 0x2ecc71,   # Green
    "Vikings": 0xf1c40f,    # Yellow
    "Tigers": 0xe67e22      # Orange
}

# === Dropdown Menu ===
class TeamSelect(ui.Select):
    def __init__(self):
        options = []
        for role_id, team_name in TEAM_ROLES.items():
            emoji_id = TEAM_EMOJIS.get(team_name)
            emoji = discord.PartialEmoji(name=team_name, id=emoji_id) if emoji_id else None

            options.append(discord.SelectOption(
                label=team_name,
                value=str(role_id),
                emoji=emoji
            ))

        super().__init__(placeholder="Select a team", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("❌ Could not find this team role!", ephemeral=True)
            return

        await interaction.response.send_modal(LineupModal(role))


class TeamSelectView(ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(TeamSelect())


# === Modal for lineup input ===
class LineupModal(ui.Modal):
    def __init__(self, team: discord.Role):
        super().__init__(title=f"{team.name} Lineup")
        self.team = team

        # Batting order as single input
        self.add_item(ui.TextInput(
            label="Batting Order",
            placeholder="Enter batters separated by commas (9 total)",
            required=True
        ))

        # Starting pitcher
        self.add_item(ui.TextInput(
            label="Starting Pitcher",
            placeholder="Enter SP",
            required=True
        ))

        # Bench
        self.add_item(ui.TextInput(
            label="Bench",
            placeholder="Enter bench players separated by commas (max 3)",
            required=False
        ))

    async def on_submit(self, interaction: discord.Interaction):
        team_name = TEAM_ROLES[self.team.id]
        emoji_id = TEAM_EMOJIS.get(team_name)
        emoji_str = f"<:team:{emoji_id}>" if emoji_id else "⚾"

        batting_order = [b.strip() for b in self.children[0].value.split(",")][:9]
        starting_pitcher = self.children[1].value
        bench = [b.strip() for b in self.children[2].value.split(",")][:3]

        lineup_text = ""
        for idx, player in enumerate(batting_order, start=1):
            lineup_text += f"{idx}: {player}\n"
        lineup_text += f"SP: {starting_pitcher}\n"
        lineup_text += f"Bench: {', '.join(bench)}"

        embed = discord.Embed(
            title=f"{emoji_str} {team_name} Lineup!",
            description=lineup_text,
            color=TEAM_COLORS.get(team_name, 0x2b2d31)
        )

        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        embed.set_footer(
            text=f"Lineup posted by {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )

        lineup_channel = interaction.guild.get_channel(1424522041293406268)
        if lineup_channel:
            await lineup_channel.send(embed=embed)
            await interaction.response.send_message(f"✅ {team_name} lineup posted!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Lineup channel not found.", ephemeral=True)


# === Slash Command ===
@bot.tree.command(name="lineup", description="Start a lineup selection")
async def lineup(interaction: discord.Interaction):
    allowed_roles = {1424260472932274196, 1424260541265739880}  # Franchise Owner, General Manager

    if not any(role.id in allowed_roles for role in interaction.user.roles):
        await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )
        return

    view = TeamSelectView()
    await interaction.response.send_message("Select your team:", view=view, ephemeral=True)



    

@app_commands.checks.has_role(1424261091965538405)  # Required role ID
@bot.tree.command(name="final_score", description="Post a final score for a game.")
@app_commands.describe(
    team1="Select the first team",
    score1="Enter the first team's score",
    team2="Select the second team",
    score2="Enter the second team's score"
)
async def final_score(
    interaction: discord.Interaction,
    team1: discord.Role,
    score1: int,
    team2: discord.Role,
    score2: int
):
    if team1.id not in TEAM_ROLES or team2.id not in TEAM_ROLES:
        return await interaction.response.send_message("❌ One or both roles are not valid teams!", ephemeral=True)

    team1_name = TEAM_ROLES[team1.id]
    team2_name = TEAM_ROLES[team2.id]

    emoji1_id = TEAM_EMOJIS.get(team1_name)
    emoji2_id = TEAM_EMOJIS.get(team2_name)
    emoji1 = f"<:team:{emoji1_id}>" if emoji1_id else "⚾"
    emoji2 = f"<:team:{emoji2_id}>" if emoji2_id else "⚾"

    if score1 > score2:
        color = TEAM_COLORS.get(team1_name, 0x2b2d31)
        trophy1, trophy2 = " 🏆", ""
    elif score2 > score1:
        color = TEAM_COLORS.get(team2_name, 0x2b2d31)
        trophy1, trophy2 = "", " 🏆"
    else:
        color = 0x95a5a6
        trophy1 = trophy2 = " 🤝"

    embed = discord.Embed(
        title="🏁 Final Game Score",
        description="📢 The game has finished!",
        color=color
    )

    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)

    embed.add_field(
        name="📝 Scoreboard",
        value=(
            f"**{emoji1} {team1_name}{trophy1}** - `{score1}`\n"
            f"**{emoji2} {team2_name}{trophy2}** - `{score2}`"
        ),
        inline=False
    )

    embed.set_footer(
        text=f"Game Reported by {interaction.user}",
        icon_url=interaction.user.display_avatar.url
    )

    channel = interaction.guild.get_channel(1424256136487632987)
    if not channel:
        return await interaction.response.send_message("⚠️ Final score channel not found.", ephemeral=True)

    await channel.send(embed=embed)
    await interaction.response.send_message(f"✅ Final score posted in {channel.mention}!", ephemeral=True)




keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
