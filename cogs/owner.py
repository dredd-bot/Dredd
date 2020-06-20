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
import json
import math
import time
import random
import humanize
import datetime
import aiohttp
import typing
import os
import platform
import psutil
import importlib
import asyncio

from discord import Webhook, AsyncWebhookAdapter
from discord.ext import commands
from typing import Union
from utils import default, btime
from utils.paginator import Pages
from contextlib import redirect_stdout
from prettytable import PrettyTable
from db import emotes

class owner(commands.Cog, name="Owner"):

    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:owners:691667205082841229>"
        self.big_icon = "https://cdn.discordapp.com/emojis/691667205082841229.png?v=1"
        self._last_result = None

    async def cog_check(self, ctx: commands.Context):
        """
        Local check, makes all commands in this cog owner-only
        """
        if not await ctx.bot.is_owner(ctx.author):
            await ctx.send(f"{emotes.bot_owner} | This command is owner-locked", delete_after=20)
            return False
        return True

    @commands.group(brief="Main commands")
    @commands.guild_only()
    async def dev(self, ctx):
        """ Developer commands.
        Used to manage bot stuff."""

        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

# ! Users
    
    @dev.command()
    async def userlist(self, ctx):
        """ Whole list of users that bot can see """

        try:
            await ctx.message.delete()
        except:
            pass
        async with ctx.channel.typing():
            await asyncio.sleep(2)
        user_list = []
        for user in self.bot.users:
            user_list.append(user)

        user_lists = []  # Let's list the users
        for num, user in enumerate(user_list, start=0):
            user_lists.append(f'`[{num + 1}]` **{user.name}** ({user.id})\n**Created at:** {btime.human_timedelta(user.created_at)}\n**────────────────────────**\n')

        paginator = Pages(ctx,
                          title=f"__Users:__ `[{len(user_lists)}]`",
                          entries=user_lists,
                          per_page = 10,
                          embed_color=self.bot.embed_color,
                          show_entry_count=False,
                          author=ctx.author)

        await paginator.paginate()

    @dev.command()
    async def nicks(self, ctx, user: discord.User, limit: int = None):
        """ View someone nicknames """
        nicks = []
        for num, nick in enumerate(await self.bot.db.fetch("SELECT * FROM nicknames WHERE user_id = $1 LIMIT $2", user.id, limit), start=0):
            nicks.append(f"`[{num + 1}]` {nick['nickname']}")
        
        if not nicks:
            return await ctx.send(f"{emotes.red_mark} **{user}** has had no nicknames yet.")

        paginator = Pages(ctx,
                          title=f"{user} [{user.id}]",
                          entries=nicks,
                          per_page = 10,
                          embed_color=self.bot.embed_color,
                          show_entry_count=False,
                          author=ctx.author)

        await paginator.paginate()

    @dev.command(brief='Clear user nicknames')
    async def clearnicks(self, ctx, user: discord.User, guild: int = None):
        """ Clear user nicknames """

        db_check = await self.bot.db.fetch("SELECT * FROM nicknames WHERE user_id = $1", user.id)

        if db_check is None:
            return await ctx.send(f"{user} has had no nicknames yet")
        
        if len(db_check) == 0:
            return await ctx.send(f"{user} has no nicknames in his history.")

        try:
            if guild is None:
                def check(r, u):
                    return u.id == ctx.author.id and r.message.id == checkmsg.id
                checkmsg = await ctx.send(f"Are you sure you want to clear all **{len(db_check)}** **{user}** nicknames?")
                await checkmsg.add_reaction(f'{emotes.white_mark}')
                await checkmsg.add_reaction(f'{emotes.red_mark}')
                react, users = await self.bot.wait_for('reaction_add', check=check, timeout=30)
                
                if str(react) == f"{emotes.white_mark}":
                    await checkmsg.delete()
                    await self.bot.db.execute("DELETE FROM nicknames WHERE user_id = $1", user.id)
                    return await ctx.send(f"{emotes.white_mark} {len(db_check)} nickname(s) were removed from {user}'s history", delete_after=15)
                
                if str(react) == f"{emotes.red_mark}":
                    await checkmsg.delete()
                    return await ctx.send(f"Not clearing any nicknames.", delete_after=15)
                
            if guild is not None:
                def check(r, u):
                    return u.id == ctx.author.id and r.message.id == checkmsg.id
                
                db_checks = await self.bot.db.fetch("SELECT * FROM nicknames WHERE user_id = $1 and guild_id = $2", user.id, guild)
                    
                g = self.bot.get_guild(guild)
                checkmsg = await ctx.send(f"Are you sure you want to clear all **{len(db_checks)}** {user} nicknames in **{g}** server?")
                await checkmsg.add_reaction(f'{emotes.white_mark}')
                await checkmsg.add_reaction(f'{emotes.red_mark}')
                react, users = await self.bot.wait_for('reaction_add', check=check, timeout=30)
                
                if str(react) == f"{emotes.white_mark}":
                    await checkmsg.delete()
                    await self.bot.db.execute("DELETE FROM nicknames WHERE user_id = $1 AND guild_id = $2", user.id, guild)
                    return await ctx.send(f"{emotes.white_mark} {len(db_checks)} nickname(s) were removed from {user}'s history in {g} guild.", delete_after=15)
                
                if str(react) == f"{emotes.red_mark}":
                    await checkmsg.delete()
                    return await ctx.send("Not removing any nicknames.", delete_after=15)
        
        except asyncio.TimeoutError:
            try:
                await checkmsg.clear_reactions()
                return await checkmsg.edit(content=f"Cancelling..")
            except:
                return
    
# ! SQL

    @dev.command(name="sql")
    async def sql(self, ctx, *, query):
        try:
            if not query.lower().startswith("select"):
                data = await self.bot.db.execute(query)
                return await ctx.send(data)

            data = await self.bot.db.fetch(query)
            if not data:
                return await ctx.send("Not sure what's wrong in here.")
            columns = []
            values = []
            for k in data[0].keys():
                columns.append(k)

            for y in data:
                rows = []
                for v in y.values():
                    rows.append(v)
                values.append(rows)

            x = PrettyTable(columns)
            for d in values:
                x.add_row(d)
            
            await ctx.send(f"```ml\n{x}```")
        except Exception as e:
            await ctx.send(e)


# ! Blacklist

    @dev.command(brief="Blacklist a guild", aliases=['guildban'])
    async def guildblock(self, ctx, guild: int, *, reason: str = None):
        """ Blacklist bot from specific guild """

        try:
            await ctx.message.delete()
        except:
            pass

        if reason is None:
            reason = "No reason"

        db_check = await self.bot.db.fetchval("SELECT guild_id FROM blockedguilds WHERE guild_id = $1", guild)

        if await self.bot.db.fetchval("SELECT _id FROM noblack WHERE _id = $1", guild):
            return await ctx.send("You cannot blacklist that guild")

        if db_check is not None:
            return await ctx.send("This guild is already in my blacklist.")

        await self.bot.db.execute("INSERT INTO blockedguilds(guild_id, reason, dev) VALUES ($1, $2, $3)", guild, reason, ctx.author.id)
        
        bu = await self.bot.db.fetch("SELECT * FROM blockedguilds")
        server = await self.bot.db.fetchval("SELECT * FROM support")

        g = self.bot.get_guild(guild)
        await ctx.send(f"I've successfully added **{g}** guild to my blacklist", delete_after=10)
        try:
            try:
                owner = g.owner
                emb = discord.Embed(color=self.bot.logging_color, title="Uh oh!",
                description=f"I'm sorry, looks like I was forced to leave your server: **{g}**\n**Reason:** `[BLACKLIST]: {reason}`\n\nJoin [support server]({server}) for more information")
                await owner.send(embed=emb)
            except Exception as e:
                print(e)
                await ctx.send("Wasn't able to message guild owner")
                pass
            await g.leave()
            await ctx.send(f"I've successfully left `{g}`")
        except Exception:
            pass
        try:
            m = self.bot.get_channel(697938958226686066)
            await m.edit(name=f"Watching {len(bu)} blacklisted guilds")
        except:
            return

    @dev.command(brief="Unblacklist a guild", aliases=['guildunban'])
    async def guildunblock(self, ctx, guild: int):
        """ Unblacklist bot from blacklisted guild """

        try:
            await ctx.message.delete()
        except:
            pass

        db_check = await self.bot.db.fetchval("SELECT guild_id FROM blockedguilds WHERE guild_id = $1", guild)

        if db_check is None:
            return await ctx.send("This guild isn't in my blacklist.")

        await self.bot.db.execute("DELETE FROM blockedguilds WHERE guild_id = $1", guild)

        bu = await self.bot.db.fetch("SELECT * FROM blockedguilds")

        g = self.bot.get_guild(guild)
        await ctx.send(f"I've successfully removed **{g}** guild from my blacklist", delete_after=10)
        try:
            m = self.bot.get_channel(697938958226686066)
            await m.edit(name=f"Watching {len(bu)} blacklisted guilds")
        except:
            return

    @dev.command(brief="Bot block user", aliases=['botban'])
    async def botblock(self, ctx, user: discord.User, *, reason: str = None):
        """ Blacklist someone from bot commands """
        try:
            await ctx.message.delete()
        except:
            pass

        if reason is None:
            reason = "No reason"

        db_check = await self.bot.db.fetchval("SELECT user_id FROM blacklist WHERE user_id = $1", user.id)

        if user.id == 345457928972533773 or user.id == 373863656607318018:
            return await ctx.send("You cannot blacklist that user")


        if db_check is not None:
            return await ctx.send("This user is already in my blacklist.")

        await self.bot.db.execute("INSERT INTO blacklist(user_id, reason, dev) VALUES ($1, $2, $3)", user.id, reason, ctx.author.id)

        bu = await self.bot.db.fetch("SELECT * FROM blacklist")
        m = self.bot.get_channel(697938394663223407)
        await m.edit(name=f"Watching {len(bu)} blacklisted users")

        await ctx.send(f"I've successfully added **{user}** to my blacklist", delete_after=10)

    @dev.command(brief="Bot unblock user", aliases=['botunban'])
    async def botunblock(self, ctx, user: discord.User):
        """ Unblacklist someone from bot commands """

        try:
            await ctx.message.delete()
        except:
            pass

        db_check = await self.bot.db.fetchval("SELECT user_id FROM blacklist WHERE user_id = $1", user.id)

        if db_check is None:
            return await ctx.send("This user isn't in my blacklist.")

        await self.bot.db.execute("DELETE FROM blacklist WHERE user_id = $1", user.id)

        bu = await self.bot.db.fetch("SELECT * FROM blacklist")
        m = self.bot.get_channel(697938394663223407)
        await m.edit(name=f"Watching {len(bu)} blacklisted users")

        await ctx.send(f"I've successfully removed **{user}** from my blacklist", delete_after=10)
    
    @dev.command(aliases=["bu"])
    async def blacklistedusers(self, ctx, page: int = 1):

        try:
            await ctx.message.delete()
        except:
            pass

        user_list = []
        for user_id, in await self.bot.db.fetch("SELECT user_id FROM blacklist"):
            user_list.append(user_id)  

        m = self.bot.get_channel(697938394663223407)
        await m.edit(name=f"Watching {len(user_list)} blacklisted users")


        guild_count = len(user_list)
        items_per_page = 10
        pages = math.ceil(guild_count / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        if pages == 0:
            return await ctx.send("I don't see anyone in my blacklist")

        user_lists = []  # Let's list the guilds
        for num, user in enumerate(user_list[start:end], start=start):
            user_lists.append(f'`[{num + 1}]`**{await self.bot.fetch_user(str(user))}** ({str(user)})\n**────────────────────────**\n')
 
        embed = discord.Embed(color=self.bot.embed_color,
                              title="Blacklisted users:", description="".join(user_lists))
        embed.set_footer(text=f"Viewing page {page}/{pages}")

        await ctx.send(embed=embed, delete_after=60)

# ! Bot managment

    @dev.command(brief="Change updates")
    async def update(self, ctx, *, updates: str):
        """ Change current updates """
        try:
            await ctx.message.delete()
        except:
            pass

        db_check = await self.bot.db.fetchval(f"SELECT * FROM updates")

        if db_check is None:
            await self.bot.db.execute("INSERT INTO updates(update) VALUES ($1)", updates)
            embed = discord.Embed(color=self.bot.embed_color,
                                  description=f"Set latest updates to {updates}")
            await ctx.send(embed=embed, delete_after=10)

        if db_check is not None:
            await self.bot.db.execute(f"UPDATE updates SET update = $1", updates)
            embed = discord.Embed(color=self.bot.embed_color,
                                  description=f"Set latest updates to {updates}")
            await ctx.send(embed=embed, delete_after=10)

    @dev.command(brief="Bot invite change")
    async def invite(self, ctx, *, invite: str):
        """ Change bot invite """
        try:
            await ctx.message.delete()
        except:
            pass

        db_check = await self.bot.db.fetchval(f"SELECT * FROM invite")

        if db_check is None:
            await self.bot.db.execute("INSERT INTO invite(link) VALUES ($1)", invite)
            embed = discord.Embed(color=self.bot.embed_color,
                                  description=f"Set bot invite to {invite}")
            await ctx.send(embed=embed, delete_after=10)

        if db_check is not None:
            await self.bot.db.execute(f"UPDATE invite SET link = $1", invite)
            embed = discord.Embed(color=self.bot.embed_color,
                                  description=f"Set bot invite to {invite}")
            await ctx.send(embed=embed, delete_after=10)

    @dev.command(brief="Support invite change")
    async def support(self, ctx, *, invite: str):
        """ Change bot support invite link """
        try:
            await ctx.message.delete()
        except:
            pass
        db_check = await self.bot.db.fetchval(f"SELECT * FROM support")

        if db_check is None:
            await self.bot.db.execute("INSERT INTO support(link) VALUES ($1)", invite)
            embed = discord.Embed(color=self.bot.embed_color,
                                  description=f"Set support invite to {invite}")
            await ctx.send(embed=embed, delete_after=10)

        if db_check is not None:
            await self.bot.db.execute(f"UPDATE support SET link = $1", invite)
            embed = discord.Embed(color=self.bot.embed_color,
                                  description=f"Set support invite to {invite}")
            await ctx.send(embed=embed, delete_after=10)

    
    @dev.command(brief='Change log of bot')
    async def changes(self, ctx):

        try:
            await ctx.message.delete()
        except:
            pass

        e = discord.Embed(color=self.bot.logging_color)
        e.set_author(icon_url=self.bot.user.avatar_url, name=f'Change log for V{self.bot.version}')
        e.description = self.bot.most_recent_change
        e.set_footer(text=f"© {self.bot.user}")

        await ctx.send(embed=e)

    @dev.command(brief='Add guild to whitelist')
    async def addwhite(self, ctx, guild: int):
        check = await self.bot.db.fetchval("SELECT * FROM noblack WHERE _id = $1", guild)

        if check:
            return await ctx.send(f"{emotes.red_mark} Already whitelisted")
        elif not check:
            await self.bot.db.execute("INSERT INTO noblack(_id) VALUES($1)", guild)
            await ctx.send(f"{emotes.white_mark} Done!")

# ! Status managment
    
    @commands.group(brief="Change status/pfp/nick", description="Change bot statuses and other.")
    @commands.is_owner()
    async def change(self, ctx):
        """Change bots statuses/avatar/nickname"""
        if ctx.invoked_subcommand is None:
            pass

    @change.command(name="playing", brief="Playing status", description="Change bot status to playing")
    @commands.is_owner()
    async def change_playing(self, ctx, *, playing: str):
        """ Change playing status. """
        await ctx.trigger_typing()
        try:
            await self.bot.change_presence(
                activity=discord.Game(type=0, name=playing),
                status=discord.Status.online
            )
            # jsonedit.change_value("files/config.json", "playing", playing)
            await ctx.send(f"Changed playing status to **{playing}**")
            await ctx.message.delete()
        except discord.InvalidArgument as err:
            await ctx.send(err)
        except Exception as e:
            await ctx.send(e)

    @change.command(name='listening', brief="Listening status", description="Change bot status to listening")
    @commands.is_owner()
    async def change_listening(self, ctx, *, listening: str):
        """ Change listening status. """
        await ctx.trigger_typing()
        try:
            await self.bot.change_presence(
                activity=discord.Activity(type=discord.ActivityType.listening,
                                          name=listening)
            )
            # jsonedit.change_value("files/config.json", "playing", playing)
            await ctx.send(f"Changed listening status to **{listening}**")
            await ctx.message.delete()
        except discord.InvalidArgument as err:
            await ctx.send(err)
        except Exception as e:
            await ctx.send(e)

    @change.command(name="watching", brief="Watching status", description="Change bot status to watching")
    @commands.is_owner()
    async def change_watching(self, ctx, *, watching: str):
        """ Change watching status. """
        await ctx.trigger_typing()
        try:
            await self.bot.change_presence(
                activity=discord.Activity(type=discord.ActivityType.watching,
                                          name=watching)
            )
            # jsonedit.change_value("files/config.json", "playing", playing)
            await ctx.send(f"Changed watching status to **{watching}**")
            await ctx.message.delete()
        except discord.InvalidArgument as err:
            await ctx.send(err)
        except Exception as e:
            await ctx.send(e)
            await ctx.message.delete()

    @change.command(name="nickname", aliases=['nick'], brief="Change nick", description="Change bot's nickname")
    @commands.is_owner()
    async def change_nickname(self, ctx, *, name: str = None):
        """ Change nickname. """
        await ctx.trigger_typing()
        try:
            await ctx.guild.me.edit(nick=name)
            await ctx.message.delete()
            if name:
                await ctx.send(f"Changed nickname to **{name}**")
            else:
                await ctx.send("Removed nickname")
                await ctx.message.delete()
        except Exception as err:
            await ctx.send(err)

    @change.command(name="avatar", brief="Change avatar", description="Change bot's avatar")
    @commands.is_owner()
    async def change_avatar(self, ctx, url: str = None):
        """ Change avatar. """
        if url is None and len(ctx.message.attachments) == 1:
            url = ctx.message.attachments[0].url
        else:
            url = url.strip('<>') if url else None

        try:
            async with aiohttp.ClientSession() as c:
                async with c.get(url) as f:
                    bio = await f.read()
            await self.bot.user.edit(avatar=bio)
            embed = discord.Embed(color=self.bot.embed_color,
                                  description=f"Changed the avatar!")
            embed.set_thumbnail(url=url)
            await ctx.send(embed=embed)
        except aiohttp.InvalidURL:
            await ctx.send("URL is invalid")
        except discord.InvalidArgument:
            await ctx.send("URL doesn't contain any image")
        except discord.HTTPException as err:
            await ctx.send(err)
        except TypeError:
            await ctx.send("You need to either provide an image URL or upload one with the command")

    @change.command(name='status', brief='Change bot status')
    async def change_status(self, ctx, status: str):
        try:
            await self.bot.change_presence(status=str, activity=None)
            await ctx.send("Done!")
        except Exception as e:
            return await ctx.send(f"""```diff
- {e}```""")

    @dev.command(aliases=['edit', 'editmsg'], category="Messages", brief="Edit msg")
    @commands.guild_only()
    @commands.is_owner()
    async def editmessage(self, ctx, id: int, *, newmsg: str):
        """Edits a message sent by the bot"""
        try:
            msg = await ctx.channel.fetch_message(id)
        except discord.errors.NotFound:
            return await ctx.send("Couldn't find a message with an ID of `{}` in this channel".format(id))
        if msg.author != self.bot.user:
            return await ctx.send("That message was not sent by me")
        await msg.edit(content=newmsg)
        await ctx.message.delete()

# ! Guild managment 

    @commands.group(brief="Guild settings")
    @commands.is_owner()
    async def guild(self, ctx):
        """Guild related commands!"""
        if ctx.invoked_subcommand is None:
            pass

    @guild.command(brief="Get invites", description="Get all invites of guild bot's in")
    @commands.is_owner()
    async def inv(self, ctx, guild: int):
        """Get all the invites of the server."""
        try:
            guildid = self.bot.get_guild(guild)
            guildinvs = await guildid.invites()
            pager = commands.Paginator()
            for Invite in guildinvs:
                pager.add_line(Invite.url)
            for page in pager.pages:
                await ctx.send(page)
        except discord.Forbidden:
            await ctx.send(f"{emotes.warning} Was unable to fetch invites.")

    @guild.command(brief="Create inv", description="Create inv to any guild bot is in")
    async def createinv(self, ctx, channel: int):
        """ Create invite for a server (get that server channel id's first)"""
        try:
            channelid = self.bot.get_channel(channel)
            InviteURL = await channelid.create_invite(max_uses=1)
            await ctx.send(InviteURL)
        except discord.Forbidden:
            await ctx.send(f"{emotes.warning} Was unable to create an invite.")

    @guild.command(aliases=['slist', 'serverlist'], name="list", brief="Guild list", description="View all guilds bot is in")
    @commands.is_owner()
    async def _list(self, ctx, page: int = 1):
        """List the guilds I am in."""
        try:
            await ctx.message.delete()
        except:
            pass
        guild_list = []
        for num, guild in enumerate(self.bot.guilds, start=0):
            people = len([x for x in guild.members if not x.bot])
            bots = len([x for x in guild.members if x.bot])
            botfarm = int(100 / len(guild.members) * bots)
            guild_list.append(f"`[{num + 1}]` {guild} ({guild.id}) `[Ratio: {botfarm}%]`\n**Joined:** {humanize.naturaltime(guild.get_member(self.bot.user.id).joined_at)}\n")

        paginator = Pages(ctx,
                          title=f"Guilds I'm In:",
                          thumbnail=None,
                          entries=guild_list,
                          per_page = 10,
                          embed_color=self.bot.embed_color,
                          show_entry_count=False,
                          author=ctx.author)

        await paginator.paginate()

    @guild.command(name="inspect", brief="Inspect a guild")
    async def _inspect(self, ctx, guild: int):

        try:
            guild = self.bot.get_guild(guild)
            people = len([x for x in guild.members if not x.bot])
            bots = len([x for x in guild.members if x.bot])
            botfarm = int(100 / len(guild.members) * bots)
            sperms = dict(guild.me.guild_permissions)
            perm = []
            for p in sperms.keys():
                if sperms[p] == True and guild.me.guild_permissions.administrator == False:
                    perm.append(f"`{p}`, ")

            if guild.me.guild_permissions.administrator == True:
                    perm = [f'{emotes.white_mark} Administrator  ']
            e = discord.Embed(color=self.bot.embed_color, title=f'**{guild}** Inspection')
            if botfarm > 50 and len(guild.members) > 15:
                e.description = f"{emotes.warning} This **MIGHT** be a bot farm, do you want me to leave this guild? `[Ratio: {botfarm}%]`"
            e.add_field(name='Important information:', value=f"""
**Total Members:** {len(guild.members):,} which {people:,} of them are humans and {bots:,} bots. `[Ratio: {botfarm}%]`
**Server Owner:** {guild.owner} ({guild.owner.id})""", inline=False)
            e.add_field(name='Other information:', value=f"""
**Total channels/roles:** {len(guild.channels)} {emotes.other_unlocked} / {len(guild.roles)} roles
**Server created at:** {default.date(guild.created_at)}
**Joined server at:** {humanize.naturaltime(guild.get_member(self.bot.user.id).joined_at)}""", inline=False)
            e.add_field(name="My permissions:", value="".join(perm)[:-2])
            await ctx.send(embed=e)
        except AttributeError:
            await ctx.send(f"{emotes.warning} Can't seem to find that guild, are you sure the ID is correct?")



    @guild.command(name='leave', category="Other", brief="Leave a guild", description="Make bot leave a suspicious guild")
    @commands.is_owner()
    async def leave(self, ctx, guild: int, reason: str = None):
        """ Make bot leave suspicious guild """
        try:
            await ctx.message.delete()
        except:
            pass
        if reason is None:
            reason = "No reason"
        if guild == 667065302260908032 or guild == 684891633203806260 or guild == 650060149100249091 or guild == 368762307473571840:
            return await ctx.send("You cannot leave that guild")
        server = await self.bot.db.fetchval("SELECT * FROM support")
        owner = self.bot.get_guild(guild).owner
        g = self.bot.get_guild(guild).name
        emb = discord.Embed(color=self.bot.logging_color, title="Uh oh!",
                            description=f"I'm sorry, looks like I was forced to leave your server: **{g}**\n**Reason:** `{reason}`\n\nJoin [support server]({server}) for more information")
        try:
            await owner.send(embed=emb)
        except Exception as e:
            pass
        await self.bot.get_guild(guild).leave()

    # ! Guild update count

    @guild.command(name='count', brief="Update guild count")
    async def guild_count(self, ctx):

        channel = self.bot.get_channel(681837728320454706)
        channel2 = self.bot.get_channel(697906520863801405)

        await channel.edit(name=f"Watching {len(self.bot.guilds)} guilds")
        await channel2.edit(name=f"Watching {len(self.bot.users)} users")
        await ctx.message.add_reaction(f'{emotes.white_mark}')
    
# ! Social 

    @dev.command(brief="DM a user", description="Direct message a user. DO NOT ABUSE IT!")
    @commands.is_owner()
    async def dm(self, ctx, user: discord.User, *, msg: str):
        """ DM an user """
        try:
            await ctx.message.delete()
        except:
            pass
        try:
            await user.send(msg)
            logchannel = self.bot.get_channel(674929832596865045)
            logembed = discord.Embed(
                title=f"I've DM'ed to {user}", description=msg, color=0x0DC405)
            await logchannel.send(embed=logembed)

        except discord.errors.Forbidden:
            await ctx.author.send("Couldn't send message to that user. Maybe he's not in the same server with me?")


    @dev.command(brief="Announce something", description="Announce something in announcement channel")
    async def announce(self, ctx, *, message: str):
        """ Announce something in support server announcement channel """

        async with aiohttp.ClientSession() as session:
            webhook = Webhook.from_url('https://discordapp.com/api/webhooks/717096788674215937/t6wNzdhCTtapVwJRA-XEMnORrxLpFySx6IlB16Zo3De4fVnnrg7YUQvSxv2Wk94_tLGn', adapter=AsyncWebhookAdapter(session))
            await webhook.send(message, username=ctx.author.name, avatar_url=ctx.author.avatar_url)
            
        await ctx.message.add_reaction(f'{emotes.white_mark}')

# ! Command managment

    @dev.command(brief="Disable enabled cmd")
    async def disablecmd(self, ctx, command):
        """Disable the given command. A few important main commands have been blocked from disabling for obvious reasons"""
        cant_disable = ["help", "jishaku", "dev", "disablecmd", "enablecmd", 'admin']
        cmd = self.bot.get_command(command)

        if cmd is None:
            embed = discord.Embed(color=self.bot.logembed_color, description=f"{emotes.red_mark} Command **{command}** doesn't exist.")
            return await ctx.send(embed=embed)

        data = await self.bot.db.fetchval("SELECT * FROM cmds WHERE command = $1", str(cmd.name))

        if cmd.name in cant_disable and not ctx.author.id == 345457928972533773:
            embed = discord.Embed(color=self.bot.logembed_color, description=f"{emotes.red_mark} Why are you trying to disable **{cmd.name}** you dum dum.")
            return await ctx.send(embed=embed)

        if data is None:
            await self.bot.db.execute("INSERT INTO cmds(command) VALUES ($1)", str(cmd.name))
            embed = discord.Embed(color=self.bot.logembed_color, description=f"{emotes.white_mark} Okay. **{cmd.name}** was disabled.")
            return await ctx.send(embed=embed)

        if data is not None:
            embed = discord.Embed(color=self.bot.logembed_color, description=f"{emotes.red_mark} **{cmd.name}** is already disabled")
            return await ctx.send(embed=embed)


    @dev.command(brief="Enable disabled cmd")
    async def enablecmd(self, ctx, *, command):
        """Enables a disabled command"""
        cmd = self.bot.get_command(command)

        if cmd is None:
            embed = discord.Embed(color=self.bot.logembed_color, description=f"{emotes.red_mark} Command **{command}** doesn't exist.")
            return await ctx.send(embed=embed)

        data = await self.bot.db.fetchval("SELECT * FROM cmds WHERE command = $1", str(cmd.name))

        if data is None:
            embed = discord.Embed(color=self.bot.logembed_color, description=f"{emotes.red_mark} **{cmd.name}** is already enabled")
            return await ctx.send(embed=embed)

        await self.bot.db.execute("DELETE FROM cmds WHERE command = $1", str(cmd.name))

        embed = discord.Embed(color=self.bot.logembed_color, description=f"{emotes.white_mark} Okay. **{cmd.name}** was enabled back on.")
        await ctx.send(embed=embed)
    
    @dev.command(brief="Disabled commands list")
    async def disabledcmds(self, ctx):
        try:
            cmd = []
            for command, in await self.bot.db.fetch("SELECT command FROM cmds"):
                cmd.append(command) 

            if len(cmd) == 0:
                return await ctx.send("No disabled commands.") 
                
            cmds = []  # Let's list the guilds
            for command in cmd:
                cmds.append(f'{command}')
                
                
            e = discord.Embed(color=self.bot.embed_color, title="Disabled commands", description="`" + '`, `'.join(cmds) + '`')
            await ctx.send(embed=e)
        
        except Exception as e:
            await ctx.send(e)

# ! Cog managment
    @dev.group(brief="Cog managment", description="Manage cogs.")
    @commands.guild_only()
    async def cog(self, ctx):
        """ Cog managment commands.
        cog r <cog> to reload already loaded cog.
        cog l <cog> to load unloaded cog.
        cog u <cog> to unload loaded cog."""
        if ctx.invoked_subcommand is None:
            pass

    @cog.command(aliases=["l"], brief="Load cog", description="Load any cog")
    async def load(self, ctx, name: str):
        """ Reloads an extension. """
        try:
            self.bot.load_extension(f"cogs.{name}")
        except Exception as e:
            return await ctx.send(f"```diff\n- {e}```")
        await ctx.send(f"📥 Loaded extension **cogs/{name}.py**")


    @cog.command(aliases=["r"], brief="Reload cog", description="Reload any cog")
    async def reload(self, ctx, name: str):
        """ Reloads an extension. """

        try:
            self.bot.reload_extension(f"cogs.{name}")
            await ctx.send(f"🔁 Reloaded extension **cogs/{name}.py**")

        except Exception as e:
            return await ctx.send(f"```diff\n- {e}```")

    @cog.command(aliases=['u'], brief="Unload cog", description="Unload any cog")
    async def unload(self, ctx, name: str):
        """ Reloads an extension. """
        try:
            self.bot.unload_extension(f"cogs.{name}")
        except Exception as e:
            return await ctx.send(f"```diff\n- {e}```")
        await ctx.send(f"📤 Unloaded extension **cogs/{name}.py**")
    
    @cog.command(aliases=['ra'], brief="Reload all cogs")
    async def reloadall(self, ctx):
        """ Reloads all extensions. """
        error_collection = []
        for file in os.listdir("cogs"):
            if file.endswith(".py"):
                name = file[:-3]
                try:
                    self.bot.reload_extension(f"cogs.{name}")
                except Exception as e:
                    error_collection.append(
                        [file, default.traceback_maker(e, advance=False)]
                    )

        if error_collection:
            output = "\n".join([f"**{g[0]}** ```diff\n- {g[1]}```" for g in error_collection])
            return await ctx.send(
                f"Attempted to reload all extensions, was able to reload, "
                f"however the following failed...\n\n{output}"
            )

        await ctx.send("Successfully reloaded all extensions")
    
# ! Utils
     
    @dev.command(aliases=['ru'])
    async def reloadutils(self, ctx, name: str):
        """ Reloads a utils module. """
        name_maker = f"utils/{name}.py"
        try:
            module_name = importlib.import_module(f"utils.{name}")
            importlib.reload(module_name)
        except ModuleNotFoundError:
            return await ctx.send(f"Couldn't find module named **{name_maker}**")
        except Exception as e:
            error = default.traceback_maker(e)
            return await ctx.send(f"Module **{name_maker}** returned error and was not reloaded...\n{error}")
        await ctx.send(f"🔁 Reloaded module **{name_maker}**")

# ! Admins
    
    @dev.command(hidden=True)
    async def adminadd(self, ctx, user: discord.User):
        owner=await self.bot.db.fetchval("SELECT user_id FROM admins WHERE user_id = $1", user.id)

        if owner is None:
            await self.bot.db.execute("INSERT INTO admins(user_id) VALUES ($1)", user.id)
            await ctx.send(f"Done! Added **{user}** to my admins list")

        if owner is not None:
            await ctx.send(f"**{user}** is already in my admins list")

    @dev.command(hidden=True)
    async def adminremove(self, ctx, user: discord.User):

        owner=await self.bot.db.fetchval("SELECT user_id FROM admins WHERE user_id = $1", user.id)

        if owner is not None:
            await self.bot.db.execute("DELETE FROM admins WHERE user_id = $1", user.id)
            await ctx.send(f"Done! Removed **{user}** from my admins list")

        if owner is None:
            await ctx.send(f"**{user}** is not in my admins list")

    @dev.command()
    async def adminlist(self, ctx):
        users = [] 
        for num, data in enumerate(await self.bot.db.fetch("SELECT user_id FROM admins"), start=1):
            users.append(f"`[{num}]` | **{await self.bot.fetch_user(data['user_id'])}** ({data['user_id']})\n")
        
    

        e = discord.Embed(color=self.bot.embed_color, title="Bot admins", description="".join(users))
        await ctx.send(embed=e)

    @dev.command()
    async def logout(self, ctx):

        await ctx.send("Logging out now..")
        await self.bot.session.close()
        await self.bot.logout()




def setup(bot):
    bot.add_cog(owner(bot))
