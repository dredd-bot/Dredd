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
import config
import asyncpg
import asyncio
import aiohttp
import logging
import traceback
from discord.ext import commands
from db import emotes
from utils.caches import cache, CacheManager
from logging.handlers import RotatingFileHandler

# this section is for the new gateway (latest discord.py version)
intents = discord.Intents.default()
intents.members = True
intents.presences = False

asyncio.set_event_loop(asyncio.SelectorEventLoop())

async def run():
    description = "A bot written in Python that uses asyncpg to connect to a postgreSQL database."

    # NOTE: 127.0.0.1 is the loopback address. If your db is running on the same machine as the code, this address will work
    db = await asyncpg.create_pool(**config.DB_CONN_INFO)

    bot = Bot(description=description, db=db)
    if not hasattr(bot, 'uptime'):
        bot.uptime = datetime.datetime.now()
    try:
        await cache(bot)
        bot.session = aiohttp.ClientSession(loop=bot.loop)
        await bot.start(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        await db.close()
        await bot.logout()

async def get_prefix(bot, message):
    if not message.guild:
        if await bot.is_booster(message.author):
            cprefix = bot.boosters[message.author.id]['custom_prefix']
            custom_prefix = [cprefix, '!']
            return custom_prefix
        else:
            custom_prefix = ['!']
            return custom_prefix
    elif message.guild:
        try:
            prefix = bot.prefixes[message.guild.id]
            if not await bot.is_admin(message.author) and not await bot.is_booster(message.author):
                custom_prefix = prefix
                return commands.when_mentioned_or(custom_prefix)(bot, message)
            elif await bot.is_admin(message.author) and await bot.is_booster(message.author):
                booster_prefix = bot.boosters[message.author.id]['custom_prefix']
                custom_prefix = [booster_prefix, prefix, 'd ']
                return commands.when_mentioned_or(*custom_prefix)(bot, message)
            elif await bot.is_admin(message.author):
                custom_prefix = ['d ', prefix]
                return commands.when_mentioned_or(*custom_prefix)(bot, message)
            elif await bot.is_booster(message.author):
                cprefix = bot.boosters[message.author.id]['custom_prefix']
                custom_prefix = [cprefix, prefix]
                return commands.when_mentioned_or(*custom_prefix)(bot, message)
        except TypeError:
            return
    else:
        return

class EditingContext(commands.Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def send(self, content=None, *, tts=False, embed=None, file=None, files=None, delete_after=None, nonce=None, allowed_mentions=discord.AllowedMentions.none()):
        if file or files:
            return await super().send(content=content, tts=tts, embed=embed, file=file, files=files, delete_after=delete_after, nonce=nonce, allowed_mentions=allowed_mentions)
        reply = None
        try:
            reply = self.bot.cmd_edits[self.message.id]
        except KeyError:
            pass
        if reply:
            try:
                return await reply.edit(content=content, embed=embed, delete_after=delete_after, allowed_mentions=allowed_mentions)
            except:
                return
        msg = await super().send(content=content, tts=tts, embed=embed, file=file, files=files, delete_after=delete_after, nonce=nonce, allowed_mentions=allowed_mentions)
        self.bot.cmd_edits[self.message.id] = msg
        return msg


class Bot(commands.AutoShardedBot):
    def __init__(self, **kwargs):
        super().__init__(
            command_prefix = get_prefix,
            case_insensitive = True,
            owner_id = 345457928972533773,
            reconnect = True,
            chunk_guilds_at_startup=False,
            allowed_mentions = discord.AllowedMentions.none(),
            max_messages=10000,
            intents=intents)
        
        for extension in config.EXTENSIONS:
            try:
                self.load_extension(extension)
                print(f'[EXTENSION] {extension} was loaded successfully!')
            except Exception as e:
                tb = traceback.format_exception(type(e), e, e.__traceback__) 
                tbe = "".join(tb) + ""
                print(f'[WARNING] Could not load extension {extension}: {tbe}')

        self.db = kwargs.pop("db")
        self.counter = 0
        self.cmdUsage = {}
        self.cmdUsers = {}
        self.guildUsage = {}

        # self.embed_color = 0x0058D6 #0058D6
        # self.logembed_color = 0xD66060 #D66060
        # self.log_color = 0x1EA2B4 #1EA2B4
        # self.error_color = 0xD12312 #D12312
        # self.update_color = 0xCCE021 #CCE021
        # self.automod_color = 0xb54907 #b54907
        # self.logging_color = 0xE08C0B #E08C0B
        # self.memberlog_color = 0x55d655 #55d655
        # self.join_color = 0x0B145B #0B145B

        self.support = 'https://discord.gg/f3MaASW'
        self.invite = '<https://discord.com/oauth2/authorize?client_id=667117267405766696&scope=bot&permissions=477588727&redirect_uri=https%3A%2F%2Fdiscord.gg%2Ff3MaASW&response_type=code>'
        self.privacy = '<https://github.com/TheMoksej/Dredd/blob/master/PrivacyPolicy.md>'
        self.license = '<https://github.com/TheMoksej/Dredd/blob/master/LICENSE>'
        
        self.e = emotes
        self.config = config
        self.cache = CacheManager.get_cache
        self.cmd_edits = {}
        self.prefixes = {}
        self.vip_prefixes = {}

        self.guilds_data = {}
        self.loop = asyncio.get_event_loop()
        self.blacklisted_guilds = {}
        self.blacklisted_users = {}
        self.afk_users = []
        self.temp_timer = []
        self.temp_bans = []
        self.dm = {}
        self.user_badges = {}
        self.snipes = {}
        self.status_op_out = {}
        self.snipes_op_out = {}
        self.test_cache = {}

        self.automod = {}
        self.automod_actions = {}
        self.case_num = {}
        self.raidmode = {}
        self.moderation = {}
        self.joinlog = {}
        self.msgedit = {}
        self.msgdelete = {}
        self.joinmsg = {}
        self.leavemsg = {}
        self.antidehoist = {}
        self.memberupdate = {}
        self.masscaps = {}
        self.invites = {}
        self.massmentions = {}
        self.links = {}
        self.joinrole = {}
        self.mentionslimit = {}
        self.whitelisted_channels = {}
        self.whitelisted_roles = {}

        self.devs = {}
        self.admins = {}
        self.boosters = {}
        self.lockdown = 'False'

    def get(self, k, default=None):
        return super().get(k.lower(), default)

    def get_category(self, name):
        return self.categories.get(name)

    async def is_owner(self, user):
        if CacheManager.get_cache(self, user.id, 'devs'):
            return True
    
    async def is_admin(self, user):
        if await self.is_owner(user):
            return True
        if CacheManager.get_cache(self, user.id, 'admins'):
            return True
    
    async def is_booster(self, user):
        if CacheManager.get_cache(self, user.id, 'boosters'):
            return True

    async def close(self):
        await self.session.close()
        await super().close()
    
    def create_task_and_count(self, coro):
        self.counter += 1

        async def do_stuff():
            await coro
            self.counter -= 1

        self.loop.create_task(do_stuff())

    async def on_message(self, message):
        if message.author.bot:
            return

        try:
            ctx = await self.get_context(message, cls=EditingContext)
            if ctx.valid:
                msg = await self.invoke(ctx)
        except:
            return

    async def on_message_edit(self, before, after):

        if before.author.bot:
            return

        if after.content != before.content:
            try:
                ctx = await self.get_context(after, cls=EditingContext)
                if ctx.valid:
                    msg = await self.invoke(ctx)
            except discord.NotFound:
                return

    async def temp_punishment(self, guild: int, user: int, mod: int, reason: str, time, role: int, type: str):
        await self.db.execute("INSERT INTO moddata(guild_id, user_id, mod_id, reason, time, role_id, type) VALUES($1, $2, $3, $4, $5, $6, $7)", guild, user, mod, reason, time, role, type)

        self.temp_timer.append((guild, user, mod, reason, time, role, type))
    
    async def temp_ban_log(self, guild:int, user: int, mod: int, reason: str, time, type:str):
        await self.db.execute("INSERT INTO moddata(guild_id, user_id, mod_id, reason, time, role_id, type) VALUES($1, $2, $3, $4, $5, $6, $7)", guild, user, mod, reason, time, None, type)

        self.temp_bans.append((guild, user, mod, reason, time, type))
    
    async def log_temp_unmute(self, guild=None, mod=None, member=None, reason=None):
        check = await self.db.fetchval("SELECT * FROM moderation WHERE guild_id = $1", guild.id)

        if check is None:
            return
        elif check is not None:
            channel = await self.db.fetchval("SELECT channel_id FROM moderation WHERE guild_id = $1", guild.id)
            case = await self.db.fetchval("SELECT case_num FROM modlog WHERE guild_id = $1", guild.id)
            chan = self.get_channel(channel)

            if case is None:
                await self.db.execute("INSERT INTO modlog(guild_id, case_num) VALUES ($1, $2)", guild.id, 1)

            casenum = await self.db.fetchval("SELECT case_num FROM modlog WHERE guild_id = $1", guild.id)

            e = discord.Embed(color=self.logging_color, description=f"{emotes.log_memberedit} **{member}** unmuted `[#{casenum}]`")
            e.add_field(name="Previously muted by:", value=f"{mod} ({mod.id})", inline=False)
            e.add_field(name="Reason:", value=f"{reason}", inline=False)
            e.set_thumbnail(url=member.avatar_url_as(format='png'))
            e.set_footer(text=f"Member ID: {member.id}")

            await chan.send(embed=e)
            await self.db.execute("UPDATE modlog SET case_num = case_num + 1 WHERE guild_id = $1", guild.id)

loop = asyncio.get_event_loop()
loop.run_until_complete(run())
