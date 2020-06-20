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
from discord.ext import commands, tasks


class Background(commands.Cog, name="BG"):
    def __init__(self, bot):
        self.bot = bot
        self.temp_mute.start()
        self.help_icon = ""
        self.big_icon = ""

    @tasks.loop(seconds=1)
    async def temp_mute(self):
        for guild, user, mod, reason, timed, roleid in self.bot.temp_timer:
            if timed - time.time() <= 0:
                g = self.bot.get_guild(guild)
                m = g.get_member(user)
                r = g.get_role(roleid)
                reasons = "Auto unmute"
                try:
                    await m.remove_roles(r, reason=reasons)
                except:
                    pass
                await self.bot.db.execute("DELETE FROM moddata WHERE user_id = $1 AND guild_id = $2", user, guild)
                self.bot.temp_timer.remove((guild, user, mod, reason, timed, roleid))

    @temp_mute.before_loop
    async def before_change_lmao(self):

        await self.bot.wait_until_ready()
        print('\n[BACKGROUND] Started temp punishments task.')

def setup(bot):
    bot.add_cog(Background(bot))