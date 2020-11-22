"""
Dredd, discord bot
Copyright (C) 2020 Moksej
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.
You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import discord
import time
import os
import codecs
import pathlib
import json
import typing

from io import BytesIO
from discord.ext import commands
from discord.utils import escape_markdown
from datetime import datetime

from utils import default, btime
from utils.checks import has_voted
from utils.paginator import Pages
from utils.Nullify import clean
from utils.publicflags import UserFlags

from collections import Counter
from db import emotes
from utils.default import color_picker
from utils.caches import CacheManager as cm



class info(commands.Cog, name="Info"):

    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:tag:686251889586864145>"
        self.big_icon = "https://cdn.discordapp.com/emojis/686251889586864145.png?v=1"
        self.bot.help_command.cog = self
        self.color = color_picker('colors')

    async def bot_check(self, ctx):

        # cmd = self.bot.get_command(ctx.command.name)
        # data = await self.bot.db.fetchval("select * from cmds where command = $1", str(cmd))
        if await self.bot.is_admin(ctx.author):
            return True

        if ctx.command.parent:
            if await self.bot.db.fetchval("select * from cmds where command = $1", str(ctx.command.parent)):
                await ctx.send(f"{emotes.warning} | `{ctx.command.parent}` and it's corresponing subcommands are temporarily disabled for maintenance")
                return False
            elif await self.bot.db.fetchval("select * from cmds where command = $1", str(f"{ctx.command.parent} {ctx.command.name}")):
                await ctx.send(f"{emotes.warning} | `{ctx.command.parent} {ctx.command.name}` is temporarily disabled for maintenance")
                return False
        else:
            if await self.bot.db.fetchval("select * from cmds where command = $1", str(ctx.command.name)):
                await ctx.send(f"{emotes.warning} | `{ctx.command.name}` is temporarily disabled for maintenance")
                return False
        return True

    @commands.command(brief="Bot's latency to discord")
    async def ping(self, ctx):
        """ See bot's latency to discord """
        discord_start = time.monotonic()
        async with self.bot.session.get("https://discord.com/") as resp:
            if resp.status == 200:
                discord_end = time.monotonic()
                discord_ms = f"{round((discord_end - discord_start) * 1000)}ms"
            else:
                discord_ms = "fucking dead"
        await ctx.send(f"\U0001f3d3 Pong   |   {discord_ms}")

    @commands.command(brief="Information about the bot", aliases=["botinfo"])
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def about(self, ctx):
        """ Displays basic information about the bot """

        version = self.bot.version

        channel_types = Counter(type(c) for c in self.bot.get_all_channels())
        voice = channel_types[discord.channel.VoiceChannel]
        text = channel_types[discord.channel.TextChannel]
        
        te = len([c for c in set(self.bot.walk_commands()) if c.cog_name == "Owner"])
        se = len([c for c in set(self.bot.walk_commands()) if c.cog_name == "Staff"])
        xd = len([c for c in set(self.bot.walk_commands())])
        ts = se + te
        totcmd = xd - ts

        mems = len(self.bot.users)

        file = discord.File("avatars/dreddthumbnail.png", filename="dreddthumbnail.png")
        Moksej = self.bot.get_user(345457928972533773)

        embed = discord.Embed(color=self.color['embed_color'])
        embed.description = f"""
__**General Information:**__
**Developer:** {escape_markdown(str(Moksej), as_needed=True)}\n**Library:**\n{emotes.other_python} [Discord.py {discord.__version__}](https://github.com/Rapptz/discord.py)\n**Last boot:** {btime.human_timedelta(self.bot.uptime)}\n**Bot version:** {version}

__**Other Information:**__
**Created:** {default.date(self.bot.user.created_at)} ({default.timeago(datetime.utcnow() - self.bot.user.created_at)})\n**Total:**\nCommands: **{totcmd:,}**\nMembers: **{mems:,}**\nServers: **{len(self.bot.guilds):,}**\nChannels: {emotes.other_unlocked} **{text:,}** | {emotes.other_vcunlock} **{voice:,}**\n
"""
        embed.set_image(
            url='attachment://dreddthumbnail.png')     

        await ctx.send(file=file, embed=embed)
    
    @commands.command(aliases=['lc'], brief="Lines count of the code")
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def linecount(self, ctx):
        """ Lines count of the code used creating Dredd """
        pylines = 0
        pyfiles = 0
        for path, subdirs, files in os.walk('.'):
            for name in files:
                    if name.endswith('.py'):
                        pyfiles += 1
                        with codecs.open('./' + str(pathlib.PurePath(path, name)), 'r', 'utf-8') as f:
                            for i, l in enumerate(f):
                                if l.strip().startswith('#') or len(l.strip()) == 0:  # skip commented lines.
                                    pass
                                else:
                                    pylines += 1


        e = discord.Embed(color=self.color['embed_color'],
                          description=f"{emotes.other_python} I am made of **{pyfiles:,}** files and **{pylines:,}** lines. You can also find my source at: [github](https://github.com/TheMoksej/Dredd)") 
        await ctx.send(embed=e)

    @commands.command(brief="List of all the server staff", aliases=['guildstaff'])
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def serverstaff(self, ctx):
        """ Check which server staff are online in the server """
        message = ""
        online, idle, dnd, offline = [], [], [], []

        for user in ctx.guild.members:
            if ctx.channel.permissions_for(user).kick_members or \
               ctx.channel.permissions_for(user).ban_members:
                if not user.bot and user.status is discord.Status.online:
                    online.append(f"**{user}**")
                if not user.bot and user.status is discord.Status.idle:
                    idle.append(f"**{user}**")
                if not user.bot and user.status is discord.Status.dnd:
                    dnd.append(f"**{user}**")
                if not user.bot and user.status is discord.Status.offline:
                    offline.append(f"**{user}**")

        if online:
            message += f"{emotes.online_status} {', '.join(online)}\n"
        if idle:
            message += f"{emotes.idle_status} {', '.join(idle)}\n"
        if dnd:
            message += f"{emotes.dnd_status} {', '.join(dnd)}\n"
        if offline:
            message += f"{emotes.offline_status} {', '.join(offline)}\n"

        e = discord.Embed(color=self.color['embed_color'], title=f"{ctx.guild.name} mods", description="This lists everyone who can ban and/or kick.")
        e.add_field(name="Server Staff List:", value=message)

        await ctx.send(embed=e)

    @commands.command(brief="List of all the server roles")
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def roles(self, ctx):
        """ List of all the roles in the server """
        allroles = []

        for num, role in enumerate(sorted(ctx.guild.roles, reverse=True), start=1):
            if role.is_default():
                continue
            allroles.append(f"`[{str(num).zfill(2)}]` {role.mention} | {role.id} | **[ Users : {len(role.members)} ]**\n")

        if len(allroles) == 0:
            return await ctx.send(f"{emotes.red_mark} Server has no roles")

        #data = BytesIO(allroles.encode('utf-8'))
        paginator = Pages(ctx,
                          title=f"{ctx.guild.name} roles list",
                          entries=allroles,
                          thumbnail=None,
                          per_page = 15,
                          embed_color=self.color['embed_color'],
                          show_entry_count=True,
                          author=ctx.author)
        await paginator.paginate()


    @commands.command(brief="Get server information", aliases=['server', 'si'])
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def serverinfo(self, ctx):
        """ Overview about the information of a server """

            
        if ctx.guild.mfa_level == 0:
            mfa = "Disabled"
        else:
            mfa = "Enabled"

        tot_mem = 0
        for member in ctx.guild.members:
            tot_mem += 1

        unique_members = set(ctx.guild.members)
        unique_online = sum(1 for m in unique_members if m.status is discord.Status.online and not type(m.activity) == discord.Streaming)
        unique_offline = sum(1 for m in unique_members if m.status is discord.Status.offline and not type(m.activity) == discord.Streaming)
        unique_idle = sum(1 for m in unique_members if m.status is discord.Status.idle and not type(m.activity) == discord.Streaming)
        unique_dnd = sum(1 for m in unique_members if m.status is discord.Status.dnd and not type(m.activity) == discord.Streaming )
        unique_streaming = sum(1 for m in unique_members if type(m.activity) == discord.Streaming)
        humann = sum(1 for member in ctx.guild.members if not member.bot)
        botts = sum(1 for member in ctx.guild.members if member.bot)

        nitromsg = f"This server has **{ctx.guild.premium_subscription_count}** boosts"
        nitromsg += "\n{0}".format(default.next_level(ctx))

        ranks = []
        with open('db/badges.json', 'r') as f:
            data = json.load(f)

        try:
            ranks.append(' '.join(data["Servers"][f"{ctx.guild.id}"]["Badges"]))
        except KeyError:
            pass

        embed = discord.Embed(color=self.color['embed_color'])
        embed.set_author(icon_url=ctx.guild.icon_url,
                         name=f"Server Information")
        if ranks:
            acknowledgements = '**Acknowledgements:** ' + ' '.join(ranks)
        else:
            acknowledgements = ''
        embed.add_field(name="__**General Information**__", value=f"**Guild name:** {ctx.guild.name}\n**Guild ID:** {ctx.guild.id}\n**Guild Owner:** {ctx.guild.owner}\n**Guild Owner ID:** {ctx.guild.owner.id}\n**Created at:** {default.date(ctx.guild.created_at)}\n**Region:** {str(ctx.guild.region).title()}\n**MFA:** {mfa}\n**Verification level:** {str(ctx.guild.verification_level).capitalize()}\n{acknowledgements}", inline=True)
        embed.add_field(name="__**Other**__", value=f"**Members:**\n{emotes.online_status} **{unique_online:,}**\n{emotes.idle_status} **{unique_idle:,}**\n{emotes.dnd_status} **{unique_dnd:,}**\n{emotes.streaming_status} **{unique_streaming:,}**\n{emotes.offline_status} **{unique_offline:,}**\n**Total:** {tot_mem:,} ({humann:,} Humans/{botts:,} Bots)\n**Channels:** {emotes.other_unlocked} {len(ctx.guild.text_channels)}/{emotes.other_vcunlock} {len(ctx.guild.voice_channels)}\n**Roles:** {len(ctx.guild.roles)}", inline=True)
        embed.add_field(name='__**Server boost status**__',
                        value=nitromsg, inline=False)
        info = []
        features = set(ctx.guild.features)
        all_features = {
            'PARTNERED': 'Partnered',
            'VERIFIED': 'Verified',
            'DISCOVERABLE': 'Server Discovery',
            'COMMUNITY': 'Community server',
            'INVITE_SPLASH': 'Invite Splash',
            'VIP_REGIONS': 'VIP Voice Servers',
            'VANITY_URL': 'Vanity Invite',
            'MORE_EMOJI': 'More Emoji',
            'COMMERCE': 'Commerce',
            'LURKABLE': 'Lurkable',
            'NEWS': 'News Channels',
            'ANIMATED_ICON': 'Animated Icon',
            'BANNER': 'Banner',
            'WELCOME_SCREEN_ENABLED': "Welcome screen"
        }

        for feature, label in all_features.items():
            if feature in features:
                info.append(label)

        if info:
            embed.add_field(name="__**Features**__", value=', '.join(info))
        if not ctx.guild.is_icon_animated():
            embed.set_thumbnail(url=ctx.guild.icon_url_as(format="png"))
        elif ctx.guild.is_icon_animated():
            embed.set_thumbnail(url=ctx.guild.icon_url_as(format="gif"))
        if ctx.guild.banner:
            embed.set_image(url=ctx.guild.banner_url_as(format="png"))

        embed.set_footer(
            text=f'© {self.bot.user}')

        await ctx.send(embed=embed)


    @commands.command(brief="Get user information", aliases=['user', 'ui'])
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def userinfo(self, ctx, *, user: typing.Union[discord.User, str] = None):
        """ Overview about the information of an user """

        if isinstance(user, discord.User):
            user = user
            color = self.color['embed_color']

        elif isinstance(user, str):
            if not user.isdigit():
                return await ctx.send(f"{emotes.red_mark} Couldn't find that user!")
            else:
                try:
                    user = await self.bot.fetch_user(user)
                    color = self.color['fetch_color']
                except:
                    return await ctx.send(f"{emotes.red_mark} Unknown user!")
                
        user = user or ctx.author
        
        badges = {
            'hs_brilliance': f'{emotes.discord_brilliance}',
            'discord_employee': f'{emotes.discord_staff}',
            'discord_partner': f'{emotes.discord_partner}',
            'hs_events': f'{emotes.discord_events}',
            'bug_hunter_lvl1': f'{emotes.discord_bug1}',
            'hs_bravery': f'{emotes.discord_bravery}',
            'hs_balance': f'{emotes.discord_balance}',
            'early_supporter': f'{emotes.discord_early}',
            'bug_hunter_lvl2': f'{emotes.discord_bug2}',
            'verified_dev': f'{emotes.discord_dev}'
        }
        
        badge_list = []
        flag_vals = UserFlags((await self.bot.http.get_user(user.id))['public_flags'])
        for i in badges.keys():
            if i in [*flag_vals]:
                badge_list.append(badges[i])
        
        ranks = []
        # with open('db/badges.json', 'r') as f:
        #     data = json.load(f)
        data = self.bot.user_badges

        if cm.get_cache(self.bot, f"{user.id}", 'user_badges'):
            ranks.append(" ".join(data[f"{user.id}"]['Badges']))


        if user.bot:
            bot = "Yes"
        elif not user.bot:
            bot = "No"
        
        if badge_list:
            discord_badges = ' '.join(badge_list)
        elif not badge_list:
            discord_badges = ''
        medias = ""
        for media in await self.bot.db.fetch("SELECT * FROM media WHERE user_id = $1", user.id):
            if media['media_type'] == "twitch":
                medias += f"{emotes.social_twitch} "
            elif media['media_type'] == "youtube":
                medias += f"{emotes.social_youtube} "
            elif media['media_type'] == "reddit":
                medias += f"{emotes.social_reddit} "
            elif media['media_type'] == "twitter":
                medias += f"{emotes.social_twitter} "
            elif media['media_type'] == "github":
                medias += f"{emotes.social_github} "
            elif media['media_type'] == "steam":
                medias += f"{emotes.social_steam} "
            elif media['media_type'] == "snapchat":
                medias += f"{emotes.social_snapchat} "
            medias += f"[{media['media_type'].title()}]({media['media_link']}) \n"
        
        if len(medias) > 1024:
            medias = medias[1020]
            medias += '...'

        if ranks:
            acknowledgements = '**Acknowledgements:** ' + ' '.join(ranks)
        else:
            acknowledgements = ''

        usercheck = ctx.guild.get_member(user.id)
        if usercheck:
                
            if usercheck.nick is None:
                nick = "N/A"
            else:
                nick = usercheck.nick

            status = {
            "online": f"{f'{emotes.online_mobile}' if usercheck.is_on_mobile() else f'{emotes.online_status}'}",
            "idle": f"{f'{emotes.idle_mobile}' if usercheck.is_on_mobile() else f'{emotes.idle_status}'}",
            "dnd": f"{f'{emotes.dnd_mobile}' if usercheck.is_on_mobile() else f'{emotes.dnd_status}'}",
            "offline": f"{emotes.offline_status}"
            }
            
            if usercheck.activities:
                ustatus = ""
                for activity in usercheck.activities:
                    if activity.type == discord.ActivityType.streaming:
                        ustatus += f"{emotes.streaming_status}"
            else:
                ustatus = f'{status[str(usercheck.status)]}'

            if not ustatus:
                ustatus = f'{status[str(usercheck.status)]}'
            nicks_opout = await self.bot.db.fetchval("SELECT user_id FROM nicks_op_out WHERE user_id = $1", usercheck.id)
            if nicks_opout is None:
                nicknames = []
                for nicks, in await self.bot.db.fetch(f"SELECT nickname FROM nicknames WHERE user_id = $1 AND guild_id = $2 ORDER BY time DESC", user.id, ctx.guild.id):
                    nicknames.append(nicks)
                    
                nicknamess = ""
                for nickss in nicknames[:5]:
                    nicknamess += f"{nickss}, "
                
                if nicknamess == "":
                    lnicks = "N/A"
                else:
                    lnicks = nicknamess[:-2]
            elif nicks_opout is not None:
                lnicks = 'User is opted out.'
            uroles = []
            for role in usercheck.roles:
                if role.is_default():
                    continue
                uroles.append(role.mention)  

            uroles.reverse()

            if len(uroles) > 10:
                uroles = [f"{', '.join(uroles[:10])} (+{len(usercheck.roles) - 11})"]

            profile = discord.Profile
            
            emb = discord.Embed(color=self.color['embed_color'])
            emb.set_author(icon_url=user.avatar_url, name=f"{user}'s information")
            emb.add_field(name="__**General Info:**__", value=f"**Full name:** {user} {discord_badges}\n**User ID:** {user.id}\n**Account created:** {user.created_at.__format__('%A %d %B %Y, %H:%M')}\n**Bot:** {bot}\n**Avatar URL:** [Click here]({user.avatar_url})\n{acknowledgements}", inline=False)
            emb.add_field(name="__**Activity Status:**__", value=f"**Status:** {ustatus}\n**Activity status:** {default.member_activity(usercheck)}", inline=False)
            emb.add_field(name="__**Server Info:**__", value=f"**Nickname:** {escape_markdown(nick, as_needed=True)}\n**Latest nicknames:** {escape_markdown(lnicks, as_needed=True)}\n**Joined at:** {default.date(usercheck.joined_at)}\n**Roles: ({len(usercheck.roles) - 1}) **" + ", ".join(uroles), inline=True)    
            if user.is_avatar_animated() == False:
                emb.set_thumbnail(url=user.avatar_url_as(format='png'))
            elif user.is_avatar_animated() == True:
                emb.set_thumbnail(url=user.avatar_url_as(format='gif'))
            else:
                emb.set_thumbnail(url=user.avatar_url)
            if medias:
                emb.add_field(name="Linked medias:", value=medias[:-2])
                
            await ctx.send(embed=emb)

        elif not usercheck:
            emb = discord.Embed(color=color)
            emb.set_author(icon_url=user.avatar_url, name=f"{user}'s information")
            emb.add_field(name="__**General Info:**__", value=f"**Full name:** {user} {discord_badges}\n**User ID:** {user.id}\n**Account created:** {user.created_at.__format__('%A %d %B %Y, %H:%M')}\n**Bot:** {bot}\n**Avatar URL:** [Click here]({user.avatar_url})\n{acknowledgements}", inline=False)
            if user.is_avatar_animated() == False:
                emb.set_thumbnail(url=user.avatar_url_as(format='png'))
            elif user.is_avatar_animated() == True:
                emb.set_thumbnail(url=user.avatar_url_as(format='gif'))
            else:
                emb.set_thumbnail(url=user.avatar_url)
            if medias:
                emb.add_field(name="Linked medias:", value=medias[:-2])
            await ctx.send(embed=emb)

    @commands.command(aliases=['source'], brief="Bot's source code")
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def sourcecode(self, ctx):
        """ View the bot's source code
        Keep in mind it is [licensed](https://github.com/TheMoksej/Dredd/blob/master/PrivacyPolicy.md)"""
        await ctx.send(f"{emotes.other_python} You can find my source code at: https://github.com/TheMoksej/Dredd")

    @commands.command(aliases=['pfp'], brief="Get users avatar")
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def avatar(self, ctx, user: discord.User = None):
        """ Displays what avatar user is using """

        user = user or ctx.author

        Zenpa = self.bot.get_user(373863656607318018)
        if user is self.bot.user:
            embed = discord.Embed(color=self.color['embed_color'],
                                  title=f'{self.bot.user}\'s Profile Picture!')
            embed.set_image(url=self.bot.user.avatar_url_as(static_format='png'))
            embed.set_footer(text=f'Huge thanks to {Zenpa} for this avatar')
            await ctx.send(embed=embed)

        else:
            embed = discord.Embed(color=self.color['embed_color'],
                                  title=f'{user}\'s Profile Picture!')
            embed.set_image(url=user.avatar_url_as(static_format='png'))
            # embed.set_footer(text=f'© {self.bot.user}')
            await ctx.send(embed=embed)
        
    @commands.group(brief="Get a list of old member nicknames", aliases=['nicks'], invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def nicknames(self, ctx, member: discord.Member = None):
        """ Check someones nicknames or opt out """
        member = member or ctx.author
        nicks_opout = await self.bot.db.fetchval("SELECT user_id FROM nicks_op_out WHERE user_id = $1", member.id)
        if nicks_opout is not None:
            return await ctx.send(f"{emotes.warning} I'm sorry, but I do not store any of the **{member}'s** nicknames due to them being opted out.")
        nick = []
        for nicks, in await self.bot.db.fetch(f"SELECT nickname FROM nicknames WHERE user_id = $1 AND guild_id = $2 ORDER BY time DESC", member.id, ctx.guild.id):
            nick.append(nicks)
        
        if len(nick) == 0:
            return await ctx.send(f"{member} has had no nicknames in this server.")

        if len(nick) > 10:
            nicks = '10'
        else:
            nicks = len(nick)
        
        nicknames = ""
        for num, nickss in enumerate(nick[:10], start=0):
            nicknames += f"`[{num + 1}]` **{escape_markdown(nickss, as_needed=True)}**\n"

        e = discord.Embed(color=self.color['embed_color'], description=f"**{member}** last {nicks} nickname(s) in the server:\n{nicknames}")

        await ctx.send(embed=e)

    @nicknames.command(name='opt', brief="Disable or enable nickname tracking", aliases=['optout', 'optin'])
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def nicknames_optout(self, ctx):
        """ Opt out if you want the bot to stop logging your nicknames. You can also opt in by invoking this command.
        By opting out I'll stop logging your nicknames in any server we share. """
        nicks_opout = await self.bot.db.fetchval("SELECT user_id FROM nicks_op_out WHERE user_id = $1 AND guild_id = $2", ctx.author.id, ctx.guild.id)
        if nicks_opout is not None:
            def check(r, u):
                return u.id == ctx.author.id and r.message.id == checkmsg.id
            try:
                checkmsg = await ctx.send(f"Are you sure you want to opt-in? Once you'll opt-in I'll be logging your nicknames again")
                await checkmsg.add_reaction(f'{emotes.white_mark}')
                await checkmsg.add_reaction(f'{emotes.red_mark}')
                react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30.0)

                if str(react) == f"{emotes.white_mark}": 
                    await self.bot.db.execute('DELETE FROM nicks_op_out WHERE user_id = $1 AND guild_id = $2', ctx.author.id, ctx.guild.id)
                    await ctx.channel.send(f"{emotes.white_mark} You're now opted-in! I'll be logging your nicknames once again.")
                    await checkmsg.delete()

            # ? They don't want to unban anyone

                if str(react) == f"{emotes.red_mark}":      
                    await checkmsg.delete()
                    await ctx.channel.send("Alright. Not opting you in")
            except Exception as e:
                print(e)
                return
            
        elif nicks_opout is None:
            def check(r, u):
                return u.id == ctx.author.id and r.message.id == checkmsg.id
            try:
                checkmsg = await ctx.send(f"Are you sure you want to opt-out? I won't be logging your nicknames if you will. All the nicknames from this server that I have stored in my database will also be deleted.")
                await checkmsg.add_reaction(f'{emotes.white_mark}')
                await checkmsg.add_reaction(f'{emotes.red_mark}')
                react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30.0)

                if str(react) == f"{emotes.white_mark}": 
                    await self.bot.db.execute('INSERT INTO nicks_op_out(guild_id, user_id) VALUES($1, $2)', ctx.guild.id, ctx.author.id)
                    await self.bot.db.execute("DELETE FROM nicknames WHERE user_id = $1 AND guild_id = $2", ctx.author.id, ctx.guild.id)
                    await ctx.channel.send(f"{emotes.white_mark} You're now opted-out! I won't be logging your nicknames anymore")
                    await checkmsg.delete()

            # ? They don't want to unban anyone

                if str(react) == f"{emotes.red_mark}":      
                    await checkmsg.delete()
                    await ctx.channel.send("Alright. Not opting you out")
            except Exception as e:
                print(e)
                return
            
    @commands.command(brief="Support server invite")
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def support(self, ctx):
        """ A link to this bot's support server """

        if ctx.guild and ctx.guild.id == 671078170874740756:
            return await ctx.send("You are in the support server, dummy.")

        else:
            embed = discord.Embed(color=self.color['embed_color'], description=f"{emotes.social_discord} Join my support server [here]({self.bot.support})")
            await ctx.send(embed=embed)

    @commands.command(description="Invite of the bot", brief="Invite the bot")
    async def invite(self, ctx):
        """ Invite bot to your server """

        embed = discord.Embed(color=self.color['embed_color'], description=f"{emotes.pfp_normal} You can invite me by clicking [here]({self.bot.invite})")
        await ctx.send(embed=embed)
    
    @commands.command(brief='Vote for the bot')
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def vote(self, ctx):
        """ Give me a vote, please. Thanks... """

        # if len(self.bot.guilds) >= 100 <= 110:
        #     return await ctx.send(f"{emotes.bot_vip} We reached 100 servers! The voting will be disabled until we get 110 servers!")

        e = discord.Embed(color=self.color['embed_color'], description=f"{emotes.pfp_normal} You can vote for me [here](https://discord.boats/bot/667117267405766696/vote)")
        await ctx.send(embed=e)
    
    @commands.command(brief="Credits to people helped", description="All the people who helped with creating this bot are credited")
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def credits(self, ctx):
        """ Credits for all the people that worked with this bot """
        # return await ctx.send("test")
        Zenpa = self.bot.get_user(373863656607318018)
        xhigh = self.bot.get_user(315539924155891722)
        Dutchy = self.bot.get_user(171539705043615744)
        # ! alt 200 for ╚

        semb = discord.Embed(color=self.color['embed_color'],
                             title="I'd like to say huge thanks to these people for their help with Dredd")
        semb.add_field(name="__**Graphic designers:**__\n", value=f"• **{Zenpa}**\n╠ {emotes.social_discord} [Discord Server](https://discord.gg/A6p9tep)\n╚ {emotes.social_instagram} [Instagram](https://www.instagram.com/donatas.an/)", inline=False)
        semb.set_footer(text=f"Also thanks to {xhigh} for the image")
        semb.add_field(name="__**Bug Hunter(s)**__", value='\n'.join(f"• **{x}**" for x in self.bot.get_guild(671078170874740756).get_role(679643117510459432).members), inline=True)
                       
        semb.add_field(name="__**Programming:**__\n",
                       value=f"• **{Dutchy}**\n╚ {emotes.social_discord} [Discord Server](https://discord.gg/ZFuwq2v)", inline=True)

        await ctx.send(embed=semb)
    
    @commands.command(brief="Get a list of all the server emotes", aliases=['se', 'emotes'])
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def serveremotes(self, ctx):
        """ Get a list of all the emotes in the server """

        _all = []
        for num, e in enumerate(ctx.guild.emojis, start=0):
            _all.append(f"`[{num + 1}]` {e} **{e.name}** | {e.id}\n")

        if len(_all) == 0:
            return await ctx.send(f"{emotes.red_mark} Server has no emotes!")
        
        paginator = Pages(ctx,
                          title=f"{ctx.guild.name} emotes list",
                          entries=_all,
                          thumbnail=None,
                          per_page = 15,
                          embed_color=ctx.bot.embed_color,
                          show_entry_count=True,
                          author=ctx.author)
        await paginator.paginate()
    
    @commands.command(brief='Disabled commands list', aliases=['disabledcmds', 'discmd'])
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def disabledcommands(self, ctx):
        """ List of globally disabled commands and guild disabled commands """
        cmmd = []
        for command, in await self.bot.db.fetch("SELECT command FROM cmds"):
            cmmd.append(command)

        comd = ''
        for commands in cmmd:
            comd += f"{commands}, "
        cmmds = []
        for command, in await self.bot.db.fetch("SELECT command FROM guilddisabled WHERE guild_id = $1", ctx.guild.id):
            cmmds.append(command)

        comds = ''
        for commands in cmmds:
            comds += f"{commands}, "

        if not comd and not comds:
            return await ctx.send(f"{emotes.warning} There are no commands disabled!")
            
        e = discord.Embed(color=self.color['embed_color'], description=f"List of all disabled commands")
        if comd:
            e.add_field(name='**Globally disabled commands:**', value=f"{comd[:-2]}", inline=False)
        if comds:
            e.add_field(name=f"**Disabled commands in this server:**", value=f'{comds[:-2]}')
        await ctx.send(embed=e)
    
    @commands.command(brief='User permissions in the server', aliases=['perms'])
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def permissions(self, ctx, member: discord.Member = None):
        """ See what permissions member has in the server. """

        member = member or ctx.author
        
        sperms = dict(member.guild_permissions)

        perm = []
        for p in sperms.keys():
            if sperms[p] == True and member.guild_permissions.administrator == False:
                perm.append(f"{emotes.white_mark} {p}\n")
            if sperms[p] == False and member.guild_permissions.administrator == False:
                perm.append(f"{emotes.red_mark} {p}\n")

        if member.guild_permissions.administrator == True:
            perm = [f'{emotes.white_mark} Administrator']

        
        paginator = Pages(ctx,
                          title=f"{member.name} guild permissions",
                          entries=perm,
                          thumbnail=None,
                          per_page = 20,
                          embed_color=self.color['embed_color'],
                          show_entry_count=False,
                          author=ctx.author)
        await paginator.paginate()

    @commands.command(brief="View Dredd's privacy policy", aliases=['privacy', 'policy'])
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def privacypolicy(self, ctx):
        """ View Dredd's privacy policy """
        
        await ctx.send(f"{emotes.discord_privacy} You can view my privacy policy at: {self.bot.privacy}")

def setup(bot):
    bot.add_cog(info(bot))
