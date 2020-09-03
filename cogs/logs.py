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
import datetime
import re
import traceback
import json
import asyncio
from discord.ext import commands
from utils import default
from datetime import datetime
from db import emotes
from utils.default import color_picker
from utils.caches import CacheManager as cm

CAPS = re.compile(r"[ABCDEFGHIJKLMNOPQRSTUVWXYZ]")
LINKS = re.compile(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")
INVITE = re.compile(r"(?:https?://)?discord(?:app\.com/invite|\.gg)/?[a-zA-Z0-9]+/?")


class logs(commands.Cog, name="Logs", command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        self.bot = bot
        self._last_result = None
        self.color = color_picker('colors')

    async def get_audit_logs(self, guild, limit=100, user=None, action=None):
        return await self.bot.get_guild(guild.id).audit_logs(limit=limit, user=user, action=action).flatten()

    def cog_check(self, ctx):
        if ctx.guild is None:
            return False
        return True

    async def update_query(self, guildid=None, case=None):
        check = await self.bot.db.fetchval("SELECT * FROM modlog WHERE guild_id = $1", guildid)

        if check is None:
            await self.bot.db.execute("INSERT INTO modlog(guild_id, case_num) VALUES($1, $2)", guildid, case)
        elif check is not None:
            cs = case + 1
            await self.bot.db.execute("UPDATE modlog SET case_num = $1 WHERE guild_id = $2", cs, guildid)
    
    async def event_error(self, error=None, event=None, guild=None):
        channel = self.bot.get_guild(671078170874740756).get_channel(703627099180630068)
        tb = traceback.format_exception(type(error), error, error.__traceback__) 
        tbe = "".join(tb) + ""

        if len(tbe) < 2048:
            tbe = tbe
        elif len(tbe) > 2048:
            tbe = error

        e = discord.Embed(color=self.color['logembed_color'], title=f"{emotes.error} Error occured on event {event}")
        e.description = f"```py\n{tbe}```"
        e.add_field(name='Guild:', value=f"{guild} ({guild.id})")
        await channel.send(embed=e)
    
    def placeholder_replacer(self, emb_dict, member):
        for thing in emb_dict:
            if isinstance(emb_dict[thing], str):
                emb_dict[thing] = emb_dict[thing].replace("{{member.name}}", member.name)
                emb_dict[thing] = emb_dict[thing].replace("{{member.mention}}", member.mention)
                emb_dict[thing] = emb_dict[thing].replace("{{server.name}}", member.guild.name)
                emb_dict[thing] = emb_dict[thing].replace("{{server.members}}", str(member.guild.member_count))
        return emb_dict

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):

        if before.guild is None:
            return
        
        if before.author.bot:
            return

        db_check = cm.get_cache(self.bot, before.guild.id, 'msgedit')

        if db_check is None:
            return

        if before.content == after.content:
            return

        embed = discord.Embed(color=self.color['logging_color'],
                              description=f"{emotes.log_msgedit} Message edited! [Jump to message]({before.jump_url})",
                              timestamp=datetime.utcnow())
        embed.set_author(icon_url=before.author.avatar_url, name=before.author)
        embed.add_field(name="From:", value=f"{before.content}", inline=True)
        embed.add_field(name="To:", value=f"{after.content}", inline=False)
        embed.add_field(name="Channel:",
                         value=f"{before.channel.mention}", inline=True)

        lchannel = before.guild.get_channel(db_check)
        try:
            await lchannel.send(embed=embed)
        except Exception as e:
            await self.event_error(error=e, event='on_message_edit',guild=before.guild)
            return

# ~ End


    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return
        
        if message.guild is None:
            return
        
        db_check = cm.get_cache(self.bot, message.guild.id, 'msgdelete')

        if db_check is None:
            return

        channel = message.guild.get_channel(db_check)

        embed = discord.Embed(
            color=self.color['logging_color'], description=f"{emotes.log_msgdelete} Message deleted!", timestamp=datetime.utcnow())
        embed.set_author(icon_url=message.author.avatar_url, name=message.author)

        if message.attachments:
                attachment_url = message.attachments[0].url
                embed.add_field(name="Message:", value=attachment_url, inline=False)
        else:
            embed.add_field(name="Message:", value=message.content, inline=False)
        embed.add_field(name="Channel:",
                        value=message.channel.mention)
        embed.set_footer(text=f"ID: {message.id}")

        try:
            await channel.send(embed=embed)
        except Exception as e:
            await self.event_error(error=e, event='on_message_delete', guild=message.guild)
            return

    @commands.Cog.listener()
    async def on_member_join(self, member):
        #print(f'{member} has joined a server ({member.guild}).')

        # ! Join role (Role on join)
        db_check1 = cm.get_cache(self.bot, member.guild.id, 'joinrole')
        # ! Join log (Member join log)
        db_check2 = cm.get_cache(self.bot, member.guild.id, 'joinlog')
        # ! Join message (Welcome msg)
        db_check3 = cm.get_cache(self.bot, member.guild.id, 'joinmsg')
        # ! Temp mute
        temp_mute = await self.bot.db.fetchval("SELECT user_id FROM moddata WHERE user_id = $1 AND guild_id = $2", member.id, member.guild.id)

        badges = cm.get_cache(self.bot, f"{member.id}", 'user_badges')   

        if db_check1 is not None:
            if member.guild.me.guild_permissions.manage_roles:
                # Role on join
                if member.bot and db_check1['bots'] is not None:
                    role = member.guild.get_role(db_check1['bots'])

                    try:
                        await member.add_roles(role, reason='Autorole')
                    except Exception as e:
                        await self.event_error(error=e, event='on_member_join (bot role)', guild=member.guild)
                        pass
                elif not member.bot and db_check1['people'] is not None:
                    role = member.guild.get_role(db_check1['people'])
                    try:
                        await member.add_roles(role, reason='Autorole')
                    except Exception as e:
                        await self.event_error(error=e, event='on_member_join (people role)', guild=member.guild)
                        pass
                if temp_mute:
                    muterole = discord.utils.find(lambda r: r.name.lower() == "muted", member.guild.roles)
                    if muterole:
                        try:
                            await member.add_roles(muterole, reason='User was muted before')
                        except Exception as e:
                            await self.event_error(error=e, event='on_member_join (anti evading mute)', guild=member.guild)
                            pass
                    else:
                        pass
        if db_check2 is not None:
            # Member join log
            logchannel = self.bot.get_channel(db_check2)
            embed = discord.Embed(
                color=self.color['logging_color'], description=f"{emotes.log_memberjoin} New member joined", timestamp=datetime.utcnow())
            #embed.set_author(icon_url=member.avatar_url)
            embed.add_field(name="Username:", value=member, inline=True)
            embed.add_field(name="User ID:", value=member.id, inline=True)
            embed.add_field(name="Created at:", value=default.date(
                member.created_at), inline=False)
            embed.set_thumbnail(url=member.avatar_url)
            if member.guild.id == 671078170874740756 and badges:
                embed.add_field(name='User badges', value=', '.join(badges), inline=False)
            try:
                await logchannel.send(embed=embed)
            except Exception as e:
                await self.event_error(error=e, event='on_member_join (welcome log message)', guild=member.guild)
                pass
        
        if db_check3 is not None:
            if member.bot and db_check3['bot_joins'] == False:
                return
            elif member.bot and db_check3['bot_joins'] == True:
                pass
            elif db_check3['bot_joins'] is None:
                pass
            if db_check3['message'] and not db_check3['embed']:
                joinmessage = str(db_check3['message'])
                joinmessage = joinmessage.replace("{{member.mention}}", member.mention)
                joinmessage = joinmessage.replace("{{member.name}}", discord.utils.escape_markdown(member.name, as_needed=True))
                joinmessage = joinmessage.replace("{{server.name}}", member.guild.name)
                joinmessage = joinmessage.replace("{{server.members}}", str(member.guild.member_count))
            elif db_check3['message'] is None and not db_check3['embed']:
                joinmessage = f"{emotes.joined} {member.mention} joined the server! There are {member.guild.member_count} members in the server now."

            elif db_check3['message'] and db_check3['embed'] == True:
                msg = json.loads(db_check3['message'])
                emb_dict = msg
                emb_dict = self.placeholder_replacer(emb_dict, member)
                if "author" in emb_dict:
                    emb_dict["author"] = self.placeholder_replacer(emb_dict["author"], member)
                if "footer" in emb_dict:
                    emb_dict["footer"] = self.placeholder_replacer(emb_dict["footer"], member)
                if "fields" in emb_dict:
                    for field in emb_dict["fields"]:
                        emb_dict["fields"] = self.placeholder_replacer(field["name"], member)
                        emb_dict["fields"] = self.placeholder_replacer(field["value"], member)
            elif db_check3['message'] is None and db_check3['embed'] == True:
                emb_dict = {
                    "plainText": "{{member.mention}}",
                    "title": "Welcome to {{server.name}}",
                    "description": "You are member #{{server.members}} in this server!",
                    "color": 6215030
                    }
                emb_dict = self.placeholder_replacer(emb_dict, member)
                if "author" in emb_dict:
                    emb_dict["author"] = self.placeholder_replacer(emb_dict["author"], member)
                if "footer" in emb_dict:
                    emb_dict["footer"] = self.placeholder_replacer(emb_dict["footer"], member)
                if "fields" in emb_dict:
                    for field in emb_dict["fields"]:
                        emb_dict["fields"] = self.placeholder_replacer(field["name"], member)
                        emb_dict["fields"] = self.placeholder_replacer(field["value"], member) 
            # Welcome msg
            welcomechannel = self.bot.get_channel(db_check3['channel'])
            try:
                if db_check3['embed']:
                    try:
                        await welcomechannel.send(content=emb_dict['plainText'], embed=discord.Embed.from_dict(emb_dict), allowed_mentions=discord.AllowedMentions(users=True))
                    except:
                        await welcomechannel.send(embed=discord.Embed.from_dict(emb_dict), allowed_mentions=discord.AllowedMentions(users=True))
                else:
                    await welcomechannel.send(joinmessage, allowed_mentions=discord.AllowedMentions(users=True))
            except Exception as e:
                await self.event_error(error=e, event='on_member_join (welcome message)', guild=member.guild)
                pass

##############################
    @commands.Cog.listener()
    async def on_member_remove(self, member):

        await self.bot.db.execute("DELETE FROM warnings WHERE user_id = $1 AND guild_id = $2", member.id, member.guild.id)
        await self.bot.db.execute("DELETE FROM autowarns WHERE user_id = $1 AND guild_id = $2", member.id, member.guild.id)
        await self.bot.db.execute("DELETE FROM useractivity WHERE user_id = $1", member.id)

        db_check1 = cm.get_cache(self.bot, member.guild.id, 'leavemsg')
        db_check2 = cm.get_cache(self.bot, member.guild.id, 'joinlog')
        

        moderation = cm.get_cache(self.bot, member.guild.id, 'moderation')
        case = cm.get_cache(self.bot, member.guild.id, 'case_num')

        if member == self.bot.user:
            return

        if member.guild.me.guild_permissions.view_audit_log:
            checks = await self.get_audit_logs(member.guild, limit=1, action=discord.AuditLogAction.kick)  

        if db_check2 is not None:
            # Member leave log
            logchannel = self.bot.get_channel(db_check2)
            embed = discord.Embed(
                color=self.color['logging_color'], description=f"{emotes.log_memberleave} Member left", timestamp=datetime.utcnow())
            #embed.set_author(icon_url=member.avatar_url)
            embed.add_field(name="Username:", value=f"{member} ({member.id})", inline=True)
            embed.add_field(name="Created at:", value=default.date(
                member.created_at), inline=False)
            embed.add_field(name="Joined at:", value=default.date(member.joined_at), inline=False)
            embed.set_thumbnail(url=member.avatar_url)
            try:
                await logchannel.send(embed=embed)
            except Exception as e:
                await self.event_error(error=e, event='on_member_remove (leave log message)', guild=member.guild)
                pass

        if moderation is not None:
            try:
                deleted = ""
                reason = ""
                async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
                    if entry.target == member:
                        deleted += f"{entry.user} ({entry.user.id})"
                        reason += f"{entry.reason}"
                    #print(entry)
            except Exception as e:
                print(e)
                pass
            logchannel = self.bot.get_channel(moderation)
            if deleted and (datetime.utcnow() - checks[0].created_at).total_seconds() < 5:

                casenum = cm.get_cache(self.bot, member.guild.id, 'case_num') or 1
                embed = discord.Embed(
                    color=self.color['logging_color'], description=f"{emotes.log_memberleave} Member kicked `[#{casenum}]`", timestamp=datetime.utcnow())
                #embed.set_author(icon_url=member.avatar_url)
                embed.add_field(name="Username:", value=f"{member} ({member.id})", inline=False)
                embed.add_field(name="Created at:", value=default.date(
                    member.created_at), inline=False)
                embed.add_field(name="Joined at:", value=default.date(member.joined_at), inline=False)
                if deleted:
                    embed.add_field(name='Moderator:', value=deleted, inline=False)
                if reason:
                    embed.add_field(name="Reason:", value=reason, inline=False)
                embed.set_thumbnail(url=member.avatar_url)
                await self.update_query(guildid=member.guild.id, case=casenum)
                self.bot.case_num[member.guild.id] += 1
                try:
                    await logchannel.send(embed=embed)
                except Exception as e:
                    await self.event_error(error=e, event='on_member_remove (kick message)', guild=member.guild)
                    pass

            elif deleted and (datetime.utcnow() - checks[0].created_at).total_seconds() > 5:
                pass
            
        if db_check1 is not None:
            if member.bot and db_check1['bot_joins'] == False:
                return
            elif member.bot and db_check1['bot_joins'] == True:
                pass
            elif db_check1['bot_joins'] is None:
                pass
            if db_check1['message'] and not db_check1['embed']:
                leavemessage = str(db_check1['message'])
                leavemessage = leavemessage.replace("{{member.mention}}", member.mention)
                leavemessage = leavemessage.replace("{{member.name}}", discord.utils.escape_markdown(member.name, as_needed=True))
                leavemessage = leavemessage.replace("{{server.name}}", member.guild.name)
                leavemessage = leavemessage.replace("{{server.members}}", str(member.guild.member_count))
            elif db_check1['message'] is None and not db_check1['embed']:
                leavemessage = f"{emotes.left} {member.mention} left the server... There are {member.guild.member_count} members left in the server."
            elif db_check1['message'] and db_check1['embed'] == True:
                msg = json.loads(db_check1['message'])
                emb_dict = msg
                emb_dict = self.placeholder_replacer(emb_dict, member)
                if "author" in emb_dict:
                    emb_dict["author"] = self.placeholder_replacer(emb_dict["author"], member)
                if "footer" in emb_dict:
                    emb_dict["footer"] = self.placeholder_replacer(emb_dict["footer"], member)
                if "fields" in emb_dict:
                    for field in emb_dict["fields"]:
                        emb_dict["fields"] = self.placeholder_replacer(field["name"], member)
                        emb_dict["fields"] = self.placeholder_replacer(field["value"], member)
            elif db_check1['message'] is None and db_check1['embed'] == True:
                emb_dict = {
                    "description": "{{member.name}} left the server! There are now {{server.members}} members left!",
                    "color": 13579316
                    }
                emb_dict = self.placeholder_replacer(emb_dict, member)
                if "author" in emb_dict:
                    emb_dict["author"] = self.placeholder_replacer(emb_dict["author"], member)
                if "footer" in emb_dict:
                    emb_dict["footer"] = self.placeholder_replacer(emb_dict["footer"], member)
                if "fields" in emb_dict:
                    for field in emb_dict["fields"]:
                        emb_dict["fields"] = self.placeholder_replacer(field["name"], member)
                        emb_dict["fields"] = self.placeholder_replacer(field["value"], member) 
            leavechannel = self.bot.get_channel(db_check1['channel'])
            try:
                if db_check1['embed']:
                    try:
                        await leavechannel.send(content=emb_dict['plainText'], embed=discord.Embed.from_dict(emb_dict), allowed_mentions=discord.AllowedMentions(users=True))
                    except:
                        await leavechannel.send(embed=discord.Embed.from_dict(emb_dict), allowed_mentions=discord.AllowedMentions(users=True))
                else:
                    await leavechannel.send(leavemessage, allowed_mentions=discord.AllowedMentions(users=True))
            except Exception as e:
                await self.event_error(error=e, event='on_member_remove (leave message)', guild=member.guild)
                return


    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.bot:
            return

        db_check1 = cm.get_cache(self.bot, before.guild.id, 'memberupdate')

        if db_check1 is None:
            return
        
        if before.nick is None:
            nick = before.name
        elif before.nick:
            nick = before.nick
        if after.nick is None:
            nicks = after.name
        elif after.nick:
            nicks = after.nick

        channel = self.bot.get_channel(db_check1)

        if before.nick != after.nick:
            try:
                deleted = ""
                async for entry in before.guild.audit_logs(action=discord.AuditLogAction.member_update, limit=1):
                    deleted += f"{entry.user} ({entry.user.id})"
            except Exception as e:
                print(e)
                deleted = "Fail"
            e = discord.Embed(
                color=self.color['logging_color'],description=f"{emotes.log_memberedit} Nickname changed", timestamp=datetime.utcnow())
            e.set_author(name="Nickname changed", icon_url=before.avatar_url)
            e.add_field(name="User:", value=f"{after.name}\n({after.id})")
            e.add_field(name="Nickname:",
                        value=f"{nick} → {nicks}")
            if deleted:
                e.add_field(name="Changed by:", value=deleted, inline=False)
            e.set_thumbnail(url=after.avatar_url)
            e.set_footer(text=f'User ID: {after.id}')
            try:
                await channel.send(embed=e)
            except Exception as e:
                await self.event_error(error=e, event='on_member_update', guild=before.guild)
                return

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        # Don't listen to bots
        if before.bot:
            return

        
        for guild in self.bot.guilds:
            if before in guild.members:
                db_check1 = cm.get_cache(self.bot, guild.id, 'memberupdate')
                
                if db_check1 is None:
                    return
                    
                channel = self.bot.get_channel(db_check1)

                # Avatar changed
                if before.avatar != after.avatar:
                    e = discord.Embed(color=self.color['logging_color'],
                                              title=f"{emotes.log_memberedit} Avatar updated",
                                              timestamp=datetime.utcnow())
                    #e.set_author(name=after, icon_url=after.avatar_url)
                    e.description = f"**{after.name}** has changed his avatar"
                    e.set_thumbnail(url=after.avatar_url)
                    #e.set_image(url=before.avatar_url)
                    e.set_footer(text=f"User ID: {after.id}")
                    try:
                        await channel.send(embed=e)
                    except Exception as e:
                        await self.event_error(error=e, event='on_user_update (avatar)', guild=before.guild)
                        return
                            
                # Username changed
                if before.name != after.name:
                    e = discord.Embed(color=self.color['logging_color'], title=f"{emotes.log_memberedit} Username updated", description=f"**{before.name}** changed his username to **{after.name}**", timestamp=datetime.utcnow())
                    #e.set_author(name=after, icon_url=after.avatar_url)
                    e.set_footer(text=f"User ID: {after.id}")
                    try:
                        await channel.send(embed=e)
                    except Exception as e:
                        await self.event_error(error=e, event='on_user_update (name)', guild=before.guild)
                        return

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):

        await asyncio.sleep(2)

        db_check1 = cm.get_cache(self.bot, guild.id, 'moderation')
        #logchannel = await self.bot.db.fetchval("SELECT channel_id FROM moderation WHERE guild_id = $1", guild.id)
        case = cm.get_cache(self.bot, guild.id, 'case_num')

        if db_check1 is not None:
            channel = self.bot.get_channel(db_check1)

        if db_check1 is None:
            return
        
        try:
            deleted = ""
            reason = ""
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=50):
                if entry.target == user:
                    if (datetime.utcnow() - entry.created_at).total_seconds() < 10:
                        deleted += f"{entry.user} ({entry.user.id})"
                        reason += f"{entry.reason}"
        except Exception as e:
            print(e)
            pass

        casenum = case or 1

        embed = discord.Embed(color=self.color['logging_color'],
                              description=f"{emotes.log_ban} Member banned! `[#{casenum}]`",
                              timestamp=datetime.utcnow())
        embed.add_field(name="Member:",
                        value=f'{user} ({user.id})', inline=False)
        embed.add_field(name="Member created at:", value=default.date(user.created_at), inline=False)
        if deleted:
            embed.add_field(name="Moderator:", value=deleted, inline=False)
        if reason:
            embed.add_field(name='Reason:', value=reason, inline=False)
        embed.set_thumbnail(url=user.avatar_url)
        await self.update_query(guildid=guild.id, case=casenum)
        self.bot.case_num[guild.id] += 1
        try:
            await channel.send(embed=embed)
        except Exception as e:
            await self.event_error(error=e, event='on_member_ban', guild=guild)
            return

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await asyncio.sleep(2)

        db_check1 = cm.get_cache(self.bot, guild.id, 'moderation')
        #logchannel = await self.bot.db.fetchval("SELECT channel_id FROM moderation WHERE guild_id = $1", guild.id)
        case = cm.get_cache(self.bot, guild.id, 'case_num')

        channel = self.bot.get_channel(db_check1)

        if db_check1 is None:
            return

        try:
            deleted = ""
            reason = ""
            async for entry in guild.audit_logs(action=discord.AuditLogAction.unban, limit=50):
                if entry.target == user:
                    if (datetime.utcnow() - entry.created_at).total_seconds() < 10:
                        deleted += f"{entry.user} ({entry.user.id})"
                        reason += f"{entry.reason}"
        except Exception as e:
            print(e)
            pass

        casenum = case or 1

        embed = discord.Embed(color=self.color['logging_color'],
                              description=f"{emotes.log_unban} Member unbanned! `[#{casenum}]`",
                              timestamp=datetime.utcnow())
        embed.add_field(name="User name",
                        value=f'{user} ({user.id})', inline=False)
        embed.add_field(name="Member created at:", value=default.date(user.created_at), inline=False)
        if deleted:
            embed.add_field(name="Moderator", value=deleted, inline=False)
        if reason:
            embed.add_field(name="Reason:", value=reason, inline=False)
        embed.set_thumbnail(url=user.avatar_url)
        await self.update_query(guildid=guild.id, case=casenum)
        self.bot.case_num[guild.id] += 1
        try:
            await channel.send(embed=embed)
        except Exception as e:
            await self.event_error(error=e, event='on_member_unban', guild=guild)
            return

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):

        db_check1 = cm.get_cache(self.bot, member.guild.id, 'moderation')
        #logchannel = await self.bot.db.fetchval("SELECT channel_id FROM moderation WHERE guild_id = $1", member.guild.id)

        case = cm.get_cache(self.bot, member.guild.id, 'case_num')

        channel = self.bot.get_channel(db_check1)

        if db_check1 is None:
            return

        try:
            deleted = ""
            async for entry in member.guild.audit_logs(action=discord.AuditLogAction.member_update, limit=1):
                deleted += f"{entry.user} ({entry.user.id})"
        except Exception as e:
            print(e)
            pass

        casenum = case or 1
        
        if before.mute != after.mute:
            if after.mute is False:
                mt = "unmuted"
            elif after.mute is True:
                mt = "muted"
            embed = discord.Embed(color=self.color['logging_color'],
                                description=f"{emotes.log_memberedit} Member was voice {mt}! `[#{casenum}]`",
                                timestamp=datetime.utcnow())
            embed.add_field(name="User:",
                            value=f'{member} ({member.id})', inline=True)
            if deleted:
                embed.add_field(name="Moderator:", value=deleted)
            embed.set_thumbnail(url=member.avatar_url)
            await self.update_query(guildid=member.guild.id, case=casenum)
            self.bot.case_num[member.guild.id] += 1
            try:
                await channel.send(embed=embed)
            except Exception as e:
                await self.event_error(error=e, event='on_voice_state_update', guild=before.guild)
                return
    
    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        db_check1 = cm.get_cache(self.bot, before.id, 'moderation')
        #logchannel = await self.bot.db.fetchval("SELECT channel_id FROM moderation WHERE guild_id = $1", before.id)

        if db_check1 is None:
            return
        
        channels = self.bot.get_channel(db_check1)
        
        if before.name != after.name:
            embed = discord.Embed(color=self.color['logging_color'],
                              description=f"{emotes.log_guildupdate} Guild name was changed!",
                              timestamp=datetime.utcnow())
            embed.add_field(name="Name:", value=f"{before.name} → {after.name}")
            try:
                await channels.send(embed=embed)
            except Exception as e:
                await self.event_error(error=e, event='on_guild_update', guild=before.guild)
                return

        
        if before.region != after.region:
            embed = discord.Embed(color=self.color['logging_color'],
                              description=f"{emotes.log_guildupdate} Guild region was changed!",
                              timestamp=datetime.utcnow())
            embed.add_field(name="Region:", value=f"{before.region} → {after.region}")

            try:
                await channels.send(embed=embed)
            except Exception as e:
                await self.event_error(error=e, event='on_guild_update', guild=before.guild)
                return
        
        if before.afk_channel != after.afk_channel:
            embed = discord.Embed(color=self.color['logging_color'],
                              description=f"{emotes.log_guildupdate} Guild afk channel was changed!",
                              timestamp=datetime.utcnow())
            embed.add_field(name="AFK Channel:", value=f"{before.afk_channel} → {after.afk_channel}")

            try:
                await channels.send(embed=embed)
            except Exception as e:
                await self.event_error(error=e, event='on_guild_update', guild=before.guild)
                return
        
        if before.icon_url != after.icon_url:
            embed = discord.Embed(color=self.color['logging_color'],
                              description=f"{emotes.log_guildupdate} Guild icon was changed!",
                              timestamp=datetime.utcnow())
            embed.add_field(name="Before:", value=f"[Old icon]({before.icon_url})")
            embed.set_thumbnail(url=after.icon_url)

            try:
                await channels.send(embed=embed)
            except Exception as e:
                await self.event_error(error=e, event='on_guild_update', guild=before.guild)
                return
        
        if before.mfa_level != after.mfa_level:
            embed = discord.Embed(color=self.color['logging_color'],
                              description=f"{emotes.log_guildupdate} Guild multifactor authentication (MFA) was changed!",
                              timestamp=datetime.utcnow())
            embed.add_field(name="MFA level:", value=f"{before.mfa_level} → {after.mfa_level}")
            
            try:
                await channels.send(embed=embed)
            except Exception as e:
                await self.event_error(error=e, event='on_guild_update', guild=before.guild)
                return
        
        if before.verification_level != after.verification_level:
            embed = discord.Embed(color=self.color['logging_color'],
                              description=f"{emotes.log_guildupdate} Guild verification level was changed!",
                              timestamp=datetime.utcnow())
            embed.add_field(name="Verfication:", value=f"{before.verification_level} → {after.verification_level}")
            

            await channels.send(embed=embed)
        
        if before.default_notifications != after.default_notifications:
            embed = discord.Embed(color=self.color['logging_color'],
                              description=f"{emotes.log_guildupdate} Guild default notifications were changed!",
                              timestamp=datetime.utcnow())
            embed.add_field(name="Notifications:", value=f"{before.default_notifications.name} → {after.default_notifications.name}")

            try:
                await channels.send(embed=embed)
            except Exception as e:
                await self.event_error(error=e, event='on_guild_update', guild=before.guild)
                return
    
    @commands.Cog.listener('on_member_join')
    async def anti_join_dehoist(self, member):
        check = cm.get_cache(self.bot, member.guild.id, 'antidehoist')

        if check is None:
            return
        
        nick = member.display_name
        chosen_nick = check['nickname']
        logchannel = check['channel']
        case = cm.get_cache(self.bot, member.guild.id, 'case_num')
        chosen_nick = chosen_nick or 'z (hoister)'
        if logchannel:
            channel = member.guild.get_channel(logchannel)
        if not nick[0].isalnum():
            await asyncio.sleep(60)
            if not nick[0].isalnum():
                try:
                    casenum = case or 1
                    await member.edit(nick=chosen_nick, reason='Anti dehoist')
                    embed = discord.Embed(
                        color=self.color['logging_color'], description=f"{emotes.log_memberedit} Member dehoisted `[#{casenum}]`", timestamp=datetime.utcnow())
                    embed.add_field(name='User:', value=f"{member} ({member.id})")
                    embed.add_field(name='Previous name:', value=nick, inline=False)
                    embed.add_field(name='New name:', value=chosen_nick, inline=False)
                    embed.set_thumbnail(url=member.avatar_url)
                    if channel:
                        try:
                            await channel.send(embed=embed)
                        except Exception as e:
                            await self.event_error(error=e, event='anti_join_dehoist', guild=member.guild)
                            return
                        await self.update_query(guildid=member.guild.id, case=casenum)
                        self.bot.case_num[member.guild.id] += 1
                except:
                    pass
    
    @commands.Cog.listener('on_member_update')
    async def anti_edit_dehoist(self, before, after):
        if before.bot:
            return

        db_check1 = cm.get_cache(self.bot, before.guild.id, 'antidehoist')

        if db_check1 is None:
            return

        channel = self.bot.get_channel(db_check1['channel'])
        chosen_nick = db_check1['nickname'] or 'z (hoister)'
        case = cm.get_cache(self.bot, before.guild.id, 'case_num')

        if before.nick != after.nick:
            name = after.display_name
            if not name[0].isalnum():
                await asyncio.sleep(60)
                if not name[0].isalnum():
                    try:
                        casenum = case or 1
                        await after.edit(nick=chosen_nick, reason='Anti dehoist')
                        embed = discord.Embed(
                            color=self.color['logging_color'], description=f"{emotes.log_memberedit} Member dehoisted `[#{casenum}]`", timestamp=datetime.utcnow())
                        embed.add_field(name='User:', value=f"{after} ({after.id})")
                        embed.add_field(name='Previous name:', value=name, inline=False)
                        embed.add_field(name='New name:', value=chosen_nick, inline=False)
                        embed.set_thumbnail(url=after.avatar_url)
                        if channel:
                            try:
                                await channel.send(embed=embed)
                            except Exception as e:
                                await self.event_error(error=e, event='anti_edit_dehoist', guild=before.guild)
                                return
                            await self.update_query(guildid=before.guild.id, case=casenum)
                            self.bot.case_num[before.guild.id] += 1
                    except Exception as e:
                        print(e)
                        pass


def setup(bot):
    bot.add_cog(logs(bot))
