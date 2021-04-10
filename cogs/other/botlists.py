import delpy
import statcord
import dbl
import discordlists
import asyncio
import discord
import json

from discord.ext import commands, tasks
from utils.default import botlist_exception
from datetime import datetime, timedelta
from utils import default


class DiscordExtremeList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_stats.start()
        self.delapi = delpy.Client(bot, bot.config.DEL_TOKEN, loop=bot.loop)

        self.help_icon = ''
        self.big_icon = ''

    def cog_unload(self):
        self.update_stats.cancel()

    @tasks.loop(minutes=30.0)
    async def update_stats(self):
        try:
            await self.delapi.post_stats(guildCount=len(self.bot.guilds), shardCount=len(self.bot.shards))
        except Exception as e:
            await botlist_exception(self, 'Discord Extreme List', e)

    @update_stats.before_loop
    async def before_guild_delete(self):
        await self.bot.wait_until_ready()
        print("[BACKGROUND] Started posting guild count to DiscordExtremeList")


class DiscordLabs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.key = bot.config.STAT_TOKEN
        self.api = statcord.Client(self.bot, self.key, custom1=self.music, custom2=self.latency)
        self.api.start_loop()

        self.help_icon = ''
        self.big_icon = ''

    @commands.Cog.listener()
    async def on_command(self, ctx):
        if await self.bot.is_owner(ctx.author) or await self.bot.is_admin(ctx.author):
            return
        try:
            self.api.command_run(ctx)
        except Exception as e:
            await botlist_exception(self, 'Statcord', e)

    async def music(self):
        amount = []
        for res in self.bot.wavelink.players:
            now = datetime.utcnow()
            hours = now - timedelta(hours=24)
            if res in self.bot.music_guilds:
                if now - hours == self.bot.music_guilds[res]:
                    self.bot.music_guilds.pop(res)
                else:
                    continue
            amount.append(res)
            self.bot.music_guilds[res] = now

        return f"{len(amount)}"

    async def latency(self):
        return self.bot.latency * 1000


class ShitGG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.token = bot.config.DBL_TOKEN
        self.bot.dblpy = dbl.DBLClient(self.bot, self.token, webhook_path='/dblwebhook', webhook_auth=bot.config.DBL_password, webhook_port=5435, autopost=True)

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
        e.description = f"**{user}** has test voted for me on {datetime.now().__format__('%c')}"
        e.set_thumbnail(url="https://cdn.discordapp.com/attachments/638902095520464908/659611283443941376/upvote.png")
        e.set_footer(text=f'User ID: {user.id}')
        await c.send("A vote test has ran succesfully!", embed=e)

    @commands.Cog.listener()
    async def on_dbl_vote(self, data):
        channel = self.bot.get_channel(780066719645040651)
        user = await self.bot.fetch_user(int(data['user']))
        e = discord.Embed(title='Upvote received',
                          url="https://top.gg/bot/667117267405766696/vote",
                          color=0x5E82AC)
        e.set_author(name=user, icon_url=user.avatar_url)
        e.description = f"**{user}** has voted for me on {datetime.now().__format__('%c')}"
        e.set_thumbnail(url="https://cdn.discordapp.com/attachments/638902095520464908/659611283443941376/upvote.png")
        e.set_footer(text=f'User ID: {user.id}')
        await channel.send(embed=e)


class DiscordLists(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api = discordlists.Client(self.bot)
        self.api.set_auth("discord.bots.gg", bot.config.DBGG_TOKEN)
        self.api.set_auth("discord.boats", bot.config.DBOATS_TOKEN)
        self.api.set_auth("voidbots.net", bot.config.GLENN_TOKEN)
        self.api.set_auth("mythicalbots.xyz", bot.config.MYTH_TOKEN)
        self.api.set_auth("botsfordiscord.com", bot.config.BFD_TOKEN)
        self.api.set_auth("botlist.space", bot.config.BOTSPACE_TOKEN)
        self.api.set_auth("discordbots.co", bot.config.DISCORD_BOTS_TOKEN)
        self.api.set_auth('bladebotlist.xyz', bot.config.BBL_TOKEN)
        self.api.set_auth('blist.xyz', bot.config.BLIST_TOKEN)
        self.api.set_auth('space-bot-list.xyz', bot.config.SBL_TOKEN)
        self.api.set_auth('infinitybotlist.com', bot.config.INFINITY_TOKEN)
        self.api.start_loop()

        self.help_icon = ''
        self.big_icon = ''

    @commands.command(hidden=True)
    async def post(self, ctx):
        """
        Manually posts guild count using discordlists.py (BotBlock)
        """
        try:
            result = await self.api.post_count()
        except Exception as e:
            try:
                await ctx.send("Request failed: `{}`".format(e))
                return
            except Exception:
                s = default.traceback_maker(e, advance=False)
                print(s)
                return

        print(result['success'])
        await ctx.send("Successfully manually posted server count ({:,}) to {:,} lists."
                       "\nFailed to post server count to {} lists.".format(self.api.server_count,
                                                                           len(result["success"].keys()),
                                                                           len(result["failure"].keys())))
        if len(result['failure']) != 0:
            for item in result['failure']:
                await botlist_exception(self, item, result['failure'][item])
                await asyncio.sleep(5)


class Others(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.discordbotlist.start()
        self.discordservices.start()

        self.help_icon = ''
        self.big_icon = ''

    def cog_unload(self):
        self.discordbotlist.cancel()
        self.discordservices.cancel()

    @tasks.loop(minutes=30)
    async def discordbotlist(self):
        try:
            headers = {"Authorization": self.bot.config.DBLIST_TOKEN}
            data = {"guilds": len(self.bot.guilds), "users": sum([x.member_count for x in self.bot.guilds])}
            r = await self.bot.session.post('https://discordbotlist.com/api/v1/bots/667117267405766696/stats', headers=headers, data=data)
            response = await r.json()

            if response['success']:
                return
            elif not response['success']:
                raise Exception(response)
        except Exception as e:
            await botlist_exception(self, 'Discord Bot List', e)

    @tasks.loop(minutes=30)
    async def discordservices(self):
        headers = {"Authorization": self.bot.config.DSERVICES_TOKEN}
        data = {"servers": len(self.bot.guilds), "shards": len(self.bot.shards)}
        r = await self.bot.session.post('https://api.discordservices.net/bot/667117267405766696/stats', headers=headers, data=json.dumps(data))
        response = await r.json()
        if response['code'] != 200:
            await botlist_exception(self, 'Discord Services', response['message'])

    @discordbotlist.before_loop
    async def before_discordbotlist(self):
        await self.bot.wait_until_ready()
        print("[BACKGROUND] Started posting guild count to DiscordBotList")

    @discordservices.before_loop
    async def before_discordservices(self):
        await self.bot.wait_until_ready()
        print("[BACKGROUND] Started posting guild count to DiscordServices")


def setup(bot):
    bot.add_cog(DiscordExtremeList(bot))
    bot.add_cog(DiscordLabs(bot))
    bot.add_cog(ShitGG(bot))
    bot.add_cog(DiscordLists(bot))
    bot.add_cog(Others(bot))
