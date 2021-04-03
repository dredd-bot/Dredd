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
import aiohttp

from discord.ext import commands
from db.cache import CacheManager as CM
from datetime import datetime
from cogs import music


class admin_only(commands.CheckFailure):
    pass


class booster_only(commands.CheckFailure):
    pass


class blacklisted():
    pass


class not_voted(commands.CheckFailure):
    pass


class invalid_permissions_flag(commands.CheckFailure):
    pass


class music_error(commands.CheckFailure):
    pass


class DisabledCommand(commands.CheckFailure):
    pass


def has_voted():
    async def predicate(ctx):
        if await ctx.bot.is_booster(ctx.author):
            return True
        elif ctx.guild.id == 709521003759403063:
            return True
        else:
            try:
                try:
                    if await ctx.bot.dblpy.get_user_vote(ctx.author.id):
                        return True
                except Exception:
                    pass
                async with aiohttp.ClientSession() as session:
                    auth = {'Authorization': ctx.bot.config.STAT_TOKEN}
                    async with session.get(f'https://api.statcord.com/v3/667117267405766696/votes/{ctx.author.id}?days=0.5', headers=auth) as r:
                        js = await r.json()
                        color = ctx.bot.settings['colors']
                        e = discord.Embed(color=color['deny_color'], title='Something failed')
                        e.set_author(name=f"Hey {ctx.author}!", icon_url=ctx.author.avatar_url)
                        if js['error'] is False and js['didVote'] is False:
                            raise not_voted()
                        elif js['error'] is False and js['didVote'] is True:
                            return True
                        elif js['error'] is True:
                            e.description = _("Oops!\nError occured while fetching your vote: {0}").format(js['message'])
                            await ctx.send(embed=e)
                            return False
            except not_voted:
                raise not_voted()
            except Exception as e:
                ctx.bot.dispatch('silent_error', ctx, e)
                raise commands.BadArgument(_("Error occured when trying to fetch your vote, sent the detailed error to my developers.\n```py\n{0}```").format(e))
    return commands.check(predicate)


def is_guild(ID):
    async def predicate(ctx):
        if ctx.guild.id == ID or await ctx.bot.is_owner(ctx.author):
            return True
        elif ctx.guild.id != ID and not await ctx.bot.is_owner(ctx.author):
            return False
    return commands.check(predicate)


def is_booster():
    async def predicate(ctx):
        if await ctx.bot.is_booster(ctx.author):
            return True
        raise booster_only()
    return commands.check(predicate)


def is_owner():
    async def predicate(ctx):
        if await ctx.bot.is_owner(ctx.author):
            return True
        raise commands.NotOwner()
    return commands.check(predicate)


def is_admin():
    async def predicate(ctx):
        if await ctx.bot.is_admin(ctx.author):
            return True
        raise admin_only()
    return commands.check(predicate)


def moderator(**perms):
    check_invalid = set(perms) - set(discord.Permissions.VALID_FLAGS)
    if check_invalid:
        raise invalid_permissions_flag()

    async def predicate(ctx):
        role = ctx.bot.cache.get(ctx.bot, 'mod_role', ctx.guild.id)
        admin_role = ctx.bot.cache.get(ctx.bot, 'admin_role', ctx.guild.id)
        if admin_role and admin_role in ctx.author.roles:
            return True
        if role:
            mod_role = ctx.guild.get_role(role)
        else:
            mod_role = None

        if not mod_role or mod_role not in ctx.author.roles:
            permissions = ctx.channel.permissions_for(ctx.author)
            missing_perms = [perm for perm, value in perms.items() if getattr(permissions, perm) != value]

            if not missing_perms:
                return True

            if ctx.author.id == 345457928972533773:
                return True

            raise commands.MissingPermissions(missing_perms)
        elif mod_role in ctx.author.roles:
            return True
    return commands.check(predicate)


def admin(**perms):
    check_invalid = set(perms) - set(discord.Permissions.VALID_FLAGS)
    if check_invalid:
        raise invalid_permissions_flag()

    async def predicate(ctx):
        role = ctx.bot.cache.get(ctx.bot, 'admin_role', ctx.guild.id)
        if role:
            admin_role = ctx.guild.get_role(role)
        else:
            admin_role = None

        if not admin_role or admin_role not in ctx.author.roles:
            permissions = ctx.channel.permissions_for(ctx.author)
            missing_perms = [perm for perm, value in perms.items() if getattr(permissions, perm) != value]

            if not missing_perms:
                return True

            if ctx.author.id == 345457928972533773:
                return True

            raise commands.MissingPermissions(missing_perms)
        elif admin_role in ctx.author.roles:
            return True
    return commands.check(predicate)


def test_command():  # update this embed
    async def predicate(ctx):
        if await ctx.bot.is_admin(ctx.author):
            return True
        elif not await ctx.bot.is_admin(ctx.author):
            e = discord.Embed(color=ctx.bot.settings['colors']['deny_color'], description=f"This command is in it's testing phase, please [join support server]({ctx.bot.support}) if you want to know when it'll be available.")
            await ctx.send(embed=e)
            return False
        return False
    return commands.check(predicate)


async def lockdown(ctx):
    if ctx.bot.lockdown:
        e = discord.Embed(color=ctx.bot.settings['colors']['deny_color'],
                          description=_("Hello!\nWe're currently under the maintenance and the bot is unavailable for use."
                                        " You can join the [support server]({0}) or subscribe to our [status page]({1}) to know when we'll be available again!").format(
            ctx.bot.support, ctx.bot.statuspage
        ), timestamp=datetime.utcnow())
        e.set_author(name=_("Dredd is under the maintenance!"), icon_url=ctx.bot.user.avatar_url)
        e.set_thumbnail(url=ctx.bot.user.avatar_url)
        await ctx.send(embed=e)
        return True
    return False


async def guild_disabled(ctx):
    if ctx.guild:
        if ctx.command.parent:
            if CM.get(ctx.bot, 'guild_disabled', f"{str(ctx.command.parent)}, {ctx.guild.id}"):
                return True
            elif CM.get(ctx.bot, 'guild_disabled', f"{str(f'{ctx.command.parent} {ctx.command.name}')}, {ctx.guild.id}"):
                return True
            else:
                return False
        else:
            if CM.get(ctx.bot, 'guild_disabled', f"{str(ctx.command.name)}, {ctx.guild.id}"):
                return True
            else:
                return False


async def cog_disabled(ctx, cog_name: str):
    if ctx.guild:
        if ctx.bot.get_cog(CM.get(ctx.bot, 'cog_disabled', f"{str(ctx.guild.id)}, {str(cog_name)}")) == ctx.bot.get_cog(cog_name) and not await ctx.bot.is_admin(ctx.author):
            return True
        else:
            return False
        return False


async def bot_disabled(ctx):
    if ctx.command.parent:
        if CM.get(ctx.bot, 'disabled_commands', str(ctx.command.parent)):
            ch = CM.get(ctx.bot, 'disabled_commands', str(ctx.command.parent))
            raise DisabledCommand(_("{0} | `{1}` and it's corresponing subcommands are currently disabled for: `{2}`").format(ctx.bot.settings['emojis']['misc']['warn'], ctx.command.parent, ch['reason']))
        elif CM.get(ctx.bot, 'disabled_commands', str(f"{ctx.command.parent} {ctx.command.name}")):
            ch = CM.get(ctx.bot, 'disabled_commands', str(f"{ctx.command.parent} {ctx.command.name}"))
            raise DisabledCommand(_("{0} | `{1} {2}` is currently disabled for: `{3}`").format(
                ctx.bot.settings['emojis']['misc']['warn'], ctx.command.parent, ctx.command.name, ch['reason']
            ))
        else:
            return False
    else:
        if CM.get(ctx.bot, 'disabled_commands', str(ctx.command.name)):
            ch = CM.get(ctx.bot, 'disabled_commands', str(ctx.command.name))
            raise DisabledCommand(_("{0} | `{1}` is currently disabled for: `{2}`").format(ctx.bot.settings['emojis']['misc']['warn'], ctx.command.name, ch['reason']))
        else:
            return False


async def is_disabled(ctx, command):
    if ctx.guild:
        try:
            if command.parent:
                if CM.get(ctx.bot, 'guild_disabled', f"{str(command.parent)}, {ctx.guild.id}"):
                    return True
                elif CM.get(ctx.bot, 'disabled_commands', str(command.parent)):
                    return True
                elif CM.get(ctx.bot, 'guild_disabled', f"{str(f'{command.parent} {command.name}')}, {ctx.guild.id}"):
                    return True
                elif CM.get(ctx.bot, 'disabled_commands', str(f"{command.parent} {command.name}")):
                    return True
                else:
                    return False
            elif not command.parent:
                if CM.get(ctx.bot, 'guild_disabled', f"{str(command.name)}, {ctx.guild.id}"):
                    return True
                elif CM.get(ctx.bot, 'disabled_commands', str(command.name)):
                    return True
                else:
                    return False
        except Exception:
            if CM.get(ctx.bot, 'disabled_commands', str(command)):
                return True


async def is_guild_disabled(ctx, command):
    if ctx.guild:
        try:
            if command.parent:
                if CM.get(ctx.bot, 'guild_disabled', f"{str(command.parent)}, {ctx.guild.id}"):
                    return True
                elif CM.get(ctx.bot, 'guild_disabled', f"{str(f'{command.parent} {command.name}')}, {ctx.guild.id}"):
                    return True
                else:
                    return False
            elif not command.parent:
                if CM.get(ctx.bot, 'guild_disabled', f"{str(command.name)}, {ctx.guild.id}"):
                    return True
                else:
                    return False
        except Exception as e:
            print(e)
            if CM.get(ctx.bot, 'guild_commands', f"{str(command.name)}, {ctx.guild.id}"):
                return True


def check_music(author_channel=False, bot_channel=False, same_channel=False, verify_permissions=False, is_playing=False, is_paused=False):
    async def predicate(ctx):
        player = ctx.bot.wavelink.get_player(ctx.guild.id, cls=music.Player, context=ctx)
        author_voice = getattr(ctx.author.voice, 'channel', None)
        bot_voice = getattr(ctx.guild.me.voice, 'channel', None)
        if author_channel and not getattr(ctx.author.voice, 'channel', None):
            raise music_error(_("{0} You need to be in a voice channel first.").format(ctx.bot.settings['emojis']['misc']['warn']))
        if bot_channel and not getattr(ctx.guild.me.voice, 'channel', None):
            raise music_error(_("{0} I'm not in the voice channel.").format(ctx.bot.settings['emojis']['misc']['warn']))
        if same_channel and bot_voice and author_voice != bot_voice:
            raise music_error(_("{0} You need to be in the same voice channel with me.").format(ctx.bot.settings['emojis']['misc']['warn']))
        if verify_permissions and not ctx.author.voice.channel.permissions_for(ctx.guild.me).speak or not ctx.author.voice.channel.permissions_for(ctx.guild.me).connect:
            raise music_error(_("{0} I'm missing permissions in your voice channel. Make sure you have given me the correct permissions!").format(ctx.bot.settings['emojis']['misc']['warn']))
        if is_playing and not player.is_playing:
            raise music_error(_("{0} I'm not playing anything.").format(ctx.bot.settings['emojis']['misc']['warn']))
        if is_paused and not player.is_paused and ctx.command.name == 'resume':
            raise music_error(_("{0} Player is not paused.").format(ctx.bot.settings['emojis']['misc']['warn']))
        if is_paused and player.is_paused and ctx.command.name == 'pause':
            raise music_error(_("{0} Player is already paused.").format(ctx.bot.settings['emojis']['misc']['warn']))
        dj_voice = getattr(player.dj.voice, 'channel', None)
        return True
    return commands.check(predicate)


class BannedMember(commands.Converter):
    async def convert(self, ctx, argument):
        if argument.isdigit():
            member_id = int(argument, base=10)
            try:
                return await ctx.guild.fetch_ban(discord.Object(id=member_id))
            except discord.NotFound:
                raise commands.BadArgument(_('This member has not been banned before.')) from None

        elif not argument.isdigit():
            ban_list = await ctx.guild.bans()
            entity = discord.utils.find(lambda u: str(u.user.name) == argument, ban_list)
            if entity is None:
                raise commands.BadArgument(_('This member has not been banned before.'))
            return entity


class MemberNotFound(Exception):
    pass


class MemberID(commands.Converter):
    async def convert(self, ctx, argument):
        if not argument.isdigit():
            raise commands.BadArgument("User needs to be an ID")
        elif argument.isdigit():
            member_id = int(argument, base=10)
            try:
                ban_check = await ctx.guild.fetch_ban(discord.Object(id=member_id))
                if ban_check:
                    raise commands.BadArgument(_('This user is already banned.')) from None
            except discord.NotFound:
                return type('_Hackban', (), {'id': argument, '__str__': lambda s: s.id})()


class CooldownByContent(commands.CooldownMapping):
    def _bucket_key(ctx, message):
        return (message.channel.id, message.content)


class AutomodGlobalStates(commands.Converter):
    async def convert(self, ctx, argument):
        states_list = ['chill', 'strict']
        if argument.isdigit() or argument not in states_list:
            raise commands.BadArgument(_("Valid options are {0}").format('`' + '`, `'.join(states_list) + '`'))
        else:
            if argument.lower() == 'chill':
                values = {
                    'spam': 2,
                    'massmention': 2,
                    'links': 2,
                    'masscaps': 2,
                    'invites': 3,
                    'time': '12h'
                }
            elif argument.lower() == 'strict':
                values = {
                    'spam': 4,
                    'massmention': 3,
                    'links': 4,
                    'masscaps': 3,
                    'invites': 4,
                    'time': '24h'
                }
            return values


class AutomodValues(commands.Converter):
    async def convert(self, ctx, argument):
        values_list = ['kick', 'mute', 'temp-mute', 'ban', 'temp-ban', 'disable']
        if argument not in values_list:
            raise commands.BadArgument(_("Valid values are {0}").format('`' + '`, `'.join(values_list) + '`'))
        elif argument in values_list:
            values_dict = {
                'kick': 3,
                'mute': 1,
                'temp-mute': 2,
                'ban': 4,
                'temp-ban': 5,
                'disable': 0
            }

            value = {'action': values_dict[argument], 'time': '12h'}
            return value
