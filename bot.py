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
import asyncpg
import config
import datetime
import aiohttp
import logging
import sys
import psutil
import sr_api
import async_cleverbot as ac


from discord.ext import commands
from db.cache import LoadCache, CacheManager
from utils import i18n
from cogs.music import Player
from collections import Counter
from logging.handlers import RotatingFileHandler

if sys.version_info < (3, 5, 3):
    raise Exception('Your python is outdated. Please update to at least 3.5.3')


logger = logging.getLogger('wavelink.player')  # cause music keeps crashing randomly
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    filename='.logs/discord_voice.log',
    encoding='utf-8',
    mode='w',
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    delay=0
)
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


async def run():
    description = "A bot written in Python that uses asyncpg to connect to a postgreSQL database."

    # NOTE: 127.0.0.1 is the loopback address. If your db is running on the same machine as the code, this address will work
    db = await asyncpg.create_pool(**config.DB_CONN_INFO)

    bot = Bot(description=description, db=db)
    if not hasattr(bot, 'uptime'):
        bot.uptime = datetime.datetime.now()
    try:
        await LoadCache.start(bot)
        bot.session = aiohttp.ClientSession(loop=bot.loop)
        # await bot.start(config.DISCORD_TOKEN)
        await bot.start(config.MAIN_TOKEN)
    except KeyboardInterrupt:
        await db.close()
        await bot.logout()


async def get_prefix(bot, message):
    if bot.user.id == 663122720044875796:  # for beta, so I don't accidentally kill both bots
        custom_prefix = ['rw ', 'db ']
        return commands.when_mentioned_or(*custom_prefix)(bot, message)
    if message.guild:
        prefix = bot.prefix[message.guild.id]
    elif not message.guild:
        prefix = '!'
    custom_prefix = [prefix]
    if await bot.is_booster(message.author):
        boosters_prefix = CacheManager.get(bot, 'boosters', message.author.id) or 'dredd '
        custom_prefix.append(boosters_prefix)
    if await bot.is_admin(message.author):
        custom_prefix.append('d ')

    return commands.when_mentioned_or(*custom_prefix)(bot, message)


class EditingContext(commands.Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def send(self, content=None, *, tts=False, embed=None, file=None, files=None, delete_after=None, nonce=None, allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False, replied_user=True)):
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
            except discord.errors.NotFound:  # Message was deleted
                pass
        reference = self.message.reference
        if reference and isinstance(reference.resolved, discord.Message):
            msg = await reference.resolved.reply(content=content, tts=tts, embed=embed, file=file, files=files, delete_after=delete_after, nonce=nonce, allowed_mentions=allowed_mentions)
        else:
            msg = await super().send(content=content, tts=tts, embed=embed, file=file, files=files, delete_after=delete_after, nonce=nonce, allowed_mentions=allowed_mentions)
        self.bot.cmd_edits[self.message.id] = msg
        return msg


class Bot(commands.AutoShardedBot):
    def __init__(self, **kwargs):
        super().__init__(
            command_prefix=get_prefix,
            case_insensitive=True,
            # case_insensitive_prefix=True,
            status=discord.Status.dnd,
            activity=discord.Activity(type=discord.ActivityType.competing, name='a boot up challenge'),
            owner_id=345457928972533773,
            reconnect=True,
            allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False, replied_user=True),
            max_messages=10000,
            chunk_guilds_at_startup=True,  # this is here for easy access. In case I need to switch it fast to False I won't need to look at docs.
            intents=discord.Intents(
                guilds=True,  # guild/channel join/remove/update
                members=True,  # member join/remove/update
                bans=True,  # member ban/unban
                emojis=False,  # emoji update
                integrations=False,  # integrations update
                webhooks=False,  # webhook update
                invites=False,  # invite create/delete
                voice_states=True,  # voice state update
                presences=False,  # member/user update for games/activities
                guild_messages=True,  # message create/update/delete
                dm_messages=True,  # message create/update/delete
                guild_reactions=True,  # reaction add/remove/clear
                dm_reactions=True,  # reaction add/remove/clear
                guild_typing=False,  # on typing
                dm_typing=False,  # on typing
            )
        )

        self.config = config

        for extension in config.EXTENSIONS:
            try:
                self.load_extension(extension)
                print(f'[EXTENSION] {extension} was loaded successfully!')
            except Exception as e:
                print(f'[WARNING] Could not load extension {extension}: {e}')

        self.db = kwargs.pop("db")
        self.cmdUsage = {}
        self.cmdUsers = {}
        self.guildUsage = {}
        self.process = psutil.Process()

        self.support = 'https://discord.gg/f3MaASW'
        self.invite = 'https://dredd-bot.xyz/invite'
        self.privacy = 'https://dredd-bot.xyz/privacy-policy'
        self.license = '<https://github.com/TheMoksej/Dredd/blob/master/LICENSE>'
        self.gif_pfp = 'https://cdn.discordapp.com/attachments/667077166789558288/747132112099868773/normal_3.gif'
        self.vote = '<https://discord.boats/bot/667117267405766696/vote>'
        self.source = '<https://github.com/TheMoksej/Dredd/>'
        self.statuspage = '<https://status.dredd-bot.xyz>'
        self.bot_lists = {'dbots': "[Discord Bot Labs](https://dbots.cc/dredd 'bots.discordlabs.org')", 'dboats': "[Discord Boats](https://discord.boats/bot/667117267405766696/vote 'discord.boats')",
                          'dbl': "[Discord Bot list](https://discord.ly/dredd/upvote 'discordbotlist.com')", 'shitgg': "[Top.GG](https://top.gg/bot/667117267405766696/vote 'top.gg')"}
        self.cleverbot = ac.Cleverbot(config.CB_TOKEN)
        self.join_counter = Counter()  # counter for anti raid so the bot would ban the user if they try to join more than 5 times in short time span

        self.cache = CacheManager
        self.cmd_edits = {}
        self.dm = {}
        self.dms = {}  # cache for checks if user was already informed about dm logging
        self.updates = {}
        self.snipes = {}
        self.sr_api = sr_api.Client()

        self.guilds_data = {}
        self.loop = asyncio.get_event_loop()
        self.guild_loop = {}
        self.to_dispatch = {}
        self.music_guilds = {}

        # ranks
        self.devs = {}
        self.admins = {}
        self.boosters = {}
        self.lockdown = False
        self.auto_reply = True
        self.settings = {}
        self.blacklist = {}
        self.check_duration = {}

        # guilds / moderation
        self.prefix = {}
        self.moderation = {}
        self.memberlog = {}
        self.joinlog = {}
        self.leavelog = {}
        self.guildlog = {}
        self.joinrole = {}
        self.joinmessage = {}
        self.leavemessage = {}
        self.messageedits = {}
        self.messagedeletes = {}
        self.antihoist = {}
        self.automod = {}
        self.massmention = {}
        self.masscaps = {}
        self.invites = {}
        self.links = {}
        self.spam = {}
        self.modlog = {}
        self.raidmode = {}
        self.temp_bans = {}
        self.temp_mutes = {}
        self.mute_role = {}
        self.mod_role = {}
        self.admin_role = {}
        self.channels_whitelist = {}
        self.roles_whitelist = {}
        self.guild_disabled = {}
        self.cog_disabled = {}
        self.case_num = {}
        self.rr = {}

        # other
        self.afk = {}
        self.status_op = {}
        self.snipes_op = {}
        self.nicks_op = {}
        self.badges = {}
        self.disabled_commands = {}
        self.translations = {}
        self.reminders = {}

    def get(self, k, default=None):
        return super().get(k.lower(), default)

    async def close(self):
        await self.session.close()
        await super().close()

    async def is_owner(self, user):
        return CacheManager.get(self, 'devs', user.id)

    async def is_admin(self, user):
        if CacheManager.get(self, 'devs', user.id):
            return True
        return CacheManager.get(self, 'admins', user.id)

    async def is_booster(self, user):
        if CacheManager.get(self, 'devs', user.id):
            return True
        return CacheManager.get(self, 'boosters', user.id)

    async def is_blacklisted(self, user):
        return CacheManager.get(self, 'blacklist', user.id)

    async def on_message(self, message):
        if message.author.bot:
            return
        try:
            ctx = await self.get_context(message, cls=EditingContext)
            if message.guild:
                i18n.current_locale.set(self.translations.get(message.guild.id, 'en_US'))
            if ctx.valid:
                await self.invoke(ctx)
        except Exception as e:
            print(e)
            return

    async def on_message_edit(self, before, after):

        if before.author.bot:
            return

        if after.content != before.content:
            try:
                ctx = await self.get_context(after, cls=EditingContext)
                if after.guild:
                    i18n.current_locale.set(self.translations.get(after.guild.id, 'en_US'))
                if ctx.valid:
                    await self.invoke(ctx)
            except discord.NotFound:
                return

    def music_player(self, **kwargs):
        ctx = kwargs.get('ctx')
        return self.wavelink.get_player(guild_id=ctx.guild.id, cls=Player)


loop = asyncio.get_event_loop()
loop.run_until_complete(run())
