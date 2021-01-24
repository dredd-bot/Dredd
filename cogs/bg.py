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
import subprocess
import os
import asyncio

from discord.ext import commands, tasks
from datetime import datetime
from db import emotes
from utils.default import color_picker, traceback_maker
from utils.caches import CacheManager as cm


class Background(commands.Cog, name="BG"):
    def __init__(self, bot):
        self.bot = bot
        self.temp_mute.start()
        self.temp_ban.start()
        self.auto_backup.start()
        self.help_icon = ""
        self.big_icon = ""
        self.color = color_picker('colors')
    
    async def log_temp_unmute(self, guild=None, mod=None, member=None, reason=None):
        check = cm.get_cache(self.bot, guild.id, 'moderation')

        if check is None:
            return
        elif check is not None:
            channel = check
            case = cm.get_cache(self.bot, guild.id, 'case_num')
            chan = self.bot.get_channel(channel)

            if case is None:
                await self.bot.db.execute("INSERT INTO modlog(guild_id, case_num) VALUES ($1, $2)", guild.id, 1)
                self.bot.case_num[guild.id] = 1

            casenum = self.bot.case_num[guild.id]
            e = discord.Embed(color=self.color['logging_color'], description=f"{emotes.log_memberedit} **{member}** unmuted `[#{str(casenum)}]`")
            e.add_field(name="Previously muted by:", value=f"{mod} ({mod.id})", inline=False)
            e.add_field(name="Reason:", value=f"{reason}", inline=False)
            e.set_thumbnail(url=member.avatar_url_as(format='png'))
            e.set_footer(text=f"Member ID: {member.id}")

            await chan.send(embed=e)
            await self.bot.db.execute("UPDATE modlog SET case_num = case_num + 1 WHERE guild_id = $1", guild.id)
            self.bot.case_num[guild.id] += 1

    def cog_unload(self):
        self.temp_mute.cancel()
        self.temp_ban.cancel()
        self.auto_backup.cancel()

    # yes this is unprofessional way, but don't blame me ok. Thanks
    @tasks.loop(seconds=1)
    async def temp_mute(self):
        for guild, user, mod, reason, timed, roleid, mute in self.bot.temp_timer:
            now = datetime.utcnow()
            seconds = (timed - now).total_seconds()
            if timed and seconds <= 0:
                try:
                    g = self.bot.get_guild(guild)
                    m = g.get_member(user)
                    r = g.get_role(roleid)
                    mm = g.get_member(mod)
                    reasons = "Auto unmute"
                    try:
                        await m.remove_roles(r, reason=reasons)
                        await self.log_temp_unmute(guild=g, mod=mm, member=m, reason=reasons)
                    except Exception as e:
                        print(e)
                        pass
                except Exception as e:
                    print(e)
                    pass
                await self.bot.db.execute("DELETE FROM moddata WHERE user_id = $1 AND guild_id = $2 AND type = $3", user, guild, mute)
                self.bot.temp_timer.remove((guild, user, mod, reason, timed, roleid, mute))

    @tasks.loop(seconds=1)
    async def temp_ban(self):
        for guild, user, mod, reason, timed, ban in self.bot.temp_bans:
            now = datetime.utcnow()
            seconds = (timed - now).total_seconds()
            if timed and seconds <= 0:
                try:
                    g = self.bot.get_guild(guild)
                    mm = g.get_member(mod)
                    reasons = "Auto unmute"
                    try:
                       await g.unban(discord.Object(user), reason=f"Auto unban. Previously banned by: {mm}")
                    except Exception as e:
                        print(traceback_maker(e))
                        pass
                except Exception as e:
                    print(traceback_maker(e))
                    pass
                await self.bot.db.execute("DELETE FROM moddata WHERE user_id = $1 AND guild_id = $2 AND type = $3", user, guild, ban)
                self.bot.temp_bans.remove((guild, user, mod, reason, timed, ban))

    @tasks.loop(hours=12)
    async def auto_backup(self):
        name = datetime.utcnow().__format__("%d%m%y-%H:%M")          
        SHELL = os.getenv("SHELL") or "/bin/bash"
        sequence = [SHELL, '-c', 'pg_dump -U dredd -h localhost dredd > "backups/{0}.sql"'.format(name)]
        subprocess.Popen(sequence, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        await asyncio.sleep(10)
        file = discord.File('backups/{0}.sql'.format(name))
        mok = self.bot.get_user(345457928972533773)
        await mok.send(file=file, content="Auto backup made on - `{0}`".format(datetime.utcnow().__format__("%D @ %H:%M")))
        os.remove('backups/{0}.sql'.format(name))

    @temp_mute.before_loop
    async def before_change_lmao(self):

        await self.bot.wait_until_ready()
        print('\n[BACKGROUND] Started temp mutes punishments task.')
    
    @temp_ban.before_loop
    async def before_temp_unban(self):

        await self.bot.wait_until_ready()
        print('\n[BACKGROUND] Started temp ban punishments task.')

    @auto_backup.before_loop
    async def before_auto_backup(self):
        await self.bot.wait_until_ready()
        print('\n[BACKGROUND] Started auto backups task.')

def setup(bot):
    bot.add_cog(Background(bot))
