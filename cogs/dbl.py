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

import dbl
import discord
from discord.ext import commands, tasks
import config
import datetime

import asyncio


class DiscordBotsOrgAPI(commands.Cog, name="DBL"):
    """Handles interactions with the discordbots.org API"""

    def __init__(self, bot):
        self.bot = bot
        self.token = config.DBLToken # set this to your DBL token
        self.bot.dblpy = dbl.DBLClient(self.bot, self.token, webhook_path='/dblwebhook', webhook_auth=config.DBL_password, webhook_port=5000, autopost=True)

        self.help_icon = ""
        self.big_icon = ""

    @commands.Cog.listener()
    async def on_dbl_test(self, data):
        c = await self.bot.fetch_channel(780066719645040651)
        user = await self.bot.fetch_user(int(data['user']))
        e = discord.Embed(title='Upvote received', 
                          url="https://top.gg/bot/667117267405766696/vote",
                          color=0x5E82AC)
        e.set_author(name=user, icon_url=user.avatar_url)
        e.description = f"**{user}** has test voted for me on {datetime.datetime.now().__format__('%c')}"
        e.set_thumbnail(url="https://cdn.discordapp.com/attachments/638902095520464908/659611283443941376/upvote.png")
        e.set_footer(text=f'User ID: {user.id}')
        await c.send(f"A vote test has ran succesfully!", embed=e)

    @commands.Cog.listener()
    async def on_dbl_vote(self, data):
        channel = self.bot.get_channel(780066719645040651)
        user = await self.bot.fetch_user(int(data['user']))
        e = discord.Embed(title='Upvote received', 
                          url="https://top.gg/bot/667117267405766696/vote",
                          color=0x5E82AC)
        e.set_author(name=user, icon_url=user.avatar_url)
        e.description = f"**{user}** has voted for me on {datetime.datetime.now().__format__('%c')}"
        e.set_thumbnail(url="https://cdn.discordapp.com/attachments/638902095520464908/659611283443941376/upvote.png")
        e.set_footer(text=f'User ID: {user.id}')
        await channel.send(embed=e)
    
    @tasks.loop(minutes=30.0)
    async def update_stats(self):
        """This function runs every 30 minutes to automatically update your server count"""
        print('Attempting to post server count')
        try:
            await self.dblpy.post_guild_count()
            print('Posted server count ({})'.format(self.dblpy.guild_count()))
        except Exception as e:
            print('Failed to post server count\n{}: {}'.format(type(e).__name__, e))

    @commands.Cog.listener()
    async def on_guild_post():
        print("Server count posted successfully")

def setup(bot):
    bot.add_cog(DiscordBotsOrgAPI(bot))
