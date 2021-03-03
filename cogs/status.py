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
import datetime
from discord.ext import commands
from discord.utils import escape_markdown
from utils import btime
from utils.default import timeago
from datetime import datetime
from db import emotes
from utils.caches import CacheManager as cm

class Eventss(commands.Cog, name="Eventss", command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener('on_member_update')
    async def status_log(self, before, after):
        await self.bot.wait_until_ready()

        if before.status == after.status:
            return

        check = cm.get_cache(self.bot, before.id, 'status_op_out')

        if check is None:
            return
        
        if before.bot:
            return

        idle = discord.Status.idle
        online = discord.Status.online
        dnd = discord.Status.dnd
        offline = discord.Status.offline

        check2 = await self.bot.db.fetchval("SELECT * FROM useractivity WHERE user_id = $1", before.id)

        if before.status != after.status:
            if before.status != offline and after.status == offline:
                if check2:
                    await self.bot.db.execute("UPDATE useractivity SET activity_title = $1, time = $2 WHERE user_id = $3", str(after.status.name), datetime.now(), before.id)
                elif check2 is None:
                    await self.bot.db.execute("INSERT INTO useractivity(user_id, activity_title, time) VALUES($1, $2, $3)", before.id, str(after.status.name), datetime.now())
            
            elif before.status == offline and after.status != offline:
                if check2:
                    await self.bot.db.execute("UPDATE useractivity SET activity_title = $1, time = $2 WHERE user_id = $3", str(after.status.name), datetime.now(), before.id)
                elif check2 is None:
                    await self.bot.db.execute("INSERT INTO useractivity(user_id, activity_title, time) VALUES($1, $2, $3)", before.id, str(after.status.name), datetime.now())
            
            elif before.status != offline and after.status == idle:
                if check2:
                    await self.bot.db.execute("UPDATE useractivity SET activity_title = $1, time = $2 WHERE user_id = $3", str(after.status.name), datetime.now(), before.id)
                elif check2 is None:
                    await self.bot.db.execute("INSERT INTO useractivity(user_id, activity_title, time) VALUES($1, $2, $3)", before.id, str(after.status.name), datetime.now())
            
            elif before.status != offline and after.status == dnd:
                if check2:
                    await self.bot.db.execute("UPDATE useractivity SET activity_title = $1, time = $2 WHERE user_id = $3", str(after.status.name), datetime.now(), before.id)
                elif check2 is None:
                    await self.bot.db.execute("INSERT INTO useractivity(user_id, activity_title, time) VALUES($1, $2, $3)", before.id, str(after.status.name), datetime.now())
            
            elif before.status != offline and after.status == online:
                if check2:
                    await self.bot.db.execute("UPDATE useractivity SET activity_title = $1, time = $2 WHERE user_id = $3", str(after.status.name), datetime.now(), before.id)
                elif check2 is None:
                    await self.bot.db.execute("INSERT INTO useractivity(user_id, activity_title, time) VALUES($1, $2, $3)", before.id, str(after.status.name), datetime.now())

    @commands.Cog.listener('on_message_delete')
    async def snipe_messages(self, message):
        await self.bot.wait_until_ready()

        op_out_check = cm.get_cache(self.bot, message.author.id, 'snipes_op_out')

        if op_out_check:
            return
        
        if message.webhook_id is None:
            self.bot.snipes[message.channel.id] = {'message': message.content, 'deleted_at': datetime.now(), 'author': message.author.id, 'nsfw': message.channel.is_nsfw()}

def setup(bot):
    bot.add_cog(Eventss(bot))
