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
import os
import platform
import psutil
import asyncio
import json

from discord.ext import commands
from db import emotes
from datetime import datetime
from utils.default import color_picker

class admin(commands.Cog, name="Staff"):

    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:staff:706190137058525235>"
        self.big_icon = "https://cdn.discordapp.com/emojis/706190137058525235.png?v=1"
        self._last_result = None
        self.color = color_picker('colors')

    async def cog_check(self, ctx: commands.Context):
        """
        Local check, makes all commands in this cog owner-only
        """
        if not await ctx.bot.is_admin(ctx.author):
            text = f"{emotes.bot_admin} | This command is admin-locked"
            await ctx.send(text)
            return False
        return True

    @commands.group(brief="Main commands", invoke_without_command=True)
    async def admin(self, ctx):
        """ Bot admin commands.
        Used to help managing bot stuff."""

        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

# ! Blacklist

    @admin.command(brief="Blacklist a guild", aliases=['guildban'])
    async def guildblock(self, ctx, guild: int, *, reason: str):
        """ Blacklist bot from specific guild """

        try:
            await ctx.message.delete()
        except:
            pass

        db_check = await self.bot.db.fetchval("SELECT guild_id FROM blockedguilds WHERE guild_id = $1", guild)

        if await self.bot.db.fetchval("SELECT _id FROM noblack WHERE _id = $1", guild):
            return await ctx.send("You cannot blacklist that guild")

        if db_check is not None:
            return await ctx.send("This guild is already in my blacklist.")

        await self.bot.db.execute("INSERT INTO blockedguilds(guild_id, reason, dev) VALUES ($1, $2, $3)", guild, reason, ctx.author.id)
        self.bot.blacklisted_guilds[guild] = [reason]
        server = self.bot.support

        g = self.bot.get_guild(guild)
        await ctx.send(f"I've successfully added **{g}** guild to my blacklist", delete_after=10)
        try:
            try:
                owner = g.owner
                e = discord.Embed(color=self.color['deny_color'], description=f"Hello!\nYour server **{ctx.guild}** has been blacklisted by {ctx.author}.\n**Reason:** {reason}\n\nIf you wish to appeal feel free to join the [support server]({self.bot.support})", timestamp=datetime.utcnow())
                e.set_author(name=f"Blacklist state updated!", icon_url=self.bot.user.avatar_url)
                await owner.send(embed=e)
            except Exception as e:
                print(e)
                await ctx.send("Wasn't able to message guild owner")
                pass
            await g.leave()
            await ctx.send(f"I've successfully left `{g}`")
        except Exception:
            pass

    @admin.command(brief="Unblacklist a guild", aliases=['guildunban'])
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
        self.bot.blacklisted_guilds.pop(guild)

        bu = await self.bot.db.fetch("SELECT * FROM blockedguilds")

        g = self.bot.get_guild(guild)
        await ctx.send(f"I've successfully removed **{g}** ({guild}) guild from my blacklist")

    @admin.command(brief="Bot block user", aliases=['botban'])
    async def botblock(self, ctx, user: discord.User, *, reason: str):
        """ Blacklist someone from bot commands """

        try:
            await ctx.message.delete()
        except:
            pass

        if reason is None:
            reason = 'No reason'

        with open('db/badges.json', 'r') as f:
            data = json.load(f)

        db_check = await self.bot.db.fetchval("SELECT user_id FROM blacklist WHERE user_id = $1", user.id)

        if user.id == 345457928972533773 or user.id == 373863656607318018:
            return await ctx.send("You cannot blacklist that user")


        if db_check is not None:
            return await ctx.send("This user is already in my blacklist.")

        try:
            data['Users'][f'{user.id}']["Badges"] = [f'{emotes.blacklisted}']
            self.bot.user_badges[f"{user.id}"]["Badges"] = [f'{emotes.blacklisted}']
        except KeyError:
            data['Users'][f'{user.id}'] = {"Badges": [f'{emotes.blacklisted}']}
            self.bot.user_badges[f"{user.id}"] = {"Badges": [f'{emotes.blacklisted}']}

        g = self.bot.get_guild(671078170874740756)
        member = g.get_member(user.id)
        if member:
            for role in member.roles:
                try:
                    await member.remove_roles(role, reason='User was blacklisted')
                except:
                    pass
        
            role = member.guild.get_role(734537587116736597)
            bot_admin = member.guild.get_role(674929900674875413)
            await member.add_roles(role, reason='User is blacklisted')
            overwrites = {
                member.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                member.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                bot_admin: discord.PermissionOverwrite(read_messages=True, send_messages=False)
            }
            category = member.guild.get_channel(734539183703588954)
            channel = await member.guild.create_text_channel(name=f'{member.id}-blacklist', overwrites=overwrites, category=category, reason=f"User was blacklisted")
            await channel.send(f"{member.mention} Hello! Since you're blacklisted, I'll be locking your access to all the channels. If you wish to appeal, feel free to do so in here. Leaving the server will get you banned immediately.\n\n**Blacklist reason:** {''.join(reason)}", allowed_mentions=discord.AllowedMentions(users=True))
        
        with open('db/badges.json', 'w') as f:
            data = json.dump(data, f, indent=4)

        await self.bot.db.execute("INSERT INTO blacklist(user_id, reason, dev) VALUES ($1, $2, $3)", user.id, reason, ctx.author.id)
        self.bot.blacklisted_users[user.id] = [reason]

        try:
            e = discord.Embed(color=self.color['deny_color'], description=f"Hello!\nYou've been blacklisted from using Dredd commands by {ctx.author}.\n**Reason:** {reason}\n\nIf you think your blacklist was unfair, please join the [support server]({self.bot.support})", timestamp=datetime.utcnow())
            e.set_author(name=f"Blacklist state updated!", icon_url=self.bot.user.avatar_url)
            await user.send(embed=e)
        except Exception as e:
            await ctx.channel.send(f"{emotes.warning} **Error occured:** {e}")
            pass
        await ctx.send(f"I've successfully added **{user}** to my blacklist")

    @admin.command(brief="Bot unblock user", aliases=['botunban'])
    async def botunblock(self, ctx, user: discord.User, *, reason: str):
        """ Unblacklist someone from bot commands """

        try:
            await ctx.message.delete()
        except:
            pass

        db_check = await self.bot.db.fetchval("SELECT user_id FROM blacklist WHERE user_id = $1", user.id)

        with open('db/badges.json', 'r') as f:
            data = json.load(f)

        if db_check is None:
            return await ctx.send("This user isn't in my blacklist.")

        await self.bot.db.execute("DELETE FROM blacklist WHERE user_id = $1", user.id)
        self.bot.blacklisted_users.pop(user.id)
        try:
            data['Users'].pop(f"{user.id}")
            self.bot.user_badges.pop(f"{user.id}")
        except KeyError:
            pass
        
        g = self.bot.get_guild(671078170874740756)
        member = g.get_member(user.id)

        if member:
            try:
                if emotes.bot_early_supporter not in data['Users'][f'{member.id}']['Badges']:
                    data['Users'][f"{member.id}"]['Badges'] += [emotes.bot_early_supporter]
                    self.bot.user_badges[f"{user.id}"]["Badges"] += [f'{emotes.bot_early_supporter}']
                else:
                    return
            except KeyError:
                data['Users'][f"{member.id}"] = {"Badges": [emotes.bot_early_supporter]}
                self.bot.user_badges[f"{user.id}"] = {"Badges": [emotes.bot_early_supporter]}

            role1 = member.guild.get_role(741749103280783380)
            role2 = member.guild.get_role(741748979917652050)
            role3 = member.guild.get_role(741748857888571502)
            role4 = member.guild.get_role(674930044082192397)
            role5 = member.guild.get_role(679642623107137549)
            await member.add_roles(role1, role2, role3, role4, role5)
            await member.remove_roles(discord.Object(id=734537587116736597))
            for channel in member.guild.get_channel(734539183703588954).channels:
                if channel.name == f'{member.id}-blacklist':
                    await channel.delete()
        
        with open('db/badges.json', 'w') as f:
            data = json.dump(data, f, indent=4)
        try:
            e = discord.Embed(color=self.color['approve_color'], description=f"Hello!\nYou've been un-blacklisted from using Dredd commands by {ctx.author}.\n**Reason:** {reason}", timestamp=datetime.utcnow())
            e.set_author(name=f"Blacklist state updated!", icon_url=self.bot.user.avatar_url)
            await user.send(embed=e)
        except Exception as e:
            await ctx.channel.send(f"{emotes.warning} **Error occured:** {e}")
            pass

        await ctx.send(f"I've successfully removed **{user}** from my blacklist")


# ! Social 

    @commands.command(aliases=['deny'], brief="Deny suggestion", description="Deny suggestion you think is not worth adding or already exists.")
    @commands.guild_only()
    async def suggestdeny(self, ctx, suggestion_id: int, *, note: str):
        """Deny someones suggestion"""
        try:
            await ctx.message.delete()
        except:
            pass

        approved = await self.bot.db.fetchval("SELECT approved FROM suggestions WHERE suggestion_id = $1", suggestion_id)

        if approved == True:
            return await ctx.author.send(f"{emotes.warning} You're trying to deny already denied suggestion.")

        message_id = await self.bot.db.fetchval("SELECT msg_id FROM suggestions WHERE suggestion_id = $1", suggestion_id)

        if message_id is None:
            return await ctx.author.send(f"Suggestion **#{suggestion_id}** doesn't exist.")

        channel = self.bot.get_channel(674929868345180160)
        message = await channel.fetch_message(id=message_id)
        embed = message.embeds[0]


        embed.color = self.color['deny_color']
        embed.set_footer(text=f"Suggestion was denied by {ctx.author}")
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
            e = discord.Embed(color=self.color['deny_color'], description=f"The following suggestion was denied by {ctx.author}\n**Reason:** {note}\n\n**Suggestion:**\n>>> {suggestion_info}")
            e.set_author(name=f"Suggested by {suggestion_owner} | #{suggestion_id}", icon_url=suggestion_owner.avatar_url)
            try:
                user = self.bot.get_user(user)
                await self.bot.db.execute("DELETE FROM track_suggest WHERE user_id = $1 AND suggestion_id = $2", user.id, suggestion_id)
                await user.send(embed=e)
            except Exception as e:
                print(e)
                pass

    @commands.command(aliases=['approve'], brief="Approve suggestion", description="Approve suggestion you think is worth adding")
    @commands.guild_only()
    async def suggestapprove(self, ctx, suggestion_id: int, *, note: str):
        """Approve someones suggestion."""

        try:
            await ctx.message.delete()
        except:
            pass

        approved = await self.bot.db.fetchval("SELECT approved FROM suggestions WHERE suggestion_id = $1", suggestion_id)

        if approved == True:
            return await ctx.author.send(f"{emotes.warning} You're trying to approve already approved suggestion.")

        message_id = await self.bot.db.fetchval("SELECT msg_id FROM suggestions WHERE suggestion_id = $1", suggestion_id)

        if message_id is None:
            return await ctx.author.send(f"Suggestion **#{suggestion_id}** doesn't exist.")

        channel = self.bot.get_channel(674929868345180160)
        message = await channel.fetch_message(message_id)
        embed = message.embeds[0]

        embed.color = self.color['approve_color']
        embed.set_footer(text=f"Suggestion was approved by {ctx.author}")
        embed.add_field(name="Note", value=note)
        await message.clear_reactions()
        await message.edit(embed=embed)
        

        await self.bot.db.execute("UPDATE suggestions SET approved = $1 WHERE suggestion_id = $2", True, suggestion_id)
        suggestion_ownerid = await self.bot.db.fetchval("SELECT user_id FROM suggestions WHERE suggestion_id = $1", suggestion_id)
        suggestion_owner = self.bot.get_user(suggestion_ownerid)
        suggestion_info = await self.bot.db.fetchval("SELECT suggestion_info FROM suggestions WHERE suggestion_id = $1", suggestion_id)
        trackers = await self.bot.db.fetch("SELECT user_id FROM track_suggest WHERE suggestion_id = $1", suggestion_id)
        await self.bot.db.execute("INSERT INTO todolist(user_id, guild_id, todo, time, jump_to) VALUES($1, $2, $3, $4, $5)", 345457928972533773, 671078170874740756, suggestion_info, datetime.now(), message.jump_url)
        to_send = []
        for user in trackers:
            to_send.append(user['user_id'])

        for user in to_send:
            e = discord.Embed(color=self.color['approve_color'], description=f"The following suggestion was approved by {ctx.author}\n**Reason:** {note}\n\n**Suggestion:**\n>>> {suggestion_info}")
            e.set_author(name=f"Suggested by {suggestion_owner} | #{suggestion_id}", icon_url=suggestion_owner.avatar_url)
            try:
                user = self.bot.get_user(user)
                await self.bot.db.execute("DELETE FROM track_suggest WHERE user_id = $1 AND suggestion_id = $2", user.id, suggestion_id)
                await user.send(embed=e)
            except Exception as e:
                print(e)
                pass

# ! Command managment

    @admin.command(brief="Disable enabled cmd")
    async def disablecmd(self, ctx, *, command):
        """Disable the given command. A few important main commands have been blocked from disabling for obvious reasons"""
        cant_disable = ["help", "jishaku", "dev", "disablecmd", "enablecmd", 'admin']
        cmd = self.bot.get_command(command)
        if cmd is None:
            embed = discord.Embed(color=self.color['logembed_color'], description=f"{emotes.red_mark} Command **{command}** doesn't exist.")
            return await ctx.send(embed=embed)

        if cmd.name in cant_disable:
            embed = discord.Embed(color=self.color['logembed_color'], description=f"{emotes.red_mark} Why are you trying to disable **{cmd.name}** you dum dum.")
            return await ctx.send(embed=embed)

        if cmd.parent and str(cmd.parent) not in cant_disable:
            if await self.bot.db.fetchval("SELECT * FROM cmds WHERE command = $1", str(f"{cmd.parent} {cmd.name}")) is None:
                await self.bot.db.execute("INSERT INTO cmds(command) VALUES ($1)", str(f"{cmd.parent} {cmd.name}"))
                return await ctx.send(f"{emotes.white_mark} Okay. **{cmd.parent} {cmd.name}** was disabled.")
            elif await self.bot.db.fetchval("SELECT * FROM cmds WHERE command = $1", str(f"{cmd.parent} {cmd.name}")):
                return await ctx.send(f"{emotes.warning} | `{cmd.parent} {cmd.name}` is already disabled")
        elif cmd.parent and str(cmd.parent) in cant_disable:
            return await ctx.send(f"{emotes.red_mark} You can't do that, sorry!")
        elif not cmd.parent:
            if await self.bot.db.fetchval("SELECT * FROM cmds WHERE command = $1", str(cmd.name)) is None:
                await self.bot.db.execute("INSERT INTO cmds(command) VALUES ($1)", str(cmd.name))
                return await ctx.send(f"{emotes.white_mark} Okay. **{cmd.name}** was disabled.")
            elif await self.bot.db.fetchval("SELECT * FROM cmds WHERE command = $1", str(cmd.name)):
                return await ctx.send(f"{emotes.warning} | `{cmd.name}` is already disabled")


    @admin.command(brief="Enable disabled cmd")
    async def enablecmd(self, ctx, *, command):
        """Enables a disabled command"""
        cmd = self.bot.get_command(command)

        if cmd is None:
            embed = discord.Embed(color=self.color['logembed_color'], description=f"{emotes.red_mark} Command **{command}** doesn't exist.")
            return await ctx.send(embed=embed)

        if cmd.parent:
            if await self.bot.db.fetchval("SELECT * FROM cmds WHERE command = $1", str(f"{cmd.parent} {cmd.name}")) is None:
                return await ctx.send(f"{emotes.warning} | `{cmd.parent} {cmd.name}` is not disabled!")
            elif await self.bot.db.fetchval("SELECT * FROM cmds WHERE command = $1", str(f"{cmd.parent} {cmd.name}")):
                await self.bot.db.execute("DELETE FROM cmds WHERE command = $1", str(f"{cmd.parent} {cmd.name}"))
                return await ctx.send(f"{emotes.white_mark} | `{cmd.parent} {cmd.name}` is now enabled!")
        elif not cmd.parent:
            if await self.bot.db.fetchval("SELECT * FROM cmds WHERE command = $1", str(cmd.name)) is None:
                return await ctx.send(f"{emotes.warning} | `{cmd.name}` is not disabled!")
            elif await self.bot.db.fetchval("SELECT * FROM cmds WHERE command = $1", str(cmd.name)):
                await self.bot.db.execute("DELETE FROM cmds WHERE command = $1", str(cmd.name))
                return await ctx.send(f"{emotes.white_mark} | `{cmd.name}` is now enabled!")
            

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
            em = discord.Embed(color=self.color['embed_color'],
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
    
    @admin.command(name="add-badge", aliases=['addbadge', 'abadge'])
    async def add_badge(self, ctx, user: discord.User, badge):
        with open('db/badges.json', 'r') as f:
            data = json.load(f)

        avail_badges = ['bot_early_supporter', 'bot_partner', 'bot_booster', 'bot_verified', 'discord_bug1']
        if badge.lower() not in avail_badges:
            return await ctx.send(f"{emotes.warning} **Invalid badge! Here are the valid ones:** {', '.join(avail_badges)}", delete_after=20)

        if badge.lower() == "bot_early_supporter":
            badge = emotes.bot_early_supporter
        elif badge.lower() == "bot_partner":
            badge = emotes.bot_partner
        elif badge.lower() == "discord_bug1":
            badge = emotes.discord_bug1
        elif badge.lower() == "bot_booster":
            badge = emotes.bot_booster
        elif badge.lower() == "bot_verified":
            badge = emotes.bot_verified

        try:
            if badge in data['Users'][f'{user.id}']["Badges"]:
                return await ctx.send(f"{emotes.warning} {user} already has {badge} badge")
            elif badge not in data['Users'][f'{user.id}']["Badges"]:
                data['Users'][f'{user.id}']["Badges"] += [badge]
                self.bot.user_badges[f"{user.id}"]["Badges"] += [badge]
        except KeyError:
            data['Users'][f"{user.id}"] = {"Badges": [badge]}
            self.bot.user_badges[f"{user.id}"] = {"Badges": [badge]}

        with open('db/badges.json', 'w') as f:
            data = json.dump(data, f, indent=4)

        await ctx.send(f"{emotes.white_mark} Added {badge} to {user}.")

    @admin.command(name="remove-badge", aliases=['removebadge', 'rbadge'])
    async def remove_badge(self, ctx, user: discord.User, badge):
        with open('db/badges.json', 'r') as f:
            data = json.load(f)

        avail_badges = ['bot_early_supporter', 'bot_partner', 'bot_booster', 'bot_verified']
        if badge.lower() not in avail_badges:
            return await ctx.send(f"{emotes.warning} **Invalid badge! Here are the valid ones:** {', '.join(avail_badges)}", delete_after=20)

        if badge.lower() == "bot_early_supporter":
            badge = emotes.bot_early_supporter
        elif badge.lower() == "bot_partner":
            badge = emotes.bot_partner
        elif badge.lower() == "bot_hunter":
            badge = emotes.bot_hunter
        elif badge.lower() == "bot_booster":
            badge = emotes.bot_booster
        elif badge.lower() == "bot_verified":
            badge = emotes.bot_verified

        try:
            data['Users'][f'{user.id}']["Badges"].remove(badge)
            self.bot.user_badges[f"{user.id}"]["Badges"].remove(badge)
        except KeyError as e:
            print(e)
            return await ctx.send(f"{emotes.warning} {user} has no badges!")

        with open('db/badges.json', 'w') as f:
            data = json.dump(data, f, indent=4)

        await ctx.send(f"{emotes.white_mark} Removed {badge} from {user}.")



def setup(bot):
    bot.add_cog(admin(bot))
