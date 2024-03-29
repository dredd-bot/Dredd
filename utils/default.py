"""
Dredd, discord bot
Copyright (C) 2022 Moksej
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

import timeago as timesince
import discord
import time
import traceback
import json
import aiohttp

from discord.ext import commands
from datetime import datetime, timezone
from utils.publicflags import UserFlags, BotFlags
from utils.btime import FutureTime
from contextlib import suppress
from utils import logger, enums
from json.decoder import JSONDecodeError
from typing import Union, List, Optional


def timeago(target):
    return timesince.format(target)


def timetext(name):
    return f"{name}_{int(time.time())}.txt"


def date(target, clock=True):
    if clock is False:
        return target.strftime("%d %B %Y")
    return target.strftime("%d %B %Y, %H:%M")


def responsible(target, reason):
    responsible = f"{target} -"
    if reason is None:
        return f"{responsible} no reason."
    return f"{responsible} {reason}"


def traceback_maker(err, advance: bool = True):
    _traceback = ''.join(traceback.format_tb(err.__traceback__))
    error = '```py\n{1}{0}: {2}\n```'.format(type(err).__name__, _traceback, err)
    return error if advance else f"{type(err).__name__}: {err}"


async def background_error(ctx, err_type, err_msg, guild, channel):
    message = f"{ctx.bot.settings['emojis']['misc']['error']} **Error occured on event -** " \
              f"{err_type}"
    e = discord.Embed(color=ctx.bot.settings['colors']['error_color'], timestamp=datetime.now(timezone.utc))
    e.description = traceback_maker(err_msg)
    e.add_field(name="Server it occured in:", value=f"**Server:** {guild} ({guild.id})\n"
                                                    f"**Channel:** #{channel} ({'' if not channel else channel.id})")
    channel = ctx.bot.get_channel(ctx.bot.settings['channels']['event-errors'])
    return await channel.send(content=message, embed=e)


async def botlist_exception(ctx, botlist, error):
    channel = ctx.bot.get_channel(ctx.bot.settings['channels']['event-errors'])
    message = f"**Error occured when posting stats:**\n\n**Bot List:** {botlist}\n```py\n{error}```"
    await channel.send(content=message)


def next_level(ctx):
    if str(ctx.guild.premium_tier) == "0":
        count = int(2 - ctx.guild.premium_subscription_count)
        txt = _('Next level in **{0}** boosts').format(count)
        return txt

    if str(ctx.guild.premium_tier) == "1":
        count = int(7 - ctx.guild.premium_subscription_count)
        txt = _('Next level in **{0}** boosts').format(count)
        return txt

    if str(ctx.guild.premium_tier) == "2":
        count = int(14 - ctx.guild.premium_subscription_count)
        txt = _('Next level in **{0}** boosts').format(count)
        return txt

    if str(ctx.guild.premium_tier) == "3":
        txt = 'Guild is boosted to its max level'
        return txt


async def public_flags(ctx, user):
    bot = ctx.bot
    badges = {
        'discord_employee': f"{bot.settings['emojis']['badges']['staff']}",
        'discord_partner': f"{bot.settings['emojis']['badges']['partner']}",
        'hs_events': f"{bot.settings['emojis']['badges']['events']}",
        'hs_bravery': f"{bot.settings['emojis']['badges']['bravery']}",
        'hs_brilliance': f"{bot.settings['emojis']['badges']['brilliance']}",
        'hs_balance': f"{bot.settings['emojis']['badges']['balance']}",
        'bug_hunter_lvl1': f"{bot.settings['emojis']['badges']['hunter~1']}",
        'bug_hunter_lvl2': f"{bot.settings['emojis']['badges']['hunter~2']}",
        'verified_dev': f"{bot.settings['emojis']['badges']['developer']}",
        'early_supporter': f"{bot.settings['emojis']['badges']['early']}",
        'verified_bot': f"{bot.settings['emojis']['badges']['verified-bot']}",
        'certified_mod': f"{bot.settings['emojis']['badges']['certified-mod']}"
    }

    flag_vals = UserFlags((await ctx.bot.http.get_user(user.id))['public_flags'])
    badge_list = [value for i, value in badges.items() if i in [*flag_vals]]
    return " ".join(badge_list)


def region_flags(ctx):
    flags = {
        'brazil': ":flag_br:",
        "europe": ":flag_eu:",
        "hongkong": ":flag_hk:",
        "japany": ":flag_jp:",
        "russia": ":flag_ru:",
        "singapore": ":flag_sg:",
        "southafrica": ":flag_za:",
        "sydney": ":flag_au:",
        "us-central": ":flag_us:",
        "us-west": ":flag_us:",
        "us-east": ":flag_us:",
        "us-south": ":flag_us:",
        "india": ":flag_in:"
    }

    try:
        return f"{flags[str(ctx.guild.region)]} {str(ctx.guild.region).title()}"
    except KeyError:
        return f"{str(ctx.guild.region).title()}"


# noinspection PyUnboundLocalVariable
async def medias(ctx, user):
    medias = []
    for media in await ctx.bot.db.fetch("SELECT * FROM media WHERE user_id = $1", user.id):
        try:
            if media['type']:
                raise Exception()  # so the except statement triggers.
            icon = ctx.bot.settings['emojis']['social'][media['media_type']]
            title = media['media_type']
        except Exception:
            title = media['media_type']
            tp = media['type']
            if tp:
                if tp == 1:
                    icon = ctx.bot.settings['emojis']['social']['discord']
                elif tp == 2:
                    icon = ctx.bot.settings['emojis']['social']['instagram']
                elif tp == 3:
                    icon = ctx.bot.settings['emojis']['social']['twitch']
                elif tp == 4:
                    icon = ctx.bot.settings['emojis']['social']['twitter']
                elif tp == 5:
                    icon = ctx.bot.settings['emojis']['social']['github']
                elif tp == 6:
                    icon = ctx.bot.settings['emojis']['social']['spotify']
                elif tp == 7:
                    icon = ctx.bot.settings['emojis']['social']['youtube']
            else:
                icon = ''
        medias.append(f"{icon} [{title}]({media['media_link']})\n")

    if len(medias) > 10:
        medias = medias[10]
        medias.append('limit reached (10)')  # type: ignore

    return ''.join(medias)


def bot_acknowledgements(ctx, result, simple=False):
    badges = ctx.bot.cache.get(ctx.bot, 'badges', result.id)

    yes_badges = {
        "bot_owner": f"{ctx.bot.settings['emojis']['ranks']['bot_owner']} " + _("Owner of Dredd"),
        "bot_admin": f"{ctx.bot.settings['emojis']['ranks']['bot_admin']} " + _("Admin of Dredd"),
        "verified": f"{ctx.bot.settings['emojis']['ranks']['verified']} " + _("Staff member in the [support server]({0}) or Dredd's contributor").format(ctx.bot.support),
        "translator": f"{ctx.bot.settings['emojis']['ranks']['translator']} " + _("Dredd's Translator"),
        "sponsor": f"{ctx.bot.settings['emojis']['ranks']['sponsor']} " + _("Dredd's Sponsor"),
        "donator": f"{ctx.bot.settings['emojis']['ranks']['donator']} " + _("Booster of [Dredd's support server]({0}) or Donator").format(ctx.bot.support),
        "bot_partner": f"{ctx.bot.settings['emojis']['ranks']['bot_partner']} " + _("Dredd's Partner"),
        "bug_hunter_lvl1": f"{ctx.bot.settings['emojis']['ranks']['bug_hunter_lvl1']} " + _("Dredd Bug Hunter"),
        "bug_hunter_lvl2": f"{ctx.bot.settings['emojis']['ranks']['bug_hunter_lvl2']} " + _("Dredd BETA Bug Hunter"),
        "early": f"{ctx.bot.settings['emojis']['ranks']['early']} " + _("Dredd Early Supporter"),
        "early_supporter": f"{ctx.bot.settings['emojis']['ranks']['early_supporter']} " + _("Dredd Super Early Supporter"),
        "blocked": f"{ctx.bot.settings['emojis']['ranks']['blocked']} " + _("Blacklisted user"),
        "duck": "🦆 " + _("A special badge for Duck :duck:")
    }

    no_badges = {
        "bot_owner": f"{ctx.bot.settings['emojis']['ranks']['bot_owner']} ",
        "bot_admin": f"{ctx.bot.settings['emojis']['ranks']['bot_admin']} ",
        "verified": f"{ctx.bot.settings['emojis']['ranks']['verified']} ",
        "translator": f"{ctx.bot.settings['emojis']['ranks']['translator']} ",
        "sponsor": f"{ctx.bot.settings['emojis']['ranks']['sponsor']} ",
        "donator": f"{ctx.bot.settings['emojis']['ranks']['donator']} ",
        "bot_partner": f"{ctx.bot.settings['emojis']['ranks']['bot_partner']} ",
        "bug_hunter_lvl1": f"{ctx.bot.settings['emojis']['ranks']['bug_hunter_lvl1']} ",
        "bug_hunter_lvl2": f"{ctx.bot.settings['emojis']['ranks']['bug_hunter_lvl2']} ",
        "early": f"{ctx.bot.settings['emojis']['ranks']['early']} ",
        "early_supporter": f"{ctx.bot.settings['emojis']['ranks']['early_supporter']} ",
        "blocked": f"{ctx.bot.settings['emojis']['ranks']['blocked']} ",
        "duck": "🦆"
    }
    if not badges:
        return

    badge = []
    flags = BotFlags(badges)
    for i, value in yes_badges.items():
        if i in [*flags]:
            if not simple:
                badge.append(value + "\n")
            else:
                badge.append(no_badges[i])
    return ''.join(badge)


def server_badges(ctx, result):
    badges = ctx.bot.cache.get(ctx.bot, 'badges', result.id)

    the_badges = {
        'bot_admin': _("{0} Dredd Staff Server").format(ctx.bot.settings['emojis']['ranks']['bot_admin']),
        'verified': _("{} Dredd Verified Server").format(ctx.bot.settings['emojis']['ranks']['verified']),
        'server_partner': _("{0} Dredd Partnered Server").format(ctx.bot.settings['emojis']['ranks']['server_partner']),
        'duck': "🦆 Duck's Server"
    }

    if badges:
        flags = BotFlags(badges)
        badge = [value for i, value in the_badges.items() if i in [*flags]]
    else:
        return

    return '\n'.join(badge)


# noinspection PyUnusedLocal
def badge_values(ctx=None) -> dict:
    return {
        'bot_owner': 1,
        'bot_admin': 2,
        'bot_partner': 4,
        'server_partner': 8,
        'bug_hunter_lvl1': 16,
        'bug_hunter_lvl2': 32,
        'verified': 64,
        'sponsor': 128,
        'donator': 256,
        'early': 512,
        'early_supporter': 1024,
        'blocked': 2048,
        'duck': 4096,
        'translator': 8192,
        'all': -1
    }


# noinspection PyUnusedLocal
def permissions_converter(ctx, permissions):
    if not permissions:
        return None

    return [permission.replace('_', ' ').title() for permission in permissions]


async def execute_temporary(ctx, action, user, mod, guild, role, duration, reason):
    if isinstance(duration, FutureTime):
        duration = duration.dt.replace(tzinfo=None)

    if action == 1:
        await ctx.bot.db.execute("INSERT INTO modactions(time, user_id, action, guild_id, mod_id, role_id, reason) VALUES($1, $2, $3, $4, $5, $6, $7)", None if duration is None else duration, user.id, action, guild.id,
                                 mod.id, role.id, reason)
        if duration:
            ctx.bot.temp_mutes[f"{user.id}, {guild.id}"] = {'time': duration, 'reason': reason, 'role': role.id, 'moderator': mod.id}
        else:
            ctx.bot.mutes[f"{user.id}, {guild.id}"] = {'reason': reason, 'role': role.id, 'moderator': mod.id}
    elif action == 2:
        await ctx.bot.db.execute("INSERT INTO modactions(time, user_id, action, guild_id, mod_id, role_id, reason) VALUES($1, $2, $3, $4, $5, $6, $7)", None if duration is None else duration, user.id, action, guild.id,
                                 mod.id, None, reason)
        if duration:
            ctx.bot.temp_bans[f"{user.id}, {guild.id}"] = {'time': duration, 'reason': reason, 'moderator': mod.id}
        else:
            ctx.bot.bans[f"{user.id}, {guild.id}"] = {'reason': reason, 'moderator': mod.id}


async def execute_untemporary(ctx, action, user, guild):
    await ctx.bot.db.execute("DELETE FROM modactions WHERE user_id = $1 AND guild_id = $2", user.id, guild.id)
    if action == 1:
        ctx.bot.temp_mutes.pop(f"{user.id}, {guild.id}", None)
        ctx.bot.mutes.pop(f"{user.id}, {guild.id}", None)
    elif action == 2:
        ctx.bot.temp_bans.pop(f"{user.id}, {guild.id}", None)
        ctx.bot.bans.pop(f"{user.id}, {guild.id}", None)


# noinspection PyUnboundLocalVariable,PyUnusedLocal
async def get_muterole(ctx, guild, error=False):
    custom = guild.data.muterole

    if custom:
        muterole = guild.get_role(custom)
        if not muterole:
            custom = None

    if not custom:
        muterole = discord.utils.find(lambda r: r.name.lower() == "muted", guild.roles)
        if muterole is None and not error:
            return None
        elif not muterole and error:
            raise commands.RoleNotFound('muted')

    return muterole


def server_logs(ctx, server, simple=True):  # sourcery no-metrics
    server_data = server.data
    moderation = server_data.moderation  # ctx.bot.cache.get(ctx.bot, 'moderation', server.id)
    memberlog = server_data.memberlog  # ctx.bot.cache.get(ctx.bot, 'memberlog', server.id)
    joinlog = server_data.joinlog  # ctx.bot.cache.get(ctx.bot, 'joinlog', server.id)
    leavelog = server_data.leavelog  # ctx.bot.cache.get(ctx.bot, 'leavelog', server.id)
    joinmsg = server_data.joinmessage  # ctx.bot.cache.get(ctx.bot, 'joinmessage', server.id)
    leavemsg = server_data.leavemessage  # ctx.bot.cache.get(ctx.bot, 'leavemessage', server.id)
    guildlog = server_data.guildlog  # ctx.bot.cache.get(ctx.bot, 'guildlog', server.id)
    msgedits = server_data.messageedit  # ctx.bot.cache.get(ctx.bot, 'messageedits', server.id)
    msgdeletes = server_data.messagedelete  # ctx.bot.cache.get(ctx.bot, 'messagedeletes', server.id)
    antihoist = server_data.antihoist  # ctx.bot.cache.get(ctx.bot, 'antihoist', server.id)
    automod = server_data.automod  # ctx.bot.cache.get(ctx.bot, 'automod', server.id)
    raidmode = server_data.raidmode  # ctx.bot.cache.get(ctx.bot, 'raidmode', server.id)
    disabled = ctx.bot.settings['emojis']['misc']['disabled']
    enabled = ctx.bot.settings['emojis']['misc']['enabled']
    joinrole = server_data.joinrole  # ctx.bot.cache.get(ctx.bot, 'joinrole', server.id)

    logs = _("{0} Edited messages\n").format(f'{disabled}' if msgedits is None else f'{enabled}')
    logs += _("{0} Deleted messages\n").format(f'{disabled}' if msgdeletes is None else f'{enabled}')
    logs += _("{0} Moderation\n").format(f'{disabled}' if moderation is None else f'{enabled}')
    logs += _("{0} Guild logs\n").format(f'{disabled}' if guildlog is None else f'{enabled}')
    logs += _("{0} Member Joins\n").format(f'{disabled}' if joinlog is None else f'{enabled}')
    logs += _("{0} Member Leaves\n").format(f'{disabled}' if leavelog is None else f'{enabled}')
    logs += _("{0} Member Updates\n").format(f'{disabled}' if memberlog is None else f'{enabled}')
    if simple:
        logs += _("{0} Raid mode\n").format(f'{disabled}' if raidmode is None else f'{enabled}')
        logs += _("{0} Welcoming messages\n").format(f'{disabled}' if joinmsg is None else f'{enabled}')
        logs += _("{0} Leaving messages\n").format(f'{disabled}' if leavemsg is None else f'{enabled}')
        logs += _("{0} Role on Join\n").format(f'{disabled}' if joinrole is False else f'{enabled}')
        logs += _("{0} Dehoisting\n").format(f'{disabled}' if antihoist is None else f'{enabled}')
        logs += _("{0} Automod\n").format(f'{disabled}' if automod is None else f'{enabled}')
        return logs
    else:
        settings = _("{0} Raid mode\n").format(f'{disabled}' if raidmode is None else f'{enabled}')
        settings += _("{0} Welcoming messages\n").format(f'{disabled}' if joinmsg is None else f'{enabled}')
        settings += _("{0} Leaving messages\n").format(f'{disabled}' if leavemsg is None else f'{enabled}')
        settings += _("{0} Role on Join\n").format(f'{disabled}' if joinrole is False else f'{enabled}')
        settings += _("{0} Dehoisting\n").format(f'{disabled}' if antihoist is None else f'{enabled}')
        settings += _("{0} Automod\n").format(f'{disabled}' if automod is None else f'{enabled}')
        return {'logs': logs, 'settings': settings}


async def admin_tracker(ctx):
    e = discord.Embed(color=ctx.bot.settings['colors']['embed_color'], timestamp=datetime.now(timezone.utc))
    e.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
    e.title = "Admin command used"
    e.description = f"""
**Command:**\n{ctx.message.content}
**Guild:** {ctx.guild} ({ctx.guild.id})
**Channel:** #{ctx.channel.name} ({ctx.channel.id}) {ctx.channel.mention}"""
    channel = ctx.bot.get_channel(ctx.bot.settings['channels']['log-admins'])
    await channel.send(embed=e)


async def guild_data_deleted(ctx, guild_id):
    message = f"I left guild **{guild_id}** 30 days ago " \
              "and was never invited back. Thus why I'm resetting " \
              "their guild data now."
    log_channel = ctx.bot.get_channel(ctx.bot.settings['channels']['joins-leaves'])
    await log_channel.send(message)


async def auto_guild_leave(ctx, abusive_user, guild):
    notif_channel = ctx.bot.get_channel(ctx.bot.settings['channels']['joins-leaves'])
    moksej = ctx.bot.get_user(345457928972533773)

    e = discord.Embed(color=ctx.bot.settings['colors']['error_color'], timestamp=datetime.now(timezone.utc))
    e.set_author(name="Left guild forcefully", icon_url=guild.icon.url)
    e.description = f"""
Hey {guild.owner}!
Just wanted to let you know that I left your server: **{guild.name}** ({guild.id}) as one of your members ({abusive_user} - {abusive_user.id}) was abusing my commands in a channel I can't send messages in.

Since this leave was an automatic leave, you may invite me back, but if same action will occur multiple times, the server will get blacklisted."""
    msg = ''
    try:
        await guild.owner.send(embed=e)
        msg += f' I DMed the server owner ({guild.owner} ({guild.owner.id})) letting them know I\'ve left their server.'
    except Exception:
        msg += ' Unfortunately I wasn\'t able to DM the server owner ({guild.owner} ({guild.owner.id})) as they had their DMs off.'

    notif_message = f"{moksej.mention} I left {guild} as **{abusive_user}** ({abusive_user.id}) was " \
                    f"abusing my commands in a private channel.{msg}"
    all_mentions = discord.AllowedMentions(users=True, everyone=False, roles=False)
    await notif_channel.send(notif_message, allowed_mentions=all_mentions)
    await guild.leave()


async def find_user(ctx, user):
    user = user or ctx.author
    if isinstance(user, discord.User):
        pass
    elif isinstance(user, str):
        if not user.isdigit():
            return None
        try:
            user = await ctx.bot.fetch_user(user)
        except Exception:
            return None

    return user


async def change_theme(ctx, color: int, avatar: str, emoji: str):
    file = discord.File(f'avatars/{avatar}.png')
    newcolor = color

    message = await ctx.channel.send(file=file, delete_after=5)
    url = message.attachments[0].url
    with open('db/settings.json', 'r', encoding='utf8') as f:
        data = json.load(f)
    try:
        async with aiohttp.ClientSession() as c:
            async with c.get(url) as f:
                bio = await f.read()
        await ctx.bot.user.edit(avatar=bio)
        server = ctx.bot.get_guild(ctx.bot.settings['servers']['main'])
        await server.edit(icon=bio)
        data['colors']['embed_color'] = newcolor
        data['emojis']['avatars']['main'] = emoji
        data['banners']['default'] = data['banners'][avatar]
        embed = discord.Embed(color=newcolor,
                              description=f"Changed the theme to {avatar}!")
        embed.set_thumbnail(url=url)
        with open('db/settings.json', 'w') as f:
            json.dump(data, f, indent=4)
        LC = ctx.bot.cache_reload
        await LC.reloadall(ctx.bot)
        await ctx.send(embed=embed)
    except Exception as e:
        return await ctx.send(f"{ctx.bot.settings['emojis']['misc']['warn']} | **Error occured:** {e}")


async def blacklist_log(ctx, option: int, type: int, name, reason: str):
    log_channel = ctx.bot.get_channel(ctx.bot.settings['channels']['blacklist'])
    try:
        name_id = f" ({name.id})"
    except Exception:
        name_id = ''
    await log_channel.send(f"**{name}**{name_id} {'was blacklisted' if option == 0 else 'was unblacklisted'} from {'using the bot' if type == 0 else 'submitting suggestions' if type == 1 else 'sending DMs'} "
                           f"by **{ctx.author if name != ctx.author else ctx.bot.user}** for {reason}.")


async def global_cooldown(ctx) -> None:
    counter = ctx.bot.cache.get(ctx.bot, 'counter', ctx.author.id)

    if counter and counter >= 3:
        reason = 'automatic blacklist, global cooldown hit'
        query = """INSERT INTO blacklist(_id, type, reason, dev, issued, liftable)
                                VALUES($1, $2, $3, $4, $5, $6)
                                ON CONFLICT (_id) DO UPDATE
                                SET type = $2, reason = $3
                                WHERE blacklist._id = $1 """
        await ctx.bot.db.execute(query, ctx.author.id, 2, reason, ctx.bot.user.id, datetime.now(), 0)
        ctx.bot.blacklist[ctx.author.id] = {'type': 2, 'reason': reason, 'dev': ctx.bot.user.id, 'issued': datetime.now(), 'liftable': 0}
        await ctx.bot.db.execute("INSERT INTO badges(_id, flags) VALUES($1, $2)", ctx.author.id, 2048)
        ctx.bot.badges[ctx.author.id] = 2048
        await ctx.bot.db.execute("INSERT INTO bot_history(_id, action, dev, reason, issued, type, liftable) VALUES($1, $2, $3, $4, $5, $6, $7)", ctx.author.id, 1, ctx.bot.user.id, reason, datetime.now(), 2, 0)
        e = discord.Embed(color=ctx.bot.settings['colors']['deny_color'], title='Blacklist state updated!', timestamp=datetime.now(timezone.utc))
        e.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        e.description = f"Hey!\nI'm sorry, but your blacklist state was updated and you won't be able to use my commands anymore!\n**Reason:** {reason}" \
                        f"\nIf you wish to appeal, you can [join the support server]({ctx.bot.support})"
        with suppress(Exception):
            await ctx.author.send(embed=e)
        await blacklist_log(ctx, 0, 0, ctx.author, reason)
    else:
        ctx.bot.counter.update({ctx.author.id})
        ch = ctx.bot.get_channel(ctx.bot.settings['channels']['cooldowns'])
        await ch.send(f"{ctx.author} hit the global cooldown limit. They're now at {ctx.bot.counter[ctx.author.id]} hit(s)")


async def dm_reply(ctx, message):
    if len(message) < 3:
        message += '⠀' * (3 - len(message))
    elif len(message) > 60:
        message = message[:60]
    try:
        res = await ctx.bot.cleverbot.ask(message)
        return res.text
    except Exception as e:
        ctx.bot.dispatch('silent_error', ctx, e)
        ctx.bot.auto_reply = False
        message = "Chat bot would've replied to you but looks like he has ran away"
        return message


def automod_values(value) -> dict:
    values = {
        1: _('mute'),
        2: _('temp-mute'),
        3: _('kick'),
        4: _('ban'),
        5: _('temp-ban')
    }

    return values[value]


# noinspection PyUnboundLocalVariable
async def spotify_support(ctx, spotify, search_type, spotify_id, Track, queue: bool = True) -> Union[None, list]:  # sourcery no-metrics
    with suppress(ConnectionResetError, AttributeError, JSONDecodeError, discord.HTTPException):
        player = ctx.voice_client
        spotify_client = spotify.Client(ctx.bot.config.SPOTIFY_CLIENT, ctx.bot.config.SPOTIFY_SECRET)
        spotify_http_client = spotify.HTTPClient(ctx.bot.config.SPOTIFY_CLIENT, ctx.bot.config.SPOTIFY_SECRET)

        if search_type == "playlist":
            try:
                results = spotify.Playlist(client=spotify_client, data=await spotify_http_client.get_playlist(spotify_id))
                search_tracks = await results.get_all_tracks()
            except Exception:
                return await ctx.send(_("I was not able to find this playlist! Please try again or use a different link."))

        elif search_type == "album":
            try:
                results = await spotify_client.get_album(spotify_id=spotify_id)
                search_tracks = await results.get_all_tracks()
            except Exception:
                return await ctx.send(_("I was not able to find this album! Please try again or use a different link."))

        elif search_type == 'track':
            results = await spotify_client.get_track(spotify_id=spotify_id)
            search_tracks = [results]

        tracks = [
            Track('spotify',
                  {
                      'title': track.name or 'Unknown', 'author': ', '.join(artist.name for artist in track.artists) or 'Unknown',
                      'length': track.duration or 0, 'identifier': track.id or 'Unknown', 'uri': track.url or 'spotify',
                      'isStream': False, 'isSeekable': False, 'position': 0,
                  },
                  requester=ctx.author,
                  ) for track in search_tracks
        ]
        if queue:
            await logger.new_log(ctx.bot, time.time(), 4, len(tracks))
            if not tracks:
                return await ctx.send(_("The URL you put is either not valid or doesn't exist!"))

            if search_type == "playlist":
                for track in tracks:
                    player.queue.put_nowait(track)

                await ctx.send(_('{0} Added the playlist **{1}**'
                                 ' with {2} songs to the queue!').format('🎶', results.name, len(tracks)), delete_after=15)
            elif search_type == "album":
                for track in tracks:
                    player.queue.put_nowait(track)

                await ctx.send(_('{0} Added the album **{1}**'
                                 ' with {2} songs to the queue!').format('🎶', results.name, len(tracks)), delete_after=15)
            else:
                if player.is_playing():
                    await ctx.send(_('{0} Added **{1}** to the Queue!').format('🎶', tracks[0].title), delete_after=15)
                player.queue.put_nowait(tracks[0])

        await spotify_client.close()
        await spotify_http_client.close()
        if not queue:
            return tracks
        if not player.is_playing():
            await player.do_next()


def printRAW(*Text):
    with open(1, 'w', encoding='utf8', closefd=False) as RAWOut:
        print(*Text, file=RAWOut)
        RAWOut.flush()


def reaction_roles_dict_sorter(payload: List[enums.SelfRoles], message_author: enums.ReactionRolesAuthor, reaction_type: enums.ReactionRolesType) -> List[Union[enums.SelfRoles, dict]]:
    if message_author == int(enums.ReactionRolesAuthor.bot) and reaction_type == int(enums.ReactionRolesType.new_message):
        return payload
    return [{value["reaction"]: value["role"] for value in payload}]


def get_result(attr) -> Optional[dict]:
    return {"name": attr.name, "id": attr.id} if attr else None


def handle_request(bot, data):
    guild = bot.get_guild(data["guild_id"])
    user = guild.get_member(data["user_id"])
    g: DreddGuild = guild.data  # type: Ignore
    mod_channel = guild.get_channel(g.moderation)
    member_log = guild.get_channel(g.memberlog)
    guild_log = guild.get_channel(g.guildlog)
    join_log = guild.get_channel(g.joinlog)
    leave_log = guild.get_channel(g.leavelog)
    message_edit = guild.get_channel(g.messageedit)
    message_delete = guild.get_channel(g.messagedelete)
    mute_role = guild.get_role(g.muterole)
    mod_role = guild.get_role(g.modrole)
    admin_role = guild.get_role(g.adminrole)
    return json.dumps({
        "prefix": g.prefix,
        "language": g.language,
        "moderation": get_result(mod_channel),
        "member_log": get_result(member_log),
        "guild_log": get_result(guild_log),
        "joinlog": get_result(join_log),
        "leavelog": get_result(leave_log),
        "msgedit": get_result(message_edit),
        "msgdelete": get_result(message_delete),
        "mute_role": get_result(mute_role),
        "mod_role": get_result(mod_role),
        "admin_role": get_result(admin_role),
        "text_channels": [{"name": channel.name, "id": channel.id} for channel in guild.text_channels if channel.can_send],
        "roles": {
            "mute_roles": [
                {"name": role.name, "id": role.id} for role in guild.roles if role.position < guild.me.top_role.position and role.is_assignable()
                                                                              and not role.permissions.send_messages and role.id != g.joinrole
            ],
            "mod_roles": [
                {"name": role.name, "id": role.id} for role in guild.roles if role.position < guild.me.top_role.position and role.is_assignable()
                                                                              and role.permissions.manage_messages and role.id != g.joinrole
            ],
            "admin_roles": [
                {"name": role.name, "id": role.id} for role in guild.roles if role.position < guild.me.top_role.position and role.is_assignable()
                                                                              and role.permissions.ban_members and role.id != g.joinrole
            ],
            "join_roles": [
                {"name": role.name, "id": role.id} for role in guild.roles if role.position < guild.me.top_role.position and role.is_assignable()
                                                                              and role.id not in [g.modrole, g.adminrole, g.muterole]
            ]
        },
        "user_permissions": dict(user.guild_permissions)
    })


async def handle_database(bot, guild, table_name, attr, data) -> None:
    attr = getattr(bot, attr)
    table_name = table_name if table_name not in ["msgedit", "msgdelete"] else "messageedits" if table_name != "msgdelete" else "messagedeletes"
    insert_query = "INSERT INTO {table} VALUES($1, $2)".format(table=table_name)
    update_channel_query = "UPDATE {table} SET channel_id = $2 WHERE guild_id = $1".format(table=table_name)
    update_role_query = "UPDATE {table} SET role = $2 WHERE guild_id = $1".format(table=table_name)
    delete_query = "DELETE FROM {table} WHERE guild_id = $1".format(table=table_name)
    update_query = update_channel_query if table_name not in ['muterole', 'modrole', 'adminrole'] else update_role_query
    if int(data) != 1:
        query = insert_query if not attr.get(guild.id) else update_query
        x = await bot.db.execute(query, guild.id, int(data))
        attr[guild.id] = int(data)
    else:
        await bot.db.execute(delete_query, guild.id)
        attr.pop(guild.id, None)


async def handle_update(bot, data):
    try:
        g = bot.guild_cache(bot.get_guild(int(data['guild_id'])))
        correct_values = {
            "msgedit": "messageedits",
            "msgdelete": "messagedeletes",
            "muterole": "mute_role",
            "modrole": "mod_role",
            "adminrole": "admin_role"
        }
        for value in data:
            if value == 'prefix' and data['prefix'] != g.prefix:
                bot.prefix[g.id] = data['prefix']
                await bot.db.execute("UPDATE guilds SET prefix = $1 WHERE guild_id = $2", data['prefix'], g.id)
            elif value == 'language' and data['language'] != g.language:
                bot.translations[g.id] = data['language']
                await bot.db.execute("UPDATE guilds SET language = $1 WHERE guild_id = $2", data['language'], g.id)
            elif value not in ['prefix', 'language', 'guild_id']:
                attr_name = value if not correct_values.get(value) else correct_values.get(value)
                if data.get(value):
                    await handle_database(bot, g, value, attr_name, data.get(value))
    except Exception as e:
        return json.dumps({"error": "Error occured"})
