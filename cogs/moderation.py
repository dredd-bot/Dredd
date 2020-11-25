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
import datetime
import asyncio
import random
import typing
import re
import argparse
import shlex
from discord.ext import commands
from discord.utils import escape_markdown, sleep_until
from datetime import datetime
from utils import btime, default, checks
from utils.checks import BannedMember, MemberID
from utils.paginator import Pages
from db import emotes
from utils.default import responsible, timetext, date
from io import BytesIO
from utils.default import color_picker
from utils.caches import CacheManager as cm

class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(message)

class moderation(commands.Cog, name="Moderation"):

    def __init__(self, bot):
        self.bot = bot
        self.big_icon = "https://cdn.discordapp.com/emojis/747192603640070237.png?v=1"
        self.help_icon = "<:bann:747192603640070237>"
        self.color = color_picker('colors')

# ! Commands

#########################################################################################################

    async def log_delete(self, ctx, data, messages=None):
        check = await self.bot.db.fetchval("SELECT * FROM msgdelete WHERE guild_id = $1", ctx.guild.id)

        if check is not None:
            channel = await self.bot.db.fetchval("SELECT channel_id FROM msgdelete WHERE guild_id = $1", ctx.guild.id)
            chan = self.bot.get_channel(channel)
            message_history = await chan.send(content='You can either download the logs, or view it in the message below', file=data)
            data = f"<https://txt.discord.website/?txt={chan.id}/{message_history.attachments[0].id}/{ctx.message.id}>"
            #e = discord.Embed(color=self.bot.logging_color, description=f"{messages} messages were deleted by **{ctx.author}**. [View File]({data})")
            text = f"**{messages}** Message(s) were deleted by **{ctx.author}**. You can view those messages here as well: **(BETA)** "
            text += data
            await message_history.edit(content=text)
        else:
            pass

    async def do_removal(self, ctx, limit, predicate, *, before=None, after=None):
        if limit > 2000:
            return await ctx.send("You can purge maximum amount of 2000 messages!")

        if before is None:
            before = ctx.message
        else:
            before = discord.Object(id=before)

        if after is not None:
            after = discord.Object(id=after)
        # if predicate is True:
        #     msgs = []
        #     for message in await ctx.channel.history(limit=limit).flatten():
        #         msgs.append(f"[{message.created_at}] {message.author} - {message.content}\n")
        #     msgs.reverse()
        #     msghis = "".join(msgs)

        try:
            deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate)
            # if predicate is True:
            #     await self.log_delete(ctx, data=discord.File(BytesIO(("".join(msgs)).encode("utf-8")), filename=f"{ctx.message.id}.txt"), messages=len(deleted))
        except discord.Forbidden as e:
            return await ctx.send("No permissions")
        except discord.HTTPException as e:
            return await ctx.send(f"Looks like you got an error: {e}")
    
        deleted = len(deleted)
        if deleted == 1:
            messages = f"{emotes.log_msgdelete} Deleted **1** message"
        elif deleted > 1:
            messages = f"{emotes.log_msgdelete} Deleted **{deleted}** messages"
        elif deleted == 0:
            messages = f"Was unable to delete any messages"

        to_send = '\n'.join(messages)

        if len(to_send) > 2000:

            text = f"{emotes.log_msgdelete} Removed `{deleted}` messages"
            await ctx.channel.send(text, delete_after=5)
        else:
            e = discord.Embed(color=self.color['embed_color'])
            e.description = f"{messages}"
            await ctx.channel.send(embed=e, delete_after=5)

    async def log_mute(self, ctx, member=None, reason=None, timed=None):
        check = await self.bot.db.fetchval("SELECT * FROM moderation WHERE guild_id = $1", ctx.guild.id)

        if check is None:
            return
        elif check is not None:
            channel = await self.bot.db.fetchval("SELECT channel_id FROM moderation WHERE guild_id = $1", ctx.guild.id)
            chan = self.bot.get_channel(channel)

            case = cm.get_cache(self.bot, ctx.guild.id, 'case_num')
            casenum = case or 1

            e = discord.Embed(color=self.color['logging_color'], description=f"{emotes.log_memberedit} **{member}** muted `[#{casenum}]`")
            e.add_field(name="Moderator:", value=f"{ctx.author} ({ctx.author.id})", inline=False)
            e.add_field(name="Reason:", value=f"{reason}")
            if timed:
                e.add_field(name="Mute duration:", value=f"{btime.human_timedeltas(timed, suffix=None)}")
            e.set_thumbnail(url=member.avatar_url_as(format='png'))
            e.set_footer(text=f"Member ID: {member.id}")

            await chan.send(embed=e)
            self.bot.case_num[ctx.guild.id] += 1
            await self.bot.db.execute("UPDATE modlog SET case_num = case_num + 1 WHERE guild_id = $1", ctx.guild.id)
    
    async def log_unmute(self, ctx, member=None, reason=None):
        check = await self.bot.db.fetchval("SELECT * FROM moderation WHERE guild_id = $1", ctx.guild.id)

        if check is None:
            return
        elif check is not None:
            channel = await self.bot.db.fetchval("SELECT channel_id FROM moderation WHERE guild_id = $1", ctx.guild.id)
            chan = self.bot.get_channel(channel)

            case = cm.get_cache(self.bot, ctx.guild.id, 'case_num')
            casenum = case or 1

            e = discord.Embed(color=self.color['logging_color'], description=f"{emotes.log_memberedit} **{member}** unmuted `[#{casenum}]`")
            e.add_field(name="Moderator:", value=f"{ctx.author} ({ctx.author.id})", inline=False)
            e.add_field(name="Reason:", value=f"{reason}", inline=False)
            e.set_thumbnail(url=member.avatar_url_as(format='png'))
            e.set_footer(text=f"Member ID: {member.id}")

            await chan.send(embed=e)
            self.bot.case_num[ctx.guild.id] += 1
            await self.bot.db.execute("UPDATE modlog SET case_num = case_num + 1 WHERE guild_id = $1", ctx.guild.id)

    async def cog_check(self, ctx):
        if ctx.guild is None:
            return False
        return True


#########################################################################################################

    @commands.command(brief="Change someones nickname", aliases=["nick"])
    @commands.guild_only()
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def setnick(self, ctx, members: commands.Greedy[discord.Member], *, name: str = None):
        """ Change or remove anyones nickname """
        
        if not members:
            return await ctx.send(f"{emotes.red_mark} | You're missing an argument - **members**")
        if name and len(name) > 32:
            return await ctx.send(f"{emotes.red_mark} Nickname is too long! You can't have nicknames longer than 32 characters")
        error = '\n'
        try:
            total = len(members)
            if total > 10:
                return await ctx.send("You can re-name only 10 members at once!")

            failed = 0
            failed_list = []
            success_list = []
            for member in members:
                if member == ctx.author:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - you are the member?")
                    continue
                if member.top_role.position >= ctx.author.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above you in role hierarchy or has the same role.")
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above me in role hierarchy or has the same role.")
                    continue
                try:
                    await member.edit(nick=name)
                    success_list.append(f"{member.mention} ({member.id})")
                except discord.HTTPException as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
                except discord.Forbidden as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
            muted = ""
            notmuted = ""
            if success_list and not failed_list:
                muted += "**I've successfully re-named {0} member(s):**\n".format(total)
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted)
            if success_list and failed_list:
                muted += "**I've successfully re-named {0} member(s):**\n".format(total - failed)
                notmuted += f"**However I failed to re-name the following {failed} member(s):**\n"
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted + notmuted)
            if not success_list and failed_list:  
                notmuted += f"**I failed to re-name all the members:**\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(notmuted)
                    
        except Exception as e:
            print(e)
            return await ctx.send(f"{emotes.warning} Something failed! Error: (Please report it to my developers):\n- {e}")

    @commands.command(brief="Kick someone from the server")
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True, manage_messages=True)
    async def kick(self, ctx, members: commands.Greedy[discord.Member], *, reason: str = None):
        """
        Kicks member from server.
        You can also provide multiple members to kick.
        """
        if not members:
            return await ctx.send(f"{emotes.red_mark} | You're missing an argument - **members**")
            
        error = '\n'
        try:
            total = len(members)
            if total > 10:
                return await ctx.send("You can kick only 10 members at once!") 

            failed = 0
            failed_list = []
            success_list = []
            for member in members:
                if member == ctx.author:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - you are the member?")
                    continue
                if member.top_role.position >= ctx.author.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above you in role hierarchy or has the same role.")
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above me in role hierarchy or has the same role.")
                    continue
                try:
                    await ctx.guild.kick(member, reason=responsible(ctx.author, f"{reason or 'No reason'}"))
                    success_list.append(f"{member.mention} ({member.id})")
                except discord.HTTPException as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
                except discord.Forbidden as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
            muted = ""
            notmuted = ""
            if success_list and not failed_list:
                muted += "**I've successfully kicked {0} member(s):**\n".format(total)
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted)
            if success_list and failed_list:
                muted += "**I've successfully kicked {0} member(s):**\n".format(total - failed)
                notmuted += f"**However I failed to kick the following {failed} member(s):**\n"
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted + notmuted)
            if not success_list and failed_list:  
                notmuted += f"**I failed to kick all the members:**\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(notmuted)
                    
        except Exception as e:
            print(e)
            return await ctx.send(f"{emotes.warning} Something failed! Error: (Please report it to my developers):\n- {e}")

    @commands.command(brief="Ban someone from the server")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True, manage_messages=True)
    async def ban(self, ctx, members: commands.Greedy[discord.Member], *, reason: str = None):
        """
        Ban member from the server.
        You can also provide multiple members to ban.
        """

        if not members:
            return await ctx.send(f"{emotes.red_mark} | You're missing an argument - **members**")

        error = '\n'
        try:
            total = len(members)
            if total > 10:
                return await ctx.send("You can ban only 10 members at once!") 

            failed = 0
            failed_list = []
            success_list = []
            for member in members:
                if member == ctx.author:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - you are the member?")
                    continue
                if member.top_role.position >= ctx.author.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above you in role hierarchy or has the same role.")
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above me in role hierarchy or has the same role.")
                    continue
                try:
                    await ctx.guild.ban(member, reason=responsible(ctx.author, f"{reason or 'No reason'}"))
                    success_list.append(f"{member.mention} ({member.id})")
                except discord.HTTPException as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
                except discord.Forbidden as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
            muted = ""
            notmuted = ""
            if success_list and not failed_list:
                muted += "**I've successfully banned {0} member(s):**\n".format(total)
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted)
            if success_list and failed_list:
                muted += "**I've successfully banned {0} member(s):**\n".format(total - failed)
                notmuted += f"**However I failed to ban the following {failed} member(s):**\n"
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted + notmuted)
            if not success_list and failed_list:  
                notmuted += f"**I failed to ban all the members:**\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(notmuted)
                    
        except Exception as e:
            print(e)
            return await ctx.send(f"{emotes.warning} Something failed! Error: (Please report it to my developers):\n- {e}")

    @commands.command(brief='Ban someone who\'s not in the server')
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def hackban(self, ctx, user: MemberID, *, reason: str = None):
        """ Ban a user that isn't in this server """

        try:
            try:
                m = await commands.MemberConverter().convert(ctx, str(user))
                if m is not None:
                    return await ctx.send(f"{emotes.warning} Hack-ban is to ban users that are not in this server.")
            except:
                pass
            await ctx.guild.ban(user, reason=responsible(ctx.author, reason))
            await ctx.send(f"{emotes.white_mark} Banned **{await self.bot.fetch_user(user)}** for `{reason}`")
        except Exception as e:
            print(e)
            return await ctx.send(f"{emotes.error} Something failed!")

    @commands.command(brief="Unban someone from the server")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True, manage_messages=True)
    async def unban(self, ctx, user: BannedMember, *, reason: str=None):
        """
        Unbans user from server
        """
        try:
            await ctx.message.delete()
            await ctx.guild.unban(user.user, reason=responsible(ctx.author, reason))
            await ctx.send(f"{emotes.white_mark} **{user.user}** was unbanned successfully, with a reason: ``{reason}``", delete_after=15)
        except Exception as e:
            print(e)
            await ctx.send(f"{emotes.red_mark} Something failed while trying to unban.")
    
    @commands.command(brief="Unban all the users from the server")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True, manage_messages=True)
    async def unbanall(self, ctx, *, reason: str=None):
        """ Unban all users from the server """
        bans = len(await ctx.guild.bans())

        try:
            unbanned = 0
            
            if bans == 0:
                return await ctx.send("This guild has no bans.")
            
            def check(r, u):
                return u.id == ctx.author.id and r.message.id == checkmsg.id
                
            checkmsg = await ctx.send(f"Are you sure you want to unban **{bans}** members from this guild?")
            await checkmsg.add_reaction(f'{emotes.white_mark}')
            await checkmsg.add_reaction(f'{emotes.red_mark}')
            await checkmsg.add_reaction('🔍')
            react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30.0)

            # ? They want to unban everyone

            if str(react) == f"{emotes.white_mark}": 
                unb = await ctx.channel.send(f"Unbanning **{bans}** members from this guild.")    
                await checkmsg.delete()
                for user in await ctx.guild.bans():
                    await ctx.guild.unban(user.user, reason=responsible(ctx.author, reason))
                    await unb.edit(content=f"{emotes.loading1} Processing unbans...")
                await unb.edit(content=f"Unbanned **{bans}** members from this guild.", delete_after=15)

            # ? They don't want to unban anyone

            if str(react) == f"{emotes.red_mark}":      
                await checkmsg.delete()
                await ctx.channel.send("Alright. Not unbanning anyone..")

            # ? They want to see ban list

            if str(react) == "🔍":
                await checkmsg.clear_reactions()
                ban = []
                for banz in await ctx.guild.bans():
                    ben = f"• {banz.user}\n"
                    ban.append(ben)
                    e = discord.Embed(color=self.color['embed_color'], title=f"Bans for {ctx.guild}", description="".join(ban))
                    e.set_footer(text="Are you sure you want to unban them all?")
                    await checkmsg.edit(content='', embed=e)
                await checkmsg.add_reaction(f'{emotes.white_mark}')
                await checkmsg.add_reaction(f'{emotes.red_mark}')
                react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30.0)

                # ? They want to unban everyone
                

                if str(react) == f"{emotes.white_mark}": 
                    unb = await ctx.channel.send(f"Unbanning **{bans}** members from this guild.")    
                    await checkmsg.delete()
                    for user in await ctx.guild.bans():
                        await ctx.guild.unban(user.user, reason=responsible(ctx.author, reason))
                        await unb.edit(content=f"{emotes.loading1} Processing unbans...")
                    await unb.edit(content=f"Unbanned **{bans}** members from this guild.", delete_after=15)

                # ? They don't want to unban anyone

                if str(react) == f"{emotes.red_mark}":      
                    await checkmsg.delete()
                    await ctx.channel.send("Alright. Not unbanning anyone..")

        except Exception as e:
            print(e)
            return                

    @commands.command(brief="Softban someone from the server", description="Softbans member from the server")
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True, manage_messages=True)
    async def softban(self, ctx, members: commands.Greedy[discord.Member], reason: str = None):
        """ Softbans member from the server """

        if not members:
            return await ctx.send(f"{emotes.red_mark} | You're missing an argument - **members**")

        error = '\n'
        try:
            total = len(members)
            if total > 10:
                return await ctx.send("You can softban only 10 members at once!") 

            failed = 0
            failed_list = []
            success_list = []
            for member in members:
                if member == ctx.author:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - you are the member?")
                    continue
                if member.top_role.position >= ctx.author.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above you in role hierarchy or has the same role.")
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above me in role hierarchy or has the same role.")
                    continue
                try:
                    await ctx.guild.ban(member, reason=responsible(ctx.author, f"{reason or 'No reason'}"))
                    await ctx.guild.unban(member, reason=responsible(ctx.author, reason))
                    success_list.append(f"{member.mention} ({member.id})")
                except discord.HTTPException as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
                except discord.Forbidden as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
            muted = ""
            notmuted = ""
            if success_list and not failed_list:
                muted += "**I've successfully soft-banned {0} member(s):**\n".format(total)
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted)
            if success_list and failed_list:
                muted += "**I've successfully soft-banned {0} member(s):**\n".format(total - failed)
                notmuted += f"**However I failed to soft-ban the following {failed} member(s):**\n"
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted + notmuted)
            if not success_list and failed_list:  
                notmuted += f"**I failed to soft-ban all the members:**\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(notmuted)
                    
        except Exception as e:
            print(e)
            return await ctx.send(f"{emotes.warning} Something failed! Error: (Please report it to my developers):\n- {e}")
    
    @commands.command(brief="Mute someone in the server")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def mute(self, ctx, members: commands.Greedy[discord.Member], *, reason: str = None):
        """ Mute someone in your server. 
        Make sure you have muted role in your server and properly configured."""
        if not members:
            return await ctx.send(f"{emotes.red_mark} | You're missing an argument - **members**")
        muterole = discord.utils.find(lambda r: r.name.lower() == "muted", ctx.guild.roles)

        if muterole is None:
            return await ctx.send(f"{emotes.red_mark} I can't find a role named `Muted` Are you sure you've made one?")

        if muterole.position > ctx.guild.me.top_role.position:
            return await ctx.send(f"{emotes.warning} Mute role is higher than me and I cannot access it.")
        error = '\n'
        try:
            total = len(members)
            if total > 10:
                return await ctx.send("You can mute only 10 members at once!")                    
            
            failed = 0
            failed_list = []
            success_list = []
            for member in members:
                if member == ctx.author:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - you are the member?")
                    continue
                if muterole in member.roles:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is already muted.")
                    continue
                if member.top_role.position >= ctx.author.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above you in role hierarchy or has the same role.")
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above me in role hierarchy or has the same role.")
                    continue
                try:
                    await member.add_roles(muterole, reason=responsible(ctx.author, reason))
                    await self.log_mute(ctx, member=member, reason=reason)
                    await self.bot.db.execute("INSERT INTO moddata(guild_id, user_id, mod_id, reason, time, role_id, type) VALUES($1, $2, $3, $4, $5, $6, $7)", ctx.guild.id, member.id, ctx.author.id, responsible(ctx.author, reason), None, muterole.id, 'mute')
                    success_list.append(f"{member.mention} ({member.id})")
                except discord.HTTPException as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
                except discord.Forbidden as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
            muted = ""
            notmuted = ""
            if success_list and not failed_list:
                muted += "**I've successfully muted {0} member(s):**\n".format(total)
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted)
            if success_list and failed_list:
                muted += "**I've successfully muted {0} member(s):**\n".format(total - failed)
                notmuted += f"**However I failed to mute the following {failed} member(s):**\n"
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted + notmuted)
            if not success_list and failed_list:  
                notmuted += f"**I failed to mute all the members:**\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(notmuted)
        
        except Exception as e:
            print(e)
            return await ctx.send(f"{emotes.warning} Something failed! Error: (Please report it to my developers):\n- {e}") 

    @commands.command(brief="Temporarily mute someone in the server")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def tempmute(self, ctx, members: commands.Greedy[discord.Member], duration: btime.FutureTime, *, reason: str=None):
        """ You can mute someone temporarily.
        
        Note: If you'll be getting time format error, put the time into \"time\" and it'll work just fine """

        if not members:
            return await ctx.send(f"{emotes.red_mark} | You're missing an argument - **members**")
        muterole = discord.utils.find(lambda r: r.name.lower() == "muted", ctx.guild.roles)

        if muterole is None:
            return await ctx.send(f"{emotes.red_mark} I can't find a role named `Muted` Are you sure you've made one?")

        if muterole.position > ctx.guild.me.top_role.position:
            return await ctx.send(f"{emotes.warning} Mute role is higher than me and I cannot access it.")
        error = '\n'
        try:
            total = len(members)
            if total > 10:
                return await ctx.send("You can mute only 10 members at once!")                    
            
            failed = 0
            failed_list = []
            success_list = []
            for member in members:
                if member == ctx.author:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - you are the member?")
                    continue
                if muterole in member.roles:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is already muted.")
                    continue
                if member.top_role.position >= ctx.author.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above you in role hierarchy or has the same role.")
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above me in role hierarchy or has the same role.")
                    continue
                try:
                    await member.add_roles(muterole, reason=responsible(ctx.author, reason))
                    await self.log_mute(ctx, member=member, reason=reason, timed=duration.dt)
                    await self.bot.temp_punishment(ctx.guild.id, member.id, ctx.author.id, reason, duration.dt, muterole.id, 'mute')
                    success_list.append(f"{member.mention} ({member.id})")
                except discord.HTTPException as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
                except discord.Forbidden as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
            muted = ""
            notmuted = ""
            if success_list and not failed_list:
                muted += "**I've successfully muted {0} member(s):**\n".format(total)
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted)
            if success_list and failed_list:
                muted += "**I've successfully muted {0} member(s):**\n".format(total - failed)
                notmuted += f"**However I failed to mute the following {failed} member(s):**\n"
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted + notmuted)
            if not success_list and failed_list:  
                notmuted += f"**I failed to mute all the members:**\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(notmuted)
                    
        except Exception as e:
            print(e)
            return await ctx.send(f"{emotes.warning} Something failed! Error: (Please report it to my developers):\n- {e}") 
    @commands.command(brief="Temporarily ban someone from the server")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def tempban(self, ctx, members: commands.Greedy[discord.Member], duration: btime.FutureTime, *, reason: str=None):
        """ You can ban someone temporarily.
        
        Note: If you'll be getting time format error, put the time into \"time\" and it'll work just fine """

        if not members:
            return await ctx.send(f"{emotes.red_mark} | You're missing an argument - **members**")

        error = '\n'
        try:
            total = len(members)
            if total > 10:
                return await ctx.send("You can ban only 10 members at once!") 

            failed = 0
            failed_list = []
            success_list = []
            for member in members:
                if member == ctx.author:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - you are the member?")
                    continue
                if member.top_role.position >= ctx.author.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above you in role hierarchy or has the same role.")
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above me in role hierarchy or has the same role.")
                    continue
                try:
                    await ctx.guild.ban(member, reason=responsible(ctx.author, f"{reason or 'No reason'}\nBanned until: {duration.dt}"))
                    await self.bot.temp_ban_log(ctx.guild.id, member.id, ctx.author.id, reason, duration.dt, 'ban')
                    success_list.append(f"{member.mention} ({member.id})")
                except discord.HTTPException as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
                except discord.Forbidden as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
            muted = ""
            notmuted = ""
            if success_list and not failed_list:
                muted += "**I've successfully banned {0} member(s):**\n".format(total)
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted)
            if success_list and failed_list:
                muted += "**I've successfully banned {0} member(s):**\n".format(total - failed)
                notmuted += f"**However I failed to ban the following {failed} member(s):**\n"
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted + notmuted)
            if not success_list and failed_list:  
                notmuted += f"**I failed to ban all the members:**\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(notmuted)
                    
        except Exception as e:
            print(e)
            return await ctx.send(f"{emotes.warning} Something failed! Error: (Please report it to my developers):\n- {e}") 

    @commands.command(brief='Unmute someone in the server')
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def unmute(self, ctx, members: commands.Greedy[discord.Member], *, reason: str = None):
        
        if not members:
            return await ctx.send(f"{emotes.red_mark} | You're missing an argument - **members**")
        muterole = discord.utils.find(lambda r: r.name.lower() == "muted", ctx.guild.roles)

        if muterole is None:
            return await ctx.send(f"{emotes.red_mark} I can't find a role named `Muted` Are you sure you've made one?")

        if muterole.position > ctx.guild.me.top_role.position:
            return await ctx.send(f"{emotes.warning} Mute role is higher than me and I cannot access it.")
        error = '\n'
        try:
            total = len(members)
            if total > 10:
                return await ctx.send("You can unmute only 10 members at once!")                    
            
            failed = 0
            failed_list = []
            success_list = []
            for member in members:
                if member == ctx.author:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - you are the member?")
                    continue
                if muterole not in member.roles:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is not muted.")
                    continue
                if member.top_role.position >= ctx.author.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above you in role hierarchy or has the same role.")
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above me in role hierarchy or has the same role.")
                    continue
                try:
                    await member.remove_roles(muterole, reason=responsible(ctx.author, reason))
                    await self.log_unmute(ctx, member=member, reason=reason)
                    await self.bot.db.execute("DELETE FROM moddata WHERE guild_id = $1 AND user_id = $2", ctx.guild.id, member.id)
                    success_list.append(f"{member.mention} ({member.id})")
                except discord.HTTPException as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
                except discord.Forbidden as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
            muted = ""
            notmuted = ""
            if success_list and not failed_list:
                muted += "**I've successfully unmuted {0} member(s):**\n".format(total)
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted)
            if success_list and failed_list:
                muted += "**I've successfully unmuted {0} member(s):**\n".format(total - failed)
                notmuted += f"**However I failed to unmute the following {failed} member(s):**\n"
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted + notmuted)
            if not success_list and failed_list:  
                notmuted += f"**I failed to unmute all the members:**\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(notmuted)
        
        except Exception as e:
            print(e)
            return await ctx.send(f"{emotes.warning} Something failed! Error: (Please report it to my developers):\n- {e}") 
            
    @commands.command(brief="Dehoist members in the server")
    @commands.guild_only()
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def dehoist(self, ctx, *, nick: str):
        """ Dehoist members with non alphabetic names """        
        nickname_only = False
        try:
            hoisters = []
            changed = 0
            failed = 0
            error = ""
            await ctx.send(f'{emotes.loading2} Started dehoisting process...')
            for hoister in ctx.guild.members:
                if nickname_only:
                    if not hoister.nick: return
                    name = hoister.nick
                else:
                    name = hoister.display_name
                if not name[0].isalnum():
                    try:
                        await hoister.edit(nick=nick, reason=responsible(ctx.author, 'member was dehoisted.'))
                        changed += 1
                        hoisters.append(f"{hoister.mention} ({hoister.id}) - {hoister} ")
                    except Exception as e:
                        failed += 1
                        error += f"• {hoister.mention} ({hoister.id}) - {e}\n"
                        pass
            if not hoisters and failed == 0:
                return await ctx.send(f"{emotes.warning} | No hoisters were found.")
            
            if changed == 0 and failed != 0:
                msg = f"\n\n**I failed to dehoist {failed} member(s):**\n{error}"
                return await ctx.send(msg[:1980])
            
            if len(hoisters) > 20:
                hoisters = hoisters[:20]
            msg = f"**Following member(s) were dehoisted: `(Total: {changed})`**"
            for num, hoist in enumerate(hoisters, start=0):
                msg += f"\n`[{num+1}]` {escape_markdown(hoist, as_needed=True)}"
            
            if changed > 20:
                msg += "\nSorry, that caps out at 20."

            if failed != 0:
                msg += f"\n\n**However I failed to dehoist {failed} member(s):**\n{escape_markdown(error, as_needed=True)}"
            
            if len(msg) >= 1980:
                msg = msg[:1980]
                msg += "... Limit :("
            await ctx.send(msg)
                        
        except Exception as e:
            print(default.traceback_maker(e))
            await ctx.send(f"Error! ```py\n{e}```")
    
    @commands.command(brief="Clone a text channel")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def clone(self, ctx, channel: discord.TextChannel, *, reason: str = None):
        """ Clone text channel in the server"""
        server = ctx.message.guild
        if reason is None:
            reason = 'No reason'
        try:
            await ctx.message.delete()
        except:
            pass
        for c in ctx.guild.channels:
            if c.name == f'{channel.name}-clone':
                return await ctx.send(f"{emotes.red_mark} {channel.name} clone already exists!")     
        await channel.clone(name=f'{channel.name}-clone', reason=responsible(ctx.author, reason))
        await ctx.send(f"{emotes.white_mark} Successfully cloned {channel.name}")

    @commands.group(aliases=['clear', 'delete', 'prune'], brief="Manage messages in the chat", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx, search=100):
        """ Purge messages in the chat. Default amount is set to **100**"""
        await ctx.message.delete()
        await self.do_removal(ctx, search, lambda e: True) 
    # @purge.command(brief="Every message", description="Clear all messages in chat")
    # @commands.has_permissions(manage_messages=True)
    # @commands.bot_has_permissions(manage_messages=True)
    # @commands.guild_only()
    # async def all(self, ctx, search=100):
    #     """ Removes all messages
    #     Might take longer if you're purging messages that are older than 2 weeks """
    #     await ctx.message.delete()
    #     await self.do_removal(ctx, search, lambda e: True)
    
    @purge.command(brief="User messages", description="Clear messages sent from an user")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def user(self, ctx, member: discord.Member, search=100):
        """ Removes user messages """
        await ctx.message.delete()
        await self.do_removal(ctx, search, lambda e: e.author == member)
    
    @purge.command(name='bot')
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def _bot(self, ctx, prefix=None, search=100):
        """Removes a bot user's messages and messages with their optional prefix."""

        def predicate(m):
            return (m.webhook_id is None and m.author.bot) or (prefix and m.content.startswith(prefix))

        await self.do_removal(ctx, search, predicate)
    
    @purge.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def embeds(self, ctx, search=100):
        """Removes messages that have embeds in them."""
        await self.do_removal(ctx, search, lambda e: len(e.embeds))

    @purge.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def images(self, ctx, search=100):
        """Removes messages that have embeds or attachments."""
        await self.do_removal(ctx, search, lambda e: len(e.embeds) or len(e.attachments))
    
    @purge.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def contains(self, ctx, *, substr: str):
        """Removes all messages containing a substring.

        The substring must be at least 3 characters long.
        """
        if len(substr) < 3:
            await ctx.send(f"{emotes.warning} substring must be at least 3 characters long.")
        else:
            await self.do_removal(ctx, 100, lambda e: substr in e.content)
    
    @purge.command(name='emoji')
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def _emoji(self, ctx, search=100):
        """Removes all messages containing custom emoji."""
        custom_emoji = re.compile(r'<:(\w+):(\d+)>')
        def predicate(m):
            return custom_emoji.search(m.content)

        await self.do_removal(ctx, search, predicate)

    @purge.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def custom(self, ctx, *, args: str):
        """A more advanced purge command.

        This command uses a powerful "command line" syntax.
        Most options support multiple values to indicate 'any' match.
        If the value has spaces it must be quoted.

        The messages are only deleted if all options are met unless
        the `--or` flag is passed, in which case only if any is met.

        The following options are valid.

        `--user`: A mention or name of the user to remove.
        `--contains`: A substring to search for in the message.
        `--starts`: A substring to search if the message starts with.
        `--ends`: A substring to search if the message ends with.
        `--search`: How many messages to search. Default 100. Max 2000.
        `--after`: Messages must come after this message ID.
        `--before`: Messages must come before this message ID.

        Flag options (no arguments):

        `--bot`: Check if it's a bot user.
        `--embeds`: Check if the message has embeds.
        `--files`: Check if the message has attachments.
        `--emoji`: Check if the message has custom emoji.
        `--reactions`: Check if the message has reactions
        `--or`: Use logical OR for all options.
        `--not`: Use logical NOT for all options.
        """
        parser = Arguments(add_help=False, allow_abbrev=False)
        parser.add_argument('--user', nargs='+')
        parser.add_argument('--contains', nargs='+')
        parser.add_argument('--starts', nargs='+')
        parser.add_argument('--ends', nargs='+')
        parser.add_argument('--or', action='store_true', dest='_or')
        parser.add_argument('--not', action='store_true', dest='_not')
        parser.add_argument('--emoji', action='store_true')
        parser.add_argument('--bot', action='store_const', const=lambda m: m.author.bot)
        parser.add_argument('--embeds', action='store_const', const=lambda m: len(m.embeds))
        parser.add_argument('--files', action='store_const', const=lambda m: len(m.attachments))
        parser.add_argument('--reactions', action='store_const', const=lambda m: len(m.reactions))
        parser.add_argument('--search', type=int, default=100)
        parser.add_argument('--after', type=int)
        parser.add_argument('--before', type=int)

        try:
            args = parser.parse_args(shlex.split(args))
        except Exception as e:
            await ctx.send(str(e))
            return

        predicates = []
        if args.bot:
            predicates.append(args.bot)

        if args.embeds:
            predicates.append(args.embeds)

        if args.files:
            predicates.append(args.files)

        if args.reactions:
            predicates.append(args.reactions)

        if args.emoji:
            custom_emoji = re.compile(r'<:(\w+):(\d+)>')
            predicates.append(lambda m: custom_emoji.search(m.content))

        if args.user:
            users = []
            converter = commands.MemberConverter()
            for u in args.user:
                try:
                    user = await converter.convert(ctx, u)
                    users.append(user)
                except Exception as e:
                    await ctx.send(str(e))
                    return

            predicates.append(lambda m: m.author in users)

        if args.contains:
            predicates.append(lambda m: any(sub in m.content for sub in args.contains))

        if args.starts:
            predicates.append(lambda m: any(m.content.startswith(s) for s in args.starts))

        if args.ends:
            predicates.append(lambda m: any(m.content.endswith(s) for s in args.ends))

        op = all if not args._or else any
        def predicate(m):
            r = op(p(m) for p in predicates)
            if args._not:
                return not r
            return r

        args.search = max(0, min(2000, args.search)) # clamp from 0-2000
        await self.do_removal(ctx, args.search, predicate, before=args.before, after=args.after)
    
    @commands.command(brief="Voice mute someone in the server", aliases=["vmute"])
    @commands.guild_only()
    @commands.has_guild_permissions(mute_members=True)
    @commands.bot_has_guild_permissions(mute_members=True)
    async def voicemute(self, ctx, members: commands.Greedy[discord.Member], reason: str=None):
        """ Voice mute member in the server """

        if not members:
            return await ctx.send(f"{emotes.red_mark} | You're missing an argument - **members**")
            
        error = '\n'
        try:
            total = len(members)
            if total > 10:
                return await ctx.send("You can voice mute only 10 members at once!") 

            failed = 0
            failed_list = []
            success_list = []
            for member in members:
                if member == ctx.author:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - you are the member?")
                    continue
                if member.top_role.position >= ctx.author.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above you in role hierarchy or has the same role.")
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above me in role hierarchy or has the same role.")
                    continue
                try:
                    await member.edit(mute=True, reason=responsible(ctx.author, reason))
                    success_list.append(f"{member.mention} ({member.id})")
                except discord.HTTPException as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
                except discord.Forbidden as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
            muted = ""
            notmuted = ""
            if success_list and not failed_list:
                muted += "**I've successfully voice muted {0} member(s):**\n".format(total)
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted)
            if success_list and failed_list:
                muted += "**I've successfully voice muted {0} member(s):**\n".format(total - failed)
                notmuted += f"**However I failed to voice mute the following {failed} member(s):**\n"
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted + notmuted)
            if not success_list and failed_list:  
                notmuted += f"**I failed to voice mute all the members:**\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(notmuted)
                    
        except Exception as e:
            print(e)
            return await ctx.send(f"{emotes.warning} Something failed! Error: (Please report it to my developers):\n- {e}")


    @commands.command(brief="Voice unmute someone in the server", aliases=["vunmute"])
    @commands.guild_only()
    @commands.has_guild_permissions(mute_members=True)
    @commands.bot_has_guild_permissions(mute_members=True)
    async def voiceunmute(self, ctx, members: commands.Greedy[discord.Member], reason: str=None):
        """ Voice unmute member in the server """

        if not members:
            return await ctx.send(f"{emotes.red_mark} | You're missing an argument - **members**")
            
        error = '\n'
        try:
            total = len(members)
            if total > 10:
                return await ctx.send("You can voice unmute only 10 members at once!") 

            failed = 0
            failed_list = []
            success_list = []
            for member in members:
                if member == ctx.author:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - you are the member?")
                    continue
                if member.top_role.position >= ctx.author.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above you in role hierarchy or has the same role.")
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    failed += 1
                    failed_list.append(f"{member.mention} ({member.id}) - member is above me in role hierarchy or has the same role.")
                    continue
                try:
                    await member.edit(mute=False, reason=responsible(ctx.author, reason))
                    success_list.append(f"{member.mention} ({member.id})")
                except discord.HTTPException as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
                except discord.Forbidden as e:
                    print(e)
                    failed += 1
                    failed_list.append(f"{member.mention} - {e}")
            muted = ""
            notmuted = ""
            if success_list and not failed_list:
                muted += "**I've successfully voice unmuted {0} member(s):**\n".format(total)
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted)
            if success_list and failed_list:
                muted += "**I've successfully voice unmuted {0} member(s):**\n".format(total - failed)
                notmuted += f"**However I failed to voice unmute the following {failed} member(s):**\n"
                for num, res in enumerate(success_list, start=0):
                    muted += f"`[{num+1}]` {res}\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(muted + notmuted)
            if not success_list and failed_list:  
                notmuted += f"**I failed to voice unmute all the members:**\n"
                for num, res in enumerate(failed_list, start=0):
                    notmuted += f"`[{num+1}]` {res}\n"
                await ctx.send(notmuted)
                    
        except Exception as e:
            print(e)
            return await ctx.send(f"{emotes.warning} Something failed! Error: (Please report it to my developers):\n- {e}")
    
    @commands.command(brief="Get a list of newest users")
    @commands.guild_only()
    async def newusers(self, ctx, *, count: int):
        """
        See the newest members in the server.
        Limit is set to `10`
        """
        if len(ctx.guild.members) < count:
            return await ctx.send(f"This server has only {len(ctx.guild.members)} members")
        counts = max(min(count, 10), 1)

        if not ctx.guild.chunked:
            await self.bot.request_offline_members(ctx.guild)
        members = sorted(ctx.guild.members, key=lambda m: m.joined_at, reverse=True)[:counts]
        e = discord.Embed(title='Newest member(s) in this server', colour=self.color['embed_color'])
        for member in members:
            data = f'**Joined Server at** {btime.human_timedelta(member.joined_at)}\n**Account created at** {btime.human_timedelta(member.created_at)}'
            e.add_field(name=f'**{member}** ({member.id})', value=data, inline=False)
            if count > 10:
                e.set_footer(text="Limit is set to 10")

        await ctx.send(embed=e)

    @commands.command(brief="Hoist a role for an announcement", aliases=['ar'])
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def announcerole(self, ctx, *, role: discord.Role):
        """ Make a role mentionable you want to mention in announcements.
        
        The role will become unmentionable after you mention it or you don't mention it for 30seconds. """
        if role == ctx.guild.default_role:
            return await ctx.send("To prevent abuse, I won't allow mentionable role for everyone/here role.")

        if ctx.author.top_role.position <= role.position:
            return await ctx.send("It seems like the role you attempt to mention is over your permissions, therefor I won't allow you.")

        if ctx.me.top_role.position <= role.position:
            return await ctx.send("This role is above my permissions, I can't make it mentionable ;-;")

        if role.mentionable == True:
            return await ctx.send(f"{emotes.red_mark} That role is already mentionable!")

        await role.edit(mentionable=True, reason=f"announcerole command")
        msg = await ctx.send(f"**{role.mention}** is now mentionable, if you don't mention it within 30 seconds, I will revert the changes.")

        while True:
            def role_checker(m):
                if (role.mention in m.content):
                    return True
                return False

            try:
                checker = await self.bot.wait_for('message', timeout=30.0, check=role_checker)
                if checker.author.id == ctx.author.id:
                    await role.edit(mentionable=False, reason=f"announcerole command")
                    return await msg.edit(content=f"**{role.mention}** mentioned by **{ctx.author}** in {checker.channel.mention}", allowed_mentions=discord.AllowedMentions(roles=False))
                    break
                else:
                    await checker.delete()
            except asyncio.TimeoutError:
                await role.edit(mentionable=False, reason=f"announcerole command")
                return await msg.edit(content=f"**{role.mention}** was never mentioned by **{ctx.author}**...", allowed_mentions=discord.AllowedMentions(roles=False))
                break
    
    @commands.command(brief="Get all the member warnings", aliases=['warns'])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def warnings(self, ctx, member: discord.Member = None):
        """ Check all guild warns or all member warnings """

        if member is None:
            warns_check = await self.bot.db.fetchval("SELECT * FROM warnings WHERE guild_id = $1", ctx.guild.id)
            
            if warns_check is None:
                return await ctx.send(f"There are no warnings in this guild.")
                
            if warns_check is not None:
                user = []
                for user_id, reason, id, time in await self.bot.db.fetch("SELECT user_id, reason, id, time FROM warnings WHERE guild_id = $1", ctx.guild.id):
                    user.append(f'**User:** {ctx.guild.get_member(user_id)}\n' + '**ID:** ' + str(id) + "\n" + '**Reason:** ' + reason + "\n**Warned:** " + str(date(time)) + "\n**────────────────────────**")
                
                members = []
                for reason in user:
                    members.append(f"{reason}\n")
                    
                paginator = Pages(ctx,
                          title=f"Guild warnings",
                          entries=members,
                          thumbnail=None,
                          per_page = 5,
                          embed_color=ctx.bot.embed_color,
                          show_entry_count=True,
                          author=ctx.author)
                await paginator.paginate()
        

        if member is not None:
            warns_check = await self.bot.db.fetchval("SELECT * FROM warnings WHERE guild_id = $1 AND user_id = $2", ctx.guild.id, member.id)
            
            if warns_check is None:
                return await ctx.send(f"**{member}** has no warnings.")
                
            if warns_check is not None:
                user = []
                for reason, id, mod, time in await self.bot.db.fetch("SELECT reason, id, mod_id, time FROM warnings WHERE guild_id = $1 AND user_id = $2", ctx.guild.id, member.id):
                    mod = ctx.guild.get_member(mod)

                    if mod is not None:
                        mod = mod
                    elif mod is None:
                        mod = 'Unable to track'
                    user.append('**ID:** ' + str(id) + "\n" + '**Reason:** ' + reason + "\n**Warned:** " + str(date(time)) + "\n**Warned by:** " + str(mod) + "\n**────────────────────────**")
                
                members = []
                for reason in user:
                    members.append(f"{reason}\n")
                    
                paginator = Pages(ctx,
                          title=f"{member}'s warnings",
                          entries=members,
                          thumbnail=None,
                          per_page = 5,
                          embed_color=self.color['embed_color'],
                          show_entry_count=True,
                          author=ctx.author)
                await paginator.paginate()

    @commands.command(brief="Warn a member")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str = None):
        """ Warn a member for something
        Time will be logged in UTC """

        if reason is None:
            reason = "No reason."
        else:
            reason = reason
        
        if member == ctx.author:
            return await ctx.send("Ok you're warned, dummy...")
        if member.top_role.position >= ctx.author.top_role.position and ctx.author != ctx.guild.owner:
            return await ctx.send("You can't warn someone who's higher or equal to you!")

        random_id = random.randint(1111, 99999)
        
        await self.bot.db.execute("INSERT INTO warnings(user_id, guild_id, id, reason, time, mod_id) VALUES ($1, $2, $3, $4, $5, $6)", member.id, ctx.guild.id, random_id, reason, datetime.utcnow(), ctx.author.id)

        e = discord.Embed(color=self.color['embed_color'], description=f"Successfully warned **{member}** for: **{reason}** with ID: **{random_id}**", delete_after=15)

        await ctx.send(embed=e)

    @commands.command(brief="Remove warning from a member", aliases=['unwarn'])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def removewarn(self, ctx, member: discord.Member, warnid):
        """ Remove warn from member's history """

        if member is ctx.author:
            return await ctx.send("Ok your warn was removed, dummy...")
        if member.top_role.position >= ctx.author.top_role.position and ctx.author != ctx.guild.owner:
            return await ctx.send("You can't remove warns from someone who's higher or equal to you!")

        check_id = await self.bot.db.fetchval('SELECT * FROM warnings WHERE guild_id = $1 AND id = $2', ctx.guild.id, int(warnid))

        if check_id is None:
            await ctx.send(f"Warn with ID: **{warnid}** was not found.")

        if check_id is not None:
            warnings = await self.bot.db.fetchval('SELECT * FROM warnings WHERE user_id = $1 AND id = $2', member.id, int(warnid))
            if warnings is not None:
                await self.bot.db.execute("DELETE FROM warnings WHERE id = $1 AND user_id = $2", int(warnid), member.id)
                await ctx.send(f"Removed warn from **{member}** with id: **{int(warnid)}**")
            if warnings is None:
                return await ctx.send(f"Warn with ID: **{int(warnid)}** was not found.")
    
    @commands.command(brief="Remove all the warnings from a member", aliases=['unwarnall'])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(use_external_emojis=True)
    async def removewarns(self, ctx, member: discord.Member):
        """ Remove all member's warns """

        try:
            if member is ctx.author:
                return await ctx.send("Ok your warns were removed, dummy...")
            if member.top_role.position >= ctx.author.top_role.position and ctx.author != ctx.guild.owner:
                return await ctx.send("You can't remove warns from someone who's higher or equal to you!")

            def check(r, u):
                return u.id == ctx.author.id and r.message.id == checkmsg.id
            sel = await self.bot.db.fetch("SELECT * FROM warnings WHERE user_id = $1 AND guild_id = $2", member.id, ctx.guild.id)

            if len(sel) == 0:
                return await ctx.send(f"**{member}** has no warnings.")
            checkmsg = await ctx.send(f"Are you sure you want to remove all **{len(sel)}** warns from the **{member}**?")
            await checkmsg.add_reaction(f'{emotes.white_mark}')
            await checkmsg.add_reaction(f'{emotes.red_mark}')
            react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30)

            if str(react) == f"{emotes.white_mark}":
                await checkmsg.delete()
                await self.bot.db.execute("DELETE FROM warnings WHERE user_id = $1 AND guild_id = $2", member.id, ctx.guild.id)
                await ctx.send(f"Removed **{len(sel)}** warnings from: **{member}**", delete_after=15)
            
            if str(react) == f"{emotes.red_mark}":
                await checkmsg.delete()
                return await ctx.send("Not removing any warns.", delete_after=15)

        except asyncio.TimeoutError:
            await checkmsg.clear_reactions()
            return await checkmsg.edit(content=f"Timing out...", delete_after=15)
        except Exception as e:
            print(e)
            await ctx.send("Looks like something wrong happened.")

    @commands.command(brief='Lock a text channel')
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 300, commands.BucketType.guild)
    async def lockchannel(self, ctx, channel: typing.Optional[discord.TextChannel] = None, *, reason: str = None):
        """ Lock any text channels from everyone being able to chat """
        
        if reason is None:
            reason = "No reason"
        
        channel = channel or ctx.channel

        if channel.overwrites_for(ctx.guild.default_role).send_messages == False:
            return await ctx.send(f"{emotes.red_mark} {channel.mention} is already locked!", delete_after=20)
        else:
            try:
                await channel.set_permissions(ctx.guild.default_role, send_messages=False, reason=responsible(ctx.author, reason))
                await channel.send(f"{emotes.locked} This channel was locked for: `{reason}`")
                await ctx.send(f"{emotes.white_mark} {channel.mention} was locked!", delete_after=20)
            except Exception as e:
                print(default.traceback_maker(e))
                await ctx.send(f"Error! ```py\n{e}```")

    @commands.command(brief='Unlock a text channel')
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 300, commands.BucketType.guild)
    async def unlockchannel(self, ctx, channel: typing.Optional[discord.TextChannel] = None, *, reason: str = None):
        """ Unlock text channel to everyone 
        This will sync permissions with category """

        if reason is None:
            reason = "No reason"
        
        channel = channel or ctx.channel

        if channel.overwrites_for(ctx.guild.default_role).send_messages is None:
            return await ctx.send(f"{emotes.red_mark} {channel.mention} is not locked!", delete_after=20)
        elif channel.overwrites_for(ctx.guild.default_role).send_messages == False:
            try:
                await channel.set_permissions(ctx.guild.default_role, overwrite=None, reason=responsible(ctx.author, reason))
                await channel.send(f"{emotes.unlocked} This channel was unlocked for: `{reason}`")
                await ctx.send(f"{emotes.white_mark} {channel.mention} was unlocked!", delete_after=20)
            except Exception as e:
                print(default.traceback_maker(e))
                await ctx.send(f"Error! ```py\n{e}```")

    # @commands.command(brief='Lockdown the server', hidden=True)
    # @commands.guild_only()
    # @commands.is_owner()
    # @commands.cooldown(1, 300, commands.BucketType.guild)
    # @commands.has_permissions(manage_roles=True)
    # @commands.bot_has_permissions(manage_roles=True)
    # async def lockdown(self, ctx, *, reason: commands.clean_content):
    #     """ Will lock all the channels in the server """

    #     lock = 0
    #     for channel in ctx.guild.channels:
    #         if channel.overwrites_for(ctx.guild.default_role).read_messages == False:
    #             await self.bot.db.execute("INSERT INTO lockdown(guild_id, channel_id) values ($1, $2)", ctx.guild.id, channel.id)
    #             continue
    #         if channel.overwrites_for(ctx.guild.default_role).send_messages == False:
    #             if not await self.bot.db.fetchval("SELECT * FROM lockdown WHERE channel_id = $1 AND guild_id = $2", channel.id, ctx.guild.id):
    #                 await self.bot.db.execute("INSERT INTO lockdown(guild_id, channel_id) values ($1, $2)", ctx.guild.id, channel.id)
    #             continue
    #         if isinstance(channel, discord.CategoryChannel):
    #             continue
    #         try:
    #             await channel.set_permissions(ctx.guild.me, send_messages=True, reason=responsible(ctx.author, reason))
    #             await channel.set_permissions(ctx.guild.default_role, send_messages=False, connect=False, reason=responsible(ctx.author, reason))
    #             if isinstance(channel, discord.TextChannel):
    #                 await channel.send(f"{emotes.locked} **Channel locked for:** {reason}")
    #             lock += 1
    #         except Exception as e:
    #             print(e)
    #             pass
        
    #     await ctx.send(f"{emotes.white_mark} Locked {lock} channels")
    
    # @commands.command(brief='Unlockdown the server', hidden=True)
    # @commands.guild_only()
    # @commands.is_owner()
    # @commands.cooldown(1, 300, commands.BucketType.guild)
    # @commands.has_permissions(manage_roles=True)
    # @commands.bot_has_permissions(manage_roles=True)
    # async def unlockdown(self, ctx, *, reason: commands.clean_content):
    #     """ Unlock all the channels that were previously locked using a lockdown. """

    #     check = await self.bot.db.fetchval("SELECT * FROM lockdown WHERE guild_id = $1", ctx.guild.id)
    #     if check is None:
    #         try:
    #             def check(r, u):
    #                 return u.id == ctx.author.id and r.message.id == checkmsg.id

    #             channels = 0
    #             for channel in ctx.guild.channels:
    #                 if isinstance(channel, discord.CategoryChannel):
    #                     continue
    #                 channels += 1
                
    #             checkmsg = await ctx.send(f"No results of previously locked channels using `lockdown` were found are you sure you want to unlock all **{channels}** channels in this server?")
    #             await checkmsg.add_reaction(f'{emotes.white_mark}')
    #             await checkmsg.add_reaction(f'{emotes.red_mark}')
    #             react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30.0)

    #             if str(react) == f"{emotes.white_mark}":
    #                 await checkmsg.edit(content=f"{emotes.loading1} Started unlocking process")
    #                 unlocked = 0
    #                 for channel in ctx.guild.channels:
    #                     if isinstance(channel, discord.CategoryChannel):
    #                         continue
    #                     try:
    #                         await channel.set_permissions(ctx.guild.default_role, overwrite=None, reason=responsible(ctx.author, reason))
    #                         await channel.send(f"{emotes.unlocked} **Channel unlocked for:** {reason}")
    #                         unlocked += 1
    #                     except Exception as e:
    #                         print(e)
    #                         pass
    #                 return await ctx.send(f"{emotes.white_mark} Unlocked {unlocked} channels.", delete_after=15)

    #             elif str(react) == f"{emotes.red_mark}":
    #                 await checkmsg.edit(content=f"Ok. Not unlocking any channels", delete_after=15)
    #                 try:
    #                     return await checkmsg.clear_reactions()
    #                 except:
    #                     return
    #         except asyncio.TimeoutError:
    #             await checkmsg.edit(content=f"{emotes.warning} Timeout!")
    #             try:
    #                 return await checkmsg.clear_reactions()
    #             except:
    #                 return

    #     unlocked = 0
    #     for channel in ctx.guild.channels:
    #         if channel.overwrites_for(ctx.guild.default_role).read_messages == False:
    #             continue      
    #         if await self.bot.db.fetchval("SELECT channel_id FROM lockdown WHERE guild_id = $1 and channel_id = $2", ctx.guild.id, channel.id):
    #             continue
    #         if isinstance(channel, discord.CategoryChannel):
    #             continue
    #         try:
    #             await channel.set_permissions(ctx.guild.default_role, read_messages = True, send_messages=True, connect=True, reason=responsible(ctx.author, reason))
    #             if isinstance(channel, discord.TextChannel):
    #                 await channel.send(f"{emotes.unlocked} **Channel unlocked for:** {reason}")
    #             unlocked += 1
    #         except Exception as e:
    #             print(e)
    #             pass

    #     await ctx.send(f"{emotes.white_mark} Unlocked {unlocked} channels")
    #     await self.bot.db.execute("DELETE FROM lockdown WHERE guild_id = $1", ctx.guild.id)
        
            
    
def setup(bot):
    bot.add_cog(moderation(bot))
