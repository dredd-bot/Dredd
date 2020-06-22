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

import dbl
import discord
from discord.ext import commands, tasks
import config

import asyncio


class DiscordBotsOrgAPI(commands.Cog, name="DBL"):
    """Handles interactions with the discordbots.org API"""

    def __init__(self, bot):
        self.bot = bot
        self.token = config.DBLToken # set this to your DBL token
        self.bot.dblpy = dbl.DBLClient(self.bot, self.token, autopost=True)

        self.help_icon = ""
        self.big_icon = ""

    # @commands.Cog.listener()
    # async def on_dbl_test(self, data):
    #     c = await self.bot.fetch_channel(679647378210291832)
    #     await c.send("A vote test has ran succesfully!")

    # @commands.Cog.listener()
    # async def on_dbl_vote(self, data):
    #     channel = await self.bot.fetch_channel(679647378210291832)
    #     user = await self.bot.fetch_user(int(data['user']))
    #     e = discord.Embed(color=0x5E82AC, 
    #                       title="Received Upvote!",
    #                       description=f"New upvote received from **{user}**!")
    #     e.set_author(icon_url=user.avatar_url, name=str(user))
    #     e.set_thumbnail(url="https://cdn.discordapp.com/attachments/638902095520464908/659611283443941376/upvote.png")
    #     await channel.send(embed=e)

    # @commands.Cog.listener()
    # async def on_guild_post():
    #     print("Server count posted successfully")

def setup(bot):
    bot.add_cog(DiscordBotsOrgAPI(bot))