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

import timeago as timesince
import discord
import time
import traceback
import json
import aiohttp
import db.cache
import urllib

from discord.ext import commands

from utils.Nullify import clean
from datetime import datetime, timezone
from utils.publicflags import UserFlags, BotFlags
from discord.utils import escape_markdown
from utils.btime import human_timedelta, FutureTime


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
    error = ('```py\n{1}{0}: {2}\n```').format(type(err).__name__, _traceback, err)
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
        count = int(15 - ctx.guild.premium_subscription_count)
        txt = _('Next level in **{0}** boosts').format(count)
        return txt

    if str(ctx.guild.premium_tier) == "2":
        count = int(30 - ctx.guild.premium_subscription_count)
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
        'verified_bot': f"{bot.settings['emojis']['badges']['verified-bot']}"
    }

    badge_list = []
    flag_vals = UserFlags((await ctx.bot.http.get_user(user.id))['public_flags'])
    for i in badges.keys():
        if i in [*flag_vals]:
            badge_list.append(badges[i])

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


async def medias(ctx, user):
    medias = []
    for media in await ctx.bot.db.fetch("SELECT * FROM media WHERE user_id = $1", user.id):
        try:
            if not media['type']:
                icon = ctx.bot.settings['emojis']['social'][media['media_type']]
                title = media['media_type'].title()
            else:
                raise Exception()  # so the except statement triggers.
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
        medias.append('limit reached (10)')

    return ''.join(medias)


def bot_acknowledgements(ctx, result, simple=False):
    badges = db.cache.CacheManager.get(ctx.bot, 'badges', result.id)

    yes_badges = {
        "bot_owner": f"{ctx.bot.settings['emojis']['ranks']['bot_owner']} " + _("Owner of Dredd"),
        "bot_admin": f"{ctx.bot.settings['emojis']['ranks']['bot_admin']} " + _("Admin of Dredd"),
        "verified": f"{ctx.bot.settings['emojis']['ranks']['verified']} " + _("Staff member in the [support server]({0}) or Dredd's contributor").format(ctx.bot.support),
        "sponsor": f"{ctx.bot.settings['emojis']['ranks']['sponsor']} " + _("Dredd sponsor"),
        "donator": f"{ctx.bot.settings['emojis']['ranks']['donator']} " + _("Booster of [Dredd's support server]({0}) or Donator").format(ctx.bot.support),
        "bot_partner": f"{ctx.bot.settings['emojis']['ranks']['bot_partner']} " + _("Dredd Partner"),
        "bug_hunter_lvl1": f"{ctx.bot.settings['emojis']['ranks']['bug_hunter_lvl1']} " + _("Dredd Bug Hunter"),
        "bug_hunter_lvl2": f"{ctx.bot.settings['emojis']['ranks']['bug_hunter_lvl2']} " + _("Dredd BETA Bug Hunter"),
        "early": f"{ctx.bot.settings['emojis']['ranks']['early']} " + _("Dredd Early Supporter"),
        "early_supporter": f"{ctx.bot.settings['emojis']['ranks']['early_supporter']} " + _("Dredd super early supporter"),
        "blocked": f"{ctx.bot.settings['emojis']['ranks']['blocked']} " + _("Blacklisted user"),
        "duck": "🦆 " + _("A special badge for Duck :duck:")
    }

    no_badges = {
        "bot_owner": f"{ctx.bot.settings['emojis']['ranks']['bot_owner']} ",
        "bot_admin": f"{ctx.bot.settings['emojis']['ranks']['bot_admin']} ",
        "verified": f"{ctx.bot.settings['emojis']['ranks']['verified']} ",
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
    if badges:
        badge = []
        flags = BotFlags(badges)
        if not simple:
            for i in yes_badges.keys():
                if i in [*flags]:
                    badge.append(yes_badges[i] + "\n")
        else:
            for i in yes_badges.keys():
                if i in [*flags]:
                    badge.append(no_badges[i])
    else:
        return

    return ''.join(badge)


def server_badges(ctx, result):
    badges = db.cache.CacheManager.get(ctx.bot, 'badges', result.id)

    the_badges = {
        'bot_admin': _("{0} Dredd Staff Server").format(ctx.bot.settings['emojis']['ranks']['bot_admin']),
        'verified': _("{} Dredd Verified Server").format(ctx.bot.settings['emojis']['ranks']['verified']),
        'server_partner': _("{0} Dredd Partnered Server").format(ctx.bot.settings['emojis']['ranks']['server_partner'])
    }

    if badges:
        badge = []
        flags = BotFlags(badges)
        for i in the_badges.keys():
            if i in [*flags]:
                badge.append(the_badges[i])
    else:
        return

    return '\n'.join(badge)


def badge_values(ctx) -> dict:
    values = {
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
        'all': -1
    }

    return values


def permissions_converter(ctx, permissions):
    to_return = []
    if not permissions:
        return None

    for permission in permissions:
        to_return.append(permission.replace('_', ' ').title())

    return to_return


async def execute_temporary(ctx, action, user, mod, guild, role, duration, reason):
    if isinstance(duration, FutureTime):
        duration = duration.dt

    if action == 1:
        await ctx.bot.db.execute("INSERT INTO modactions(time, user_id, action, guild_id, mod_id, role_id, reason) VALUES($1, $2, $3, $4, $5, $6, $7)", None if duration is None else duration, user.id, action, guild.id, mod.id, role.id, reason)
        if not duration:
            return
        ctx.bot.temp_mutes[f"{user.id}, {guild.id}"] = {'time': duration, 'reason': reason, 'role': role.id, 'moderator': mod.id}
    elif action == 2:
        await ctx.bot.db.execute("INSERT INTO modactions(time, user_id, action, guild_id, mod_id, role_id, reason) VALUES($1, $2, $3, $4, $5, $6, $7)", None if duration is None else duration, user.id, action, guild.id, mod.id, None, reason)
        if not duration:
            return
        ctx.bot.temp_bans[f"{user.id}, {guild.id}"] = {'time': duration, 'reason': reason, 'moderator': mod.id}


async def execute_untemporary(ctx, action, user, guild):
    await ctx.bot.db.execute("DELETE FROM modactions WHERE user_id = $1 AND guild_id = $2", user.id, guild.id)
    if action == 1:
        ctx.bot.temp_mutes.pop(f"{user.id}, {guild.id}", None)
    elif action == 2:
        ctx.bot.temp_bans.pop(f"{user.id}, {guild.id}", None)


async def get_muterole(ctx, guild, error=False):
    custom = db.cache.CacheManager.get(ctx.bot, 'mute_role', guild.id)

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


def server_logs(ctx, server, simple=True):
    moderation = ctx.bot.cache.get(ctx.bot, 'moderation', server.id)
    memberlog = ctx.bot.cache.get(ctx.bot, 'memberlog', server.id)
    joinlog = ctx.bot.cache.get(ctx.bot, 'joinlog', server.id)
    leavelog = ctx.bot.cache.get(ctx.bot, 'leavelog', server.id)
    joinmsg = ctx.bot.cache.get(ctx.bot, 'joinmessage', server.id)
    leavemsg = ctx.bot.cache.get(ctx.bot, 'leavemessage', server.id)
    guildlog = ctx.bot.cache.get(ctx.bot, 'guildlog', server.id)
    msgedits = ctx.bot.cache.get(ctx.bot, 'messageedits', server.id)
    msgdeletes = ctx.bot.cache.get(ctx.bot, 'messagedeletes', server.id)
    antihoist = ctx.bot.cache.get(ctx.bot, 'antihoist', server.id)
    automod = ctx.bot.cache.get(ctx.bot, 'automod', server.id)
    raidmode = ctx.bot.cache.get(ctx.bot, 'raidmode', server.id)
    disabled = ctx.bot.settings['emojis']['misc']['disabled']
    enabled = ctx.bot.settings['emojis']['misc']['enabled']
    joinrole = ctx.bot.cache.get(ctx.bot, 'joinrole', server.id)

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
        logs += _("{0} Role on Join\n").format(f'{disabled}' if joinrole is None else f'{enabled}')
        logs += _("{0} Dehoisting\n").format(f'{disabled}' if antihoist is None else f'{enabled}')
        logs += _("{0} Automod\n").format(f'{disabled}' if automod is None else f'{enabled}')
        return logs
    elif not simple:
        settings = _("{0} Raid mode\n").format(f'{disabled}' if raidmode is None else f'{enabled}')
        settings += _("{0} Welcoming messages\n").format(f'{disabled}' if joinmsg is None else f'{enabled}')
        settings += _("{0} Leaving messages\n").format(f'{disabled}' if leavemsg is None else f'{enabled}')
        settings += _("{0} Role on Join\n").format(f'{disabled}' if joinrole is None else f'{enabled}')
        settings += _("{0} Dehoisting\n").format(f'{disabled}' if antihoist is None else f'{enabled}')
        settings += _("{0} Automod\n").format(f'{disabled}' if automod is None else f'{enabled}')
        return {'logs': logs, 'settings': settings}


async def admin_tracker(ctx):
    e = discord.Embed(color=ctx.bot.settings['colors']['embed_color'], timestamp=datetime.now(timezone.utc))
    e.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)
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
    e.set_author(name="Left guild forcefully", icon_url=guild.icon_url)
    e.description = f"""
Hey {guild.owner}!
Just wanted to let you know that I left your server: **{guild.name}** ({guild.id}) as one of your members ({abusive_user} - {abusive_user.id}) was abusing my commands in a channel I can't send messages in.
The user will most likely get blacklisted, even if it turns out they were maliciously doing that.

Since this leave was an automatic leave, you may invite me back, but if same action will occur multiple times, the server might get blacklisted."""
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
            data = json.dump(data, f, indent=4)
        LC = db.cache.LoadCache
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
    await log_channel.send(f"**{name}**{name_id} {'was blacklisted' if option == 0 else 'was unblacklisted'} from {'using the bot' if type == 0 else 'submitting suggestions' if type == 1 else 'sending DMs'} by **{ctx.author}** for {reason}.")


async def dm_reply(ctx, message):
    if len(message) < 3:
        message = message + ('⠀' * (3 - len(message)))
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


def automod_values(value):
    values = {
        1: _('mute'),
        2: _('temp-mute'),
        3: _('kick'),
        4: _('ban'),
        5: _('temp-ban')
    }

    return values[value]
