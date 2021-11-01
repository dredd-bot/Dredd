"""
Dredd, discord bot
Copyright (C) 2021 Moksej
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
from discord.errors import NotFound
from io import BytesIO

from utils import default
from datetime import datetime, timedelta
from db.cache import CacheManager as cm
from cogs.music import Player
from contextlib import suppress
from colorama import Fore as print_color


class Tasks(commands.Cog, name="Tasks", command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        self.bot = bot
        self.help_icon = ''
        self.guild_data.start()
        self.temp_ban.start()
        self.temp_mute.start()
        self.reminders.start()
        self.dispatch_unmute.start()
        self.dispatch_unban.start()
        self.delete_nicknames.start()
        self.backups.start()
        self.del_member_count.start()
        self.clear_mode247.start()
        self.clear_automod_counter.start()
        self.client = gmailpy.Client(mail=bot.config.BACKUP_USER, password=bot.config.BACKUP_PASSWORD)

    def cog_unload(self):
        self.guild_data.cancel()
        self.temp_ban.cancel()
        self.temp_mute.cancel()
        self.reminders.cancel()
        self.dispatch_unmute.cancel()
        self.dispatch_unban.cancel()
        self.delete_nicknames.cancel()
        self.backups.cancel()
        self.del_member_count.cancel()
        self.clear_mode247.cancel()
        self.clear_automod_counter.cancel()

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
                        to_disp = cm.get(self.bot, 'to_unban', guild.id)
                        if not to_disp:
                            self.bot.to_unban[guild.id] = {'users': [], 'mod': mod}
                        await default.execute_untemporary(self, 2, user, guild)
                        with suppress(NotFound):
                            await guild.unban(user, reason='Auto Unban')
                            self.bot.to_unban[guild.id]['users'].append(user)
        except Exception as e:
            print(print_color.RED, "[AUTO UNBAN] - {e}")

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
                        to_disp = cm.get(self.bot, 'to_unmute', guild.id)
                        if not to_disp:
                            self.bot.to_unmute[guild.id] = {'users': [], 'mod': mod}
                        await default.execute_untemporary(self, 1, user, guild)
                        role = guild.get_role(int(check['role']))
                        member = guild.get_member(user.id)
                        if role:
                            await member.remove_roles(role, reason='Auto Unmute')
                        if member:
                            self.bot.to_unmute[guild.id]['users'].append(member)
        except Exception as e:
            print(print_color.RED, "[AUTO UNMUTE] - {e}")

    @tasks.loop(seconds=10)
    async def dispatch_unmute(self):
        try:
            for guild in self.bot.to_unmute:
                if len(self.bot.to_unmute[guild]['users']) >= 1:
                    self.bot.dispatch('unmute', self.bot.get_guild(guild), self.bot.to_unmute[guild]['mod'], self.bot.to_unmute[guild]['users'], 'Auto Unmute')
                self.bot.to_unmute.pop(guild, None)
        except Exception:
            pass

    @tasks.loop(seconds=10)
    async def dispatch_unban(self):
        try:
            for guild in self.bot.to_unban:
                if len(self.bot.to_unban[guild]['users']) >= 1:
                    self.bot.dispatch('unban', self.bot.get_guild(guild), self.bot.to_unban[guild]['mod'], self.bot.to_unban[guild]['users'], 'Auto Unban')
                self.bot.to_unban.pop(guild, None)
        except Exception as e:
            print(print_color.RED, "[DISPATCH UNMUTE] - {e}")

    @tasks.loop(seconds=1)
    async def reminders(self):
        try:
            reminds = self.bot.reminders
            for result in reminds:
                for result_2 in reminds[result]:
                    json = reminds[result][result_2]
                    the_time = json['time']
                    try:
                        now = datetime.utcnow()
                        seconds = (the_time - now).total_seconds()
                    except Exception:
                        now = discord.utils.utcnow()
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
                                    await user.send(_("*The original message was deleted or I'm missing permissions*\n\nYour reminder: {0}").format(reminder[:1800] + '...' if len(reminder) > 1800 else reminder))
                                except Exception:
                                    pass
                        self.bot.reminders[result].pop(result_2)
                        await self.bot.db.execute("DELETE FROM reminders WHERE user_id = $1 AND reminder = $2 AND time = $3", result, json['content'], json['time'])
        except Exception:
            pass

    @tasks.loop(hours=6)
    async def backups(self):
        name = datetime.now().__format__("%d%m%y-%H:%M")
        SHELL = os.getenv("SHELL") or "/bin/bash"
        sequence = [SHELL, '-c', """pg_dump -U dredd -h localhost "dredd v3" > "backups/{0}.sql" """.format(name)]
        subprocess.Popen(sequence, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        content = 'Backup created on {0}'.format(name)
        receiver = self.bot.config.BACKUP_RECEIVER
        ch = self.bot.get_channel(679647378210291832)
        await asyncio.sleep(5)
        with open(f'backups/{name}.sql', 'r', encoding='utf8') as f:
            backup = f.read()

        backup = BytesIO(backup.encode('utf8'))
        if not backup:
            return await ch.send(f"{self.bot.get_user(345457928972533773).mention} Backup `{name}.sql` is empty!", allowed_mentions=discord.AllowedMentions(users=True))
        await self.client.send(receiver, content, subject="Database Backup", attachment_bytes=backup.read(), attachment_name=f"{name}.sql")
        return await ch.send(f"Created backup `{name}.sql`")

    @tasks.loop(hours=24)
    async def delete_nicknames(self):
        now = datetime.now()
        days = timedelta(days=90)
        time = now - days
        await self.bot.db.execute("DELETE FROM nicknames WHERE time < $1", time)

    @tasks.loop(hours=1)
    async def del_member_count(self):
        guild = self.bot.get_guild(568567800910839811)
        await self.bot.get_channel(618583328458670090).edit(name=f"Member Count: {len(guild.members)}")

    @tasks.loop(minutes=30)
    async def clear_mode247(self):
        for guild in self.bot.mode247:
            now = datetime.utcnow()
            last_connection = self.bot.mode247[guild]['last_connection'] + timedelta(hours=12)
            seconds = (last_connection - now).total_seconds()  # type: ignore
            guild = self.bot.get_guild(guild)
            if seconds <= 0 and guild:
                player = self.bot.wavelink.get_player(guild.id, cls=Player)
                channel = guild.get_channel(self.bot.mode247[guild.id]['text'])
                with suppress(Exception):
                    await channel.send(_("No one has connected to a voice channel in over 12 hours, to save up "
                                         "bot's resources I'll be destroying the player and leaving the voice channel."))
                await player.destroy()
                self.bot.mode247.pop(guild)

    @tasks.loop(minutes=15)
    async def clear_automod_counter(self):
        self.bot.automod_counter.clear()

    @guild_data.before_loop
    async def before_guild_delete(self):
        await self.bot.wait_until_ready()
        print(print_color.GREEN, "[BACKGROUND] Started automatic guild data delete process")

    @temp_ban.before_loop
    async def before_temp_ban(self):
        await self.bot.wait_until_ready()
        print(print_color.GREEN, "[BACKGROUND] Started temp bans unbanning process")

    @temp_mute.before_loop
    async def before_temp_mute(self):
        await self.bot.wait_until_ready()
        print(print_color.GREEN, "[BACKGROUND] Started temp mutes unmuting process")

    @reminders.before_loop
    async def before_reminders(self):
        await self.bot.wait_until_ready()
        print(print_color.GREEN, "[BACKGROUND] Started sending reminders")

    @delete_nicknames.before_loop
    async def before_delete_nicknames(self):
        await self.bot.wait_until_ready()
        print(print_color.GREEN, "[BACKGROUND] Started deleting old nicknames")

    @backups.before_loop
    async def before_backups(self):
        await self.bot.wait_until_ready()
        print(print_color.GREEN, "[BACKGROUND] Started creating backups")

    @del_member_count.before_loop
    async def before_del_member_count(self):
        await self.bot.wait_until_ready()
        print(print_color.GREEN, "[BACKGROUND] Started updating DEL member count")

    @clear_mode247.before_loop
    async def before_clear_mode247(self):
        await self.bot.wait_until_ready()
        print(print_color.GREEN, "[BACKGROUND] Started leaving inactive voice channels")

    @dispatch_unmute.before_loop
    async def before_dispatch_unmute(self):
        await self.bot.wait_until_ready()
        print(print_color.GREEN, "[BACKGROUND] Started dispatching mutes.")

    @dispatch_unban.before_loop
    async def before_dispatch_unban(self):
        await self.bot.wait_until_ready()
        print(print_color.GREEN, "[BACKGROUND] Started dispatching bans.")

    @clear_automod_counter.before_loop
    async def before_automod_clear(self):
        await self.bot.wait_until_ready()
        print(print_color.GREEN, "[BACKGROUND] Started resetting raid counters.")


def setup(bot):
    bot.add_cog(Tasks(bot))
