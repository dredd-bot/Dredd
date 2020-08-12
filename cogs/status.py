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
from discord.ext import commands
from discord.utils import escape_markdown
from utils import btime
from utils.default import timeago
from datetime import datetime
from db import emotes


class Eventss(commands.Cog, name="Eventss", command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener('on_member_update')
    async def status_log(self, before, after):
        await self.bot.wait_until_ready()

        if before.status == after.status:
            return

        check = await self.bot.db.fetchval("SELECT * FROM status_op_out WHERE user_id = $1", before.id)
        check2 = await self.bot.db.fetchval("SELECT * FROM useractivity WHERE user_id = $1", before.id)

        if check is None:
            return
        
        if before.bot:
            return

        idle = discord.Status.idle
        online = discord.Status.online
        dnd = discord.Status.dnd
        offline = discord.Status.offline

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

    # @commands.Cog.listener('on_member_update')
    # async def presence_log(self, before, after):
    #     check = await self.bot.db.fetchval("SELECT * FROM presence_check WHERE user_id = $1", before.id)

    #     if before.bot:
    #         return

    #     if not check:
    #         return

    #     if before.activity != after.activity:
    #         if after.activity and after.activity.type == discord.ActivityType.playing:
    #             if after.activity.start is not None:
    #                 try:
    #                     await self.bot.db.execute('INSERT INTO presence_start(user_id, title, time) VALUES($1, $2, $3)', after.id, after.activity.name, after.activity.start)
    #                     print(after.id, after.activity.name, after.activity.start)
    #                 except:
    #                     return 
    #         if after.activity != before.activity and before.activity.name == await self.bot.db.fetchval("SELECT title FROM presence_start WHERE title = $1", before.activity.name):
    #             print(before.activity.name)
    #             time = await self.bot.db.fetchval("SELECT time FROM presence_start WHERE title = $1", before.activity.name)
    #             check = await self.bot.db.fetchval("SELECT activity_name FROM presence WHERE user_id = $1 AND activity_name = $2", before.id, before.activity.name) 
    #             if not check:
    #                 await self.bot.db.execute('INSERT INTO presence(user_id, activity_name, time) VALUES($1, $2, $3)', after.id, before.activity.name, btime.human_timedelta(time, suffix=None))
    #             elif check:
    #                 return

    @commands.Cog.listener('on_message_delete')
    async def snipe_messages(self, message):
        await self.bot.wait_until_ready()

        op_out_check = await self.bot.db.fetchval("SELECT * FROM snipe_op_out WHERE user_id = $1", message.author.id)
        check = await self.bot.db.fetchval("SELECT * FROM snipe WHERE guild_id = $1 AND user_id = $2 AND channel_id = $3", message.guild.id, message.author.id, message.channel.id)

        if op_out_check:
            return
        if check is None:
            await self.bot.db.execute("INSERT INTO snipe(message, user_id, guild_id, channel_id, time) VALUES($1, $2, $3, $4, $5)", message.content, message.author.id, message.guild.id, message.channel.id, datetime.now())
        else:
            await self.bot.db.execute("UPDATE snipe SET message = $1, time = $2, channel_id = $3 WHERE guild_id = $4 AND user_id = $5", message.content, datetime.now(), message.channel.id, message.guild.id, message.author.id)

def setup(bot):
    bot.add_cog(Eventss(bot))