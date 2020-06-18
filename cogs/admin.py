"""
Dredd.
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
import asyncio


from discord.ext import commands
from typing import Union
from utils import default
from discord import Webhook, AsyncWebhookAdapter
from contextlib import redirect_stdout
from db import emotes

class admin(commands.Cog, name="Staff"):

    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:staff:691667204550295592>"
        self.big_icon = "https://cdn.discordapp.com/emojis/691667204550295592.png?v=1"
        self._last_result = None

    def is_it_me(ctx):
        return ctx.author.id == 345457928972533773


    async def cog_check(self, ctx: commands.Context):
        """
        Local check, makes all commands in this cog owner-only
        """
        if not await ctx.bot.is_admin(ctx.author):
            embed = discord.Embed(color=self.bot.logging_color, description="<:owners:691667205082841229> This command is admin-locked")
            await ctx.send(embed=embed)
            return False
        return True

    @commands.group(brief="Main commands")
    @commands.guild_only()
    async def admin(self, ctx):
        """ Bot admin commands.
        Used to help managing bot stuff."""

        if ctx.invoked_subcommand is None:
            await ctx.send("How can I help you my admin?")

# ! Blacklist

    @admin.command(brief="Blacklist a guild")
    async def guildblock(self, ctx, guild: int, *, reason: str = None):
        """ Blacklist bot from specific guild """

        if reason is None:
            reason = "No reason"

        db_check = await self.bot.db.fetchval("SELECT guild_id FROM blockedguilds WHERE guild_id = $1", guild)

        if guild == 667065302260908032 or guild == 684891633203806260 or guild == 650060149100249091 or guild == 368762307473571840:
            return await ctx.send("You cannot blacklist that guild")

        if db_check is not None:
            return await ctx.send("This guild is already in my blacklist.")

        await self.bot.db.execute("INSERT INTO blockedguilds(guild_id, reason, dev) VALUES ($1, $2, $3)", guild, reason, ctx.author.id)

        await ctx.send(f"I've successfully added **{guild}** guild to my blacklist", delete_after=10)
        try:
            g = self.bot.get_guild(guild)
            await g.leave()
        except Exception:
            pass

    @admin.command(brief="Unblacklist a guild")
    async def guildunblock(self, ctx, guild: int):
        """ Unblacklist bot from blacklisted guild """

        db_check = await self.bot.db.fetchval("SELECT guild_id FROM blockedguilds WHERE guild_id = $1", guild)

        if db_check is None:
            return await ctx.send("This guild isn't in my blacklist.")

        await self.bot.db.execute("DELETE FROM blockedguilds WHERE guild_id = $1", guild)

        await ctx.send(f"I've successfully removed **{guild}** guild from my blacklist", delete_after=10)

    @admin.command(brief="Bot block user")
    async def botblock(self, ctx, user: discord.User, *, reason: str = None):
        """ Blacklist someone from bot commands """

        if reason is None:
            reason = "No reason"

        db_check = await self.bot.db.fetchval("SELECT user_id FROM blacklist WHERE user_id = $1", user.id)

        if user.id == 345457928972533773 or user.id == 373863656607318018:
            return await ctx.send("You cannot blacklist that user")

        if db_check is not None:
            return await ctx.send("This user is already in my blacklist.")

        await self.bot.db.execute("INSERT INTO blacklist(user_id, reason) VALUES ($1, $2)", user.id, reason)

        await ctx.send(f"I've successfully added **{user}** to my blacklist", delete_after=10)

    @admin.command(brief="Bot unblock user")
    async def botunblock(self, ctx, user: discord.User):
        """ Unblacklist someone from bot commands """

        db_check = await self.bot.db.fetchval("SELECT user_id FROM blacklist WHERE user_id = $1", user.id)

        if db_check is None:
            return await ctx.send("This user isn't in my blacklist.")

        await self.bot.db.execute("DELETE FROM blacklist WHERE user_id = $1", user.id)

        await ctx.send(f"I've successfully removed **{user}** from my blacklist", delete_after=10)


# ! Social 

    @admin.command(brief="DM a user", description="Direct message a user. DO NOT ABUSE IT!")
    async def dm(self, ctx, user: discord.User, *, msg: str):
        """ DM an user """
        try:
            await user.send(msg)
            logchannel = self.bot.get_channel(674929832596865045)
            logembed = discord.Embed(
                title=f"I've DM'ed to {user}", description=msg, color=0x0DC405)
            await logchannel.send(embed=logembed)
            await ctx.message.delete()

        except discord.errors.Forbidden:
            await ctx.author.send("Couldn't send message to that user. Maybe he's not in the same server with me?")
            await ctx.message.delete()

    @commands.command(aliases=['deny'], brief="Deny suggestion", description="Deny suggestion you think is not worth adding or already exists.")
    async def suggestdeny(self, ctx, suggestion_id: int, *, note: str):
        """Deny someones suggestion"""
        await ctx.message.delete()

        approved = await self.bot.db.fetchval("SELECT approved FROM suggestions WHERE suggestion_id = $1", suggestion_id)

        if approved == True:
            return await ctx.author.send(f"{emotes.warning} You're trying to deny already denied suggestion.")

        message_id = await self.bot.db.fetchval("SELECT msg_id FROM suggestions WHERE suggestion_id = $1", suggestion_id)

        if message_id is None:
            return await ctx.author.send(f"Suggestion with id: **{suggestion_id}** doesn't exist.")

        channel = self.bot.get_channel(674929868345180160)
        message = await ctx.channel.fetch_message(id=message_id)
        embed = message.embeds[0]


        embed.color = 0xFF0202
        embed.set_footer(text=f"Suggestion was denied")
        embed.add_field(name="Note:", value=note)
        await message.clear_reactions()
        await message.edit(embed=embed)

        await self.bot.db.execute("UPDATE suggestions SET approved = $1 WHERE suggestion_id = $2", True, suggestion_id)
        suggestion_ownerid = await self.bot.db.fetchval("SELECT user_id FROM suggestions WHERE suggestion_id = $1", suggestion_id)
        suggestion_owner = self.bot.get_user(suggestion_ownerid)
        suggestion_info = await self.bot.db.fetchval("SELECT suggestion_info FROM suggestions WHERE suggestion_id = $1", suggestion_id)
        trackers = await self.bot.db.fetch("SELECT user_id FROM track_suggest WHERE suggestion_id = $1", suggestion_id)
        to_send = []
        for user in trackers:
            to_send.append(user['user_id'])

        for user in to_send:
            try:
                e = discord.Embed(color=self.bot.error_color, title=f"Suggestion was denied", description=f"Suggestion with an id of: **{suggestion_id}** and suggested by **{suggestion_owner}** was denied for a: `{note}`")
                e.add_field(name="Suggestion:", value=suggestion_info)
                user = self.bot.get_user(user)
                await user.send(embed=e)
                await self.bot.db.execute("DELETE FROM track_suggest WHERE user_id = $1 AND suggestion_id = $2", user.id, suggestion_id)
            except Exception as e:
                print(e)
                pass

    @commands.command(aliases=['approve'], brief="Approve suggestion", description="Approve suggestion you think is worth adding")
    @commands.is_owner()
    async def suggestapprove(self, ctx, suggestion_id: int, *, note: str):
        """Approve someones suggestion."""

        await ctx.message.delete()

        approved = await self.bot.db.fetchval("SELECT approved FROM suggestions WHERE suggestion_id = $1", suggestion_id)

        if approved == True:
            return await ctx.author.send(f"{emotes.warning} You're trying to approve already approved suggestion.")

        message_id = await self.bot.db.fetchval("SELECT msg_id FROM suggestions WHERE suggestion_id = $1", suggestion_id)

        if message_id is None:
            return await ctx.author.send(f"Suggestion with id: **{suggestion_id}** doesn't exist.")

        message = await ctx.channel.fetch_message(message_id)
        embed = message.embeds[0]

        embed.color = 0x00E82E
        embed.set_footer(text=f"Suggestion was approved")
        embed.add_field(name="Note", value=note)
        await message.clear_reactions()
        await message.edit(embed=embed)
        

        await self.bot.db.execute("UPDATE suggestions SET approved = $1 WHERE suggestion_id = $2", True, suggestion_id)
        suggestion_ownerid = await self.bot.db.fetchval("SELECT user_id FROM suggestions WHERE suggestion_id = $1", suggestion_id)
        suggestion_owner = self.bot.get_user(suggestion_ownerid)
        suggestion_info = await self.bot.db.fetchval("SELECT suggestion_info FROM suggestions WHERE suggestion_id = $1", suggestion_id)
        trackers = await self.bot.db.fetch("SELECT user_id FROM track_suggest WHERE suggestion_id = $1", suggestion_id)
        to_send = []
        for user in trackers:
            to_send.append(user['user_id'])

        for user in to_send:
            try:
                e = discord.Embed(color=self.bot.memberlog_color, title=f"Suggestion was approved", description=f"Suggestion with an id of: **{suggestion_id}** and suggested by **{suggestion_owner}** was approved with a note: `{note}`")
                e.add_field(name="Suggestion:", value=suggestion_info)
                user = self.bot.get_user(user)
                await user.send(embed=e)
                await self.bot.db.execute("DELETE FROM track_suggestion WHERE user_id = $1 AND suggestion_id = $2", user.id, suggestion_id)
            except Exception as e:
                print(e)
                pass

    @commands.command(brief="Approve a bug", description="Approve a bug that is not fake")
    @commands.is_owner()
    async def bugapprove(self, ctx, bug_id: int, *, note: str):
        """ Approve bug report """
        await ctx.message.delete()
        approved = await self.bot.db.fetchval("SELECT approved FROM bugs WHERE bug_id = $1", bug_id)

        if approved == True:
            return await ctx.author.send(f"{emotes.warning} You're trying to approve already approved bug report.")

        message_id = await self.bot.db.fetchval("SELECT msg_id FROM bugs WHERE bug_id = $1", bug_id)

        if message_id is None:
            return await ctx.author.send(f"Bug with id: **{bug_id}** doesn't exist.")

        channel = ctx.channel
        message = await channel.fetch_message(message_id)
        embed = message.embeds[0]

        embed.color = 0x00E82E
        embed.set_footer(text = "Bug was approved")
        embed.add_field(name="Note", value=note, inline=False)
        await message.edit(embed=embed)
        await message.clear_reactions()

        await self.bot.db.execute("UPDATE bugs SET approved = $1 WHERE bug_id = $2", True, bug_id)
        bug_ownerid = await self.bot.db.fetchval("SELECT user_id FROM bugs WHERE bug_id = $1", bug_id)
        bug_owner = self.bot.get_user(bug_ownerid)
        bug_info = await self.bot.db.fetchval("SELECT bug_info FROM bugs WHERE bug_id = $1", bug_id)
        trackers = await self.bot.db.fetch("SELECT user_id FROM track_bug WHERE bug_id = $1", bug_id)
        to_send = []
        for user in trackers:
            to_send.append(user['user_id'])

        for user in to_send:
            try:
                e = discord.Embed(color=self.bot.memberlog_color, title=f"Bug was approved", description=f"Bug with an id of: **{bug_id}** and reported by **{bug_owner}** was approved with a note: `{note}`")
                e.add_field(name="Bug that was reported:", value=bug_info)
                user = self.bot.get_user(user)
                await user.send(embed=e)
                await self.bot.db.execute("DELETE FROM track_bug WHERE user_id = $1 AND bug_id = $2", user.id, bug_id)
            except Exception as e:
                print(e)
                pass

    @commands.command(brief="Deny a bug")
    @commands.is_owner()
    async def bugdeny(self, ctx, bug_id: int, *, note: str):
        """ Deny bug report """
        await ctx.message.delete()
        approved = await self.bot.db.fetchval("SELECT approved FROM bugs WHERE bug_id = $1", bug_id)

        if approved == True:
            return await ctx.author.send(f"{emotes.warning} You're trying to deny already denied bug report.")
        message_id = await self.bot.db.fetchval("SELECT msg_id FROM bugs WHERE bug_id = $1", bug_id)
        if message_id is None:
            return await ctx.author.send(f"Bug with id: **{bug_id}** doesn't exist.")
        channel = ctx.channel
        message = await channel.fetch_message(message_id)
        embed = message.embeds[0]

        embed.color = 0xFF0202
        embed.set_footer(text = "Bug was denied")
        embed.add_field(name="Note", value=note, inline=False)
        await message.edit(embed=embed)
        await message.clear_reactions()

        await self.bot.db.execute("UPDATE bugs SET approved = $1 WHERE bug_id = $2", True, bug_id)
        bug_ownerid = await self.bot.db.fetchval("SELECT user_id FROM bugs WHERE bug_id = $1", bug_id)
        bug_owner = self.bot.get_user(bug_ownerid)
        bug_info = await self.bot.db.fetchval("SELECT bug_info FROM bugs WHERE bug_id = $1", bug_id)
        trackers = await self.bot.db.fetch("SELECT user_id FROM track_bug WHERE bug_id = $1", bug_id)
        to_send = []
        for user in trackers:
            to_send.append(user['user_id'])

        for user in to_send:
            try:
                e = discord.Embed(color=self.bot.error_color, title=f"Bug was denied", description=f"Bug with an id of: **{bug_id}** and reported by **{bug_owner}** was denied for: `{note}`")
                e.add_field(name="Bug that was reported:", value=bug_info)
                user = self.bot.get_user(user)
                await user.send(embed=e)
                await self.bot.db.execute("DELETE FROM track_bug WHERE user_id = $1 AND bug_id = $2", user.id, bug_id)
            except Exception as e:
                print(e)
                pass

# ! Command managment

    @admin.command(brief="Disable enabled cmd")
    async def disablecmd(self, ctx, command):
        """Disable the given command. A few important main commands have been blocked from disabling for obvious reasons"""
        cant_disable = ["help", "jishaku", "dev", "disablecmd", "enablecmd", 'admin']
        cmd = self.bot.get_command(command)

        if cmd is None:
            embed = discord.Embed(color=self.bot.logembed_color, description=f"{emotes.red_mark} Command **{command}** doesn't exist.")
            return await ctx.send(embed=embed)

        data = await self.bot.db.fetchval("SELECT * FROM cmds WHERE command = $1", str(cmd.name))

        if cmd.name in cant_disable:
            embed = discord.Embed(color=self.bot.logembed_color, description=f"{emotes.red_mark} Why are you trying to disable **{cmd.name}** you dum dum.")
            return await ctx.send(embed=embed)

        if data is None:
            await self.bot.db.execute("INSERT INTO cmds(command) VALUES ($1)", str(cmd.name))
            embed = discord.Embed(color=self.bot.logembed_color, description=f"{emotes.white_mark} Okay. **{cmd.name}** was disabled.")
            return await ctx.send(embed=embed)

        if data is not None:
            embed = discord.Embed(color=self.bot.logembed_color, description=f"{emotes.red_mark} **{cmd.name}** is already disabled")
            return await ctx.send(embed=embed)


    @admin.command(brief="Enable disabled cmd")
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

# ! System information
    
    @admin.command(brief="System information", description="Check system information")
    async def systeminfo(self, ctx):
        """ Check system information bot's running on """

        try:
            cpu_per = psutil.cpu_percent()
            cores = psutil.cpu_count()
            memory = psutil.virtual_memory().total >> 20
            mem_usage = psutil.virtual_memory().used >> 20
            storage_free = psutil.disk_usage('/').free >> 30
            em = discord.Embed(color=self.bot.embed_color,
                               description=f"Hosting OS: **{platform.platform()}**\n"
                                           f"Cores: **{cores}**\n"
                                           f"CPU: **{cpu_per}%**\n"
                                           f"RAM: **{mem_usage}/{memory} MB**\n"
                                           f"STORAGE: **{storage_free} GB free**")
            await ctx.send(embed=em)
        except Exception as e:
            await ctx.send("Looks like there's no system information")
    
    @admin.command(brief='Clear user nicknames')
    async def clearnicks(self, ctx, user: discord.User, guild: int = None):

        db_check = await self.bot.db.fetch("SELECT * FROM nicknames WHERE user_id = $1", user.id)
        
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


def setup(bot):
    bot.add_cog(admin(bot))
