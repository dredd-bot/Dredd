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

from discord.ext import commands, tasks

import discordlists


class DiscordListsPost(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api = discordlists.Client(self.bot)  # Create a Client instance
        self.api.set_auth("discordextremelist.xyz", self.bot.config.DEL_TOKEN)
        self.api.set_auth("discord.bots.gg",  self.bot.config.DBGG_TOKEN)
        self.api.set_auth("discord.boats",  self.bot.config.DBoats_TOKEN)
        #self.api.set_auth("wonderbotlist.com",  self.bot.config.WONDER_TOKEN)
        self.api.set_auth("glennbotlist.xyz",  self.bot.config.GLENN_TOKEN)
        self.api.set_auth("mythicalbots.xyz",  self.bot.config.MYTH_TOKEN)
        self.api.start_loop()  # Posts the server count automatically every 30 minutes

        self.help_icon = ''
        self.big_icon = ''

    @commands.command()
    async def post(self, ctx: commands.Context):
        """
        Manually posts guild count using discordlists.py (BotBlock)
        """
        try:
            result = await self.api.post_count()
        except Exception as e:
            await ctx.send("Request failed: `{}`".format(e))
            return

        print(result)
        await ctx.send("Successfully manually posted server count ({:,}) to {:,} lists."
                       "\nFailed to post server count to {} lists.".format(self.api.server_count,
                                                                             len(result["success"].keys()),
                                                                             len(result["failure"].keys())))


def setup(bot):
    bot.add_cog(DEL(bot))