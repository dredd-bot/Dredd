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
import asyncio
import gmailpy
import subprocess
import os

from discord.ext import commands, tasks
from discord.utils import escape_markdown

from utils import btime, default
from datetime import datetime, timedelta
from db.cache import CacheManager as cm


class Tasks(commands.Cog, name="Tasks", command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        self.bot = bot
        self.help_icon = ''
        self.guild_data.start()
        self.temp_ban.start()
        self.temp_mute.start()
        self.reminders.start()
        self.dispatch_unmute.start()
        self.delete_nicknames.start()
        self.backups.start()
        self.client = gmailpy.Client(mail=bot.config.BACKUP_USER, password=bot.config.BACKUP_PASSWORD)

    def cog_unload(self):
        self.guild_data.cancel()
        self.temp_ban.cancel()
        self.temp_mute.cancel()
        self.reminders.cancel()
        self.dispatch_unmute.cancel()
        self.delete_nicknames.cancel()
        self.backups.cancel()

    @tasks.loop(seconds=1)
    async def guild_data(self):
        try:
            for guild_id in self.bot.guilds_data:
                now = datetime.utcnow()
                the_time = cm.get(self.bot, 'guilds_data', guild_id)
                seconds = (the_time - now).total_seconds()
                if the_time and seconds <= 0:
                    await self.bot.db.execute("DELETE FROM guilds WHERE guild_id = $1", guild_id)
                    cm.clear(self.bot, guild_id)
                    await default.guild_data_deleted(self, guild_id)
        except Exception:
            pass

    @tasks.loop(seconds=1)
    async def temp_ban(self):
        try:
            for result in self.bot.temp_bans:
                check = cm.get(self.bot, 'temp_bans', result)
                if check:
                    now = datetime.utcnow()
                    the_time = check['time']
                    seconds = (the_time - now).total_seconds()
                    if the_time and seconds <= 0:
                        user = await self.bot.try_user(int(result.split(', ')[0]))
                        guild = self.bot.get_guild(int(result.split(', ')[1]))
                        mod = await self.bot.try_user(int(check['moderator']))
                        await default.execute_untemporary(self, 2, user, guild)
                        await guild.unban(user, reason='Auto Unban')
                        self.bot.dispatch('unban', guild, mod, [user], 'Auto Unban')
        except Exception:
            pass

    @tasks.loop(seconds=1)
    async def temp_mute(self):
        try:
            for result in self.bot.temp_mutes:
                check = cm.get(self.bot, 'temp_mutes', result)
                if check:
                    now = datetime.utcnow()
                    the_time = check['time']
                    seconds = (the_time - now).total_seconds()
                    if the_time and seconds <= 0:
                        user = await self.bot.try_user(int(result.split(', ')[0]))
                        guild = self.bot.get_guild(int(result.split(', ')[1]))
                        mod = await self.bot.try_user(int(check['moderator']))
                        to_disp = cm.get(self.bot, 'to_dispatch', guild.id)
                        if not to_disp:
                            self.bot.to_dispatch[guild.id] = {'users': [], 'mod': mod}
                        await default.execute_untemporary(self, 1, user, guild)
                        role = guild.get_role(int(check['role']))
                        if role:
                            member = guild.get_member(user.id)
                            await member.remove_roles(role, reason='Auto Unmute')
                        self.bot.to_dispatch[guild.id]['users'].append(member)
        except Exception as e:
            pass

    @tasks.loop(seconds=10)
    async def dispatch_unmute(self):
        for guild in self.bot.to_dispatch:
            self.bot.dispatch('unmute', self.bot.get_guild(guild), self.bot.to_dispatch[guild]['mod'], self.bot.to_dispatch[guild]['users'], 'Auto Unmute')
            self.bot.to_dispatch.pop(guild, None)

    @tasks.loop(seconds=1)
    async def reminders(self):
        try:
            reminds = self.bot.reminders
            for result in reminds:
                for result_2 in reminds[result]:
                    json = reminds[result][result_2]
                    now = datetime.utcnow()
                    the_time = json['time']
                    seconds = (the_time - now).total_seconds()
                    if the_time and seconds <= 0:
                        try:
                            channel = self.bot.get_channel(json['channel'])
                            message = await channel.fetch_message(json['message'])
                            await message.reply(json['content'], allowed_mentions=discord.AllowedMentions(replied_user=True))
                        except Exception:
                            user = self.bot.get_user(result)
                            try:
                                channel = self.bot.get_channel(json['channel'])
                                await channel.send(f"{user.mention}: {json['content']}", allowed_mentions=discord.AllowedMentions(users=True))
                            except Exception:
                                try:
                                    reminder = json['content']
                                    await user.send(_("*The original message was deleted or I'm missing permissions*\n\nYour reminder: {0}").format(reminder[:1800] + '...' if len(reminder) > 1800 else remidner))
                                except Exception:
                                    pass
                        self.bot.reminders[result].pop(result_2)
                        await self.bot.db.execute("DELETE FROM reminders WHERE user_id = $1 AND reminder = $2 AND time = $3", result, json['content'], json['time'])
        except Exception:
            pass

    @tasks.loop(hours=6)
    async def backups(self):
        name = datetime.utcnow().__format__("%d%m%y-%H:%M")
        SHELL = os.getenv("SHELL") or "/bin/bash"
        sequence = [SHELL, '-c', """pg_dump -U dredd -h localhost "dredd v3" > "backups/{0}.sql" """.format(name)]
        subprocess.Popen(sequence, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        content = 'Backup created on {0}'.format(name)
        receiver = self.bot.config.BACKUP_RECEIVER
        ch = self.bot.get_channel(679647378210291832)
        await asyncio.sleep(5)
        with open(f'backups/{name}.sql', 'r', encoding='utf8') as f:
            backup = f.read()
        if not backup:
            return await ch.send(f"{self.bot.get_user(345457928972533773).mention} Backup `{name}.sql` is empty!", allowed_mentions=discord.AllowedMentions(users=True))
        else:
            await self.client.send(receiver, content, subject="Database Backup", bcc=None, attachment_bytes=backup, attachment_name=f"{name}.sql")
            return await ch.send(f"Created backup `{name}.sql`")

    @tasks.loop(hours=24)
    async def delete_nicknames(self):
        now = datetime.utcnow()
        days = timedelta(days=90)
        time = now - days
        await self.bot.db.execute("DELETE FROM nicknames WHERE time < $1", time)

    @guild_data.before_loop
    async def before_guild_delete(self):
        await self.bot.wait_until_ready()
        print("[BACKGROUND] Started automatic guild data delete process")

    @temp_ban.before_loop
    async def before_temp_ban(self):
        await self.bot.wait_until_ready()
        print("[BACKGROUND] Started temp bans unbanning process")

    @temp_mute.before_loop
    async def before_temp_mute(self):
        await self.bot.wait_until_ready()
        print("[BACKGROUND] Started temp mutes unmuting process")

    @reminders.before_loop
    async def before_reminders(self):
        await self.bot.wait_until_ready()
        print("[BACKGROUND] Started sending reminders")

    @delete_nicknames.before_loop
    async def before_delete_nicknames(self):
        await self.bot.wait_until_ready()
        print("[BACKGROUND] Started deleting old nicknames")

    @backups.before_loop
    async def before_backups(self):
        await self.bot.wait_until_ready()
        print("[BACKGROUND] Started creating backups")


def setup(bot):
    bot.add_cog(Tasks(bot))
