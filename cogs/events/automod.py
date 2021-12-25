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
import re
import asyncio

from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
from db.cache import CacheManager as cm
from contextlib import suppress
from collections import defaultdict

from time import time as unix_time
from utils.checks import CooldownByContent
from utils import default, btime, logger as logging

INVITE = re.compile(r'discord(?:\.com/invite|app\.com/invite|\.gg)/?([a-zA-Z0-9\-]{2,32})')
CAPS = re.compile(r"[ABCDEFGHIJKLMNOPQRSTUVWXYZ]")
LINKS = re.compile(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|%[0-9a-fA-F][0-9a-fA-F])+")
PHISHING = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]")


# noinspection PyUnboundLocalVariable
class AutomodEvents(commands.Cog, name='AutomodEvents'):
    def __init__(self, bot):
        self.bot = bot
        # cooldown goes the same as commands.cooldown
        # (messages, seconds, user/member/channel whatever)
        self.messages_cooldown = CooldownByContent.from_cooldown(15, 17.0, commands.BucketType.member)  # checks for same content
        self.user_cooldowns = commands.CooldownMapping.from_cooldown(10, 12.0, commands.BucketType.user)  # checks for member spam
        self.invite_cooldown = commands.CooldownMapping.from_cooldown(5, 60.0, commands.BucketType.member)  # checks for invites
        self.link_cooldown = commands.CooldownMapping.from_cooldown(5, 60.0, commands.BucketType.member)
        self.caps_content = commands.CooldownMapping.from_cooldown(6, 10.0, commands.BucketType.member)  # checks for caps

        self.new_users = commands.CooldownMapping.from_cooldown(30, 35.0, commands.BucketType.channel)

        self.batch_messages = defaultdict(list)

        self.send_messages.add_exception_type(RuntimeError)
        self.send_messages.start()

    def cog_unload(self):
        self.send_messages.cancel()

    @tasks.loop(seconds=10)
    async def send_messages(self):
        if not self.bot.is_ready():
            return

        for ((guild_id, channel_id), messages) in self.batch_messages.items():
            print(self.batch_messages.items())
            guild = self.bot.get_guild(guild_id)
            channel = guild and guild.get_channel(channel_id) or self.bot.get_channel(channel_id)
            if not channel:
                continue

            paginator = commands.Paginator(suffix='', prefix='')
            for message in messages:
                paginator.add_line(message)

            for page in paginator.pages:
                try:
                    await channel.send(page)
                except discord.HTTPException:
                    pass

            self.batch_messages.clear()

    @staticmethod
    def new_member(member):
        now = datetime.utcnow()
        seven_days = now - timedelta(days=7)
        month = now - timedelta(days=30)
        return member.created_at > month.astimezone(timezone.utc) and member.joined_at > seven_days.astimezone(timezone.utc)

    # if they send a message
    @commands.Cog.listener('on_message')
    async def on_automod(self, message):
        if not message.guild or not self.bot.is_ready():
            return

        automod = cm.get(self.bot, 'automod', message.guild.id)
        if not automod:
            return

        if message.author.bot:  # author is a bot
            return

        if not isinstance(message.author, discord.Member):
            return

        if message.author.guild_permissions.manage_messages and automod['ignore_admins']:  # Member has MANAGE_MESSAGES permissions and bot is configured to ignore admins/mods
            return

        if message.author.guild_permissions.administrator:
            return

        if not message.guild.me.guild_permissions.manage_roles or not message.guild.me.guild_permissions.kick_members or not message.guild.me.guild_permissions.ban_members:
            return

        channel_whitelist = cm.get(self.bot, 'channels_whitelist', message.guild.id)
        if channel_whitelist and message.channel.id in channel_whitelist:
            return

        role_whitelist = cm.get(self.bot, 'roles_whitelist', message.guild.id)
        if role_whitelist:
            for role in message.author.roles:
                if role.id in role_whitelist:
                    return

        users_whitelist = cm.get(self.bot, 'users_whitelist', message.guild.id)
        if users_whitelist and message.author.id in users_whitelist:
            return

        for coro in self.automodactions.copy():
            if await coro(self, message):  # type: ignore
                break

    # if they edit existing message
    @commands.Cog.listener('on_message_edit')
    async def on_automod_edit(self, before, after):
        message = after
        if not message.guild or not self.bot.is_ready():
            return

        automod = cm.get(self.bot, 'automod', message.guild.id)
        if not automod:
            return

        if message.author.bot:  # author is a bot
            return

        if not isinstance(message.author, discord.Member):
            return

        if message.author.guild_permissions.manage_messages and automod['ignore_admins']:  # Member has MANAGE_MESSAGES permissions and bot is configured to ignore admins/mods
            return

        if message.author.guild_permissions.administrator:  # Will still ignore admins
            return

        if not message.guild.me.guild_permissions.manage_roles or not message.guild.me.guild_permissions.kick_members or not message.guild.me.guild_permissions.ban_members:
            return

        if not before.embeds and after.embeds:
            return

        channel_whitelist = cm.get(self.bot, 'channels_whitelist', message.guild.id)
        if channel_whitelist and message.channel.id in channel_whitelist:
            return

        role_whitelist = cm.get(self.bot, 'roles_whitelist', message.guild.id)
        if role_whitelist:
            for role in message.author.roles:
                if role.id in role_whitelist:
                    return

        users_whitelist = cm.get(self.bot, 'users_whitelist', message.guild.id)
        if users_whitelist and message.author.id in users_whitelist:
            return

        for coro in self.automodactions.copy():
            if await coro(self, message):  # type: ignore
                break

    @commands.Cog.listener('on_member_join')
    async def on_anti_raid(self, member):
        if not member.guild:
            return

        automod = cm.get(self.bot, 'automod', member.guild.id)
        raidmode = cm.get(self.bot, 'raidmode', member.guild.id)
        if not automod:
            return
        if not raidmode:
            return

        if not member.guild.me.guild_permissions.ban_members or not member.guild.me.guild_permissions.kick_members:
            return

        if not self.new_member(member) and raidmode['action'] in [1, 2]:
            return

        users_whitelist = cm.get(self.bot, 'users_whitelist', member.guild.id)
        if users_whitelist and member.id in users_whitelist:
            return

        for coro in self.raidmode.copy():
            if await coro(self, member):  # type: ignore
                break

    async def anti_spam(self, message):
        current = message.created_at.timestamp()
        reason = _("Spam (sending multiple messages in a short time span)")
        antispam = cm.get(self.bot, 'spam', message.guild.id)

        if not antispam:
            return

        if self.new_member(message.author):
            content_bucket = self.new_users.get_bucket(message)
            if content_bucket.update_rate_limit(current):
                content_bucket.reset()
                return await self.execute_punishment(antispam['level'], message, reason, btime.FutureTime(antispam['time']))

        content_bucket = self.messages_cooldown.get_bucket(message)
        if content_bucket.update_rate_limit(current):
            content_bucket.reset()
            return await self.execute_punishment(antispam['level'], message, reason, btime.FutureTime(antispam['time']))

        user_bucket = self.user_cooldowns.get_bucket(message)
        if user_bucket.update_rate_limit(current):
            user_bucket.reset()
            return await self.execute_punishment(antispam['level'], message, reason, btime.FutureTime(antispam['time']))

    async def anti_invite(self, message):
        invites = INVITE.findall(message.content)
        current = message.created_at.timestamp()
        reason = _('Advertising')
        automod = cm.get(self.bot, 'automod', message.guild.id)
        antiinvite = cm.get(self.bot, 'invites', message.guild.id)

        if invites and antiinvite:
            content_bucket = self.invite_cooldown.get_bucket(message)
            the_invite = invites[0]
            try:
                invite = await self.bot.fetch_invite(the_invite)
                if invite.guild.id == message.guild.id and len(invites) == 1:
                    return
                if automod['delete_messages'] and message.channel.permissions_for(message.guild.me).manage_messages:
                    await message.delete()
            except Exception:
                return

            retry = content_bucket.update_rate_limit(current)
            if retry:
                content_bucket.reset()
                await self.execute_punishment(antiinvite['level'], message, reason, btime.FutureTime(antiinvite['time']))

    async def anti_caps(self, message):
        cap = CAPS.findall(message.content)
        current = message.created_at.timestamp()
        reason = _('Spamming caps')
        automod = cm.get(self.bot, 'automod', message.guild.id)
        masscaps = cm.get(self.bot, 'masscaps', message.guild.id)

        if not masscaps:
            return

        perc = masscaps['percentage'] / 100

        if len(cap) >= len(message.content) * perc and len(message.content) > 10:
            content_bucket = self.caps_content.get_bucket(message)
            retry = content_bucket.update_rate_limit(current)
            if automod['delete_messages'] and message.channel.permissions_for(message.guild.me).manage_messages:
                await message.delete()

            if retry:
                content_bucket.reset()
                await self.execute_punishment(masscaps['level'], message, reason, btime.FutureTime(masscaps['time']))

    async def anti_links(self, message):
        link = LINKS.findall(message.content)
        invites = INVITE.search(message.content)
        current = message.created_at.timestamp()
        reason = _('Spamming links')
        automod = cm.get(self.bot, 'automod', message.guild.id)
        antilinks = cm.get(self.bot, 'links', message.guild.id)

        if not antilinks:
            return

        if invites:  # invites and links are different things
            return

        if link:
            content_bucket = self.link_cooldown.get_bucket(message)
            retry = content_bucket.update_rate_limit(current)
            if automod['delete_messages'] and message.channel.permissions_for(message.guild.me).manage_messages:
                await message.delete(silent=True)

            if retry:
                content_bucket.reset()
                await self.execute_punishment(antilinks['level'], message, reason, btime.FutureTime(antilinks['time']))

    async def anti_mentions(self, message):
        reason = _('Spamming mentions')
        automod = cm.get(self.bot, 'automod', message.guild.id)
        massmention = cm.get(self.bot, 'massmention', message.guild.id)

        if not massmention:
            return

        limit = massmention['limit']
        mentions = sum(not x.bot and x.id != message.author.id for x in message.mentions)
        if mentions >= limit:
            if automod['delete_messages'] and message.channel.permissions_for(message.guild.me).manage_messages:
                await message.delete()

            await self.execute_punishment(massmention['level'], message, reason, btime.FutureTime(massmention['time']))

    async def anti_raid(self, member):
        raidmode = cm.get(self.bot, 'raidmode', member.guild.id)

        if not raidmode:
            return

        reason = _("anti raid: user account is younger than 30 days.") if raidmode['action'] in [1, 2] else _("Strict Anti Raid: No one is allowed to join the server")
        if raidmode['action'] == 1:
            action = 6
        elif raidmode['action'] == 2:
            action = 7
        elif raidmode['action'] == 3:
            action = 8
        elif raidmode['action'] == 4:
            action = 9
        await self.execute_punishment(action, member, reason)

    async def anti_phishing(self, message):  # this cannot be toggled off if automod is enabled in the server (it is not grouped under anti link or anti invites)
        current = message.created_at.timestamp()
        reason = _("Sending malicious links")
        phishing_links = PHISHING.search(message.content)

        if phishing_links:
            print(phishing_links)
            agent = {"User-Agent": f"Dredd ({self.bot.website})"}
            body = {"message": f"{phishing_links}"}
            validation = await self.bot.session.post(self.bot.config.PHISHING, headers=agent, json=body)  # The API is private. Credits: Fish Project
            if 500 % (validation.status + 1) == 500:  # service is down
                return
            result = await validation.json()
            if result.get("match") is False:
                return
            
            print(validation)
            await message.delete()  # delete the message
            print("Deleted")
            await self.execute_punishment(4, message, reason)  # ban

    def embed(self, member, reason, action, time=None) -> discord.Embed:
        emoji = self.bot.settings['emojis']['logs']
        if action in [1, 2, 3]:
            color = self.bot.settings['colors']['kick_color']
            emoji = emoji['msgdelete'] if action == 1 else emoji['memberedit']
            action = _('Member Muted') if action == 1 else _("Member Temp-Muted") if action == 2 else _("Member Kicked")
        elif action in [4, 5]:
            color = self.bot.settings['colors']['ban_color']
            emoji = emoji['ban']
            action = _("Member Banned") if action == 4 else _("Member Temp-Banned")
        elif action in [6, 7, 8, 9]:
            color = self.bot.settings['colors']
            color = color['ban_color'] if action in [7, 9] else color['kick_color']
            emoji = emoji['memberedit'] if action in [6, 8] else emoji['ban']
            action = _("Member Kicked") if action in [6, 8] else _("Member Banned")

        embed = discord.Embed(color=color, timestamp=datetime.now(timezone.utc))

        embed.set_author(name=_("Automod Action"), icon_url=member.avatar.url if member.avatar else member.display_avatar.url, url=f'https://discord.com/users/{member.id}')
        embed.title = f"{emoji} {action}"
        msg = _("\n**Duration:** {0}").format(time) if time else ''
        embed.description = _("**Member:** {0}{1}\n**Reason:** {2}").format(member, msg, reason)
        embed.set_footer(text=f'Member ID: {member.id}')
        return embed

    async def execute_punishment(self, action, message, reason, time=None):  # sourcery no-metrics
        automod = cm.get(self.bot, 'automod', message.guild.id)
        logchannel = message.guild.get_channel(automod['channel'])
        muterole = await default.get_muterole(self, message.guild)
        audit_reason = _("Automod Action | {0}").format(reason)
        anti_raid = cm.get(self.bot, 'raidmode', message.guild.id)
        error_msg = _("{0} Something failed while punishing the member, sent the error to my developers. "
                      "This is most likely due to me either missing permissions or not being able to access the person and/or role").format(self.bot.settings['emojis']['misc']['warn'])
        await logging.new_log(self.bot, unix_time(), 8, 1)

        try:
            if action == 1:
                if not message.guild.me.guild_permissions.manage_roles:
                    return
                try:
                    if muterole and muterole not in message.author.roles and muterole.position < message.guild.me.top_role.position:
                        await message.author.add_roles(muterole, reason=audit_reason)
                        await default.execute_temporary(self, 1, message.author, message.guild.me, message.guild, muterole, None, reason)
                        self.batch_messages[(message.guild.id, message.channel.id)].append(_("{0} Muted **{1}** for {2}.").format(self.bot.settings['emojis']['logs']['memberedit'], message.author, reason))
                    elif not muterole:
                        if not message.author.permissions_in(message.channel).send_messages:
                            return
                        await self.update_channel_permissions(message, action)
                    elif muterole in message.author.roles:
                        return
                    else:
                        await self.update_channel_permissions(message, action)
                    time = None
                except Exception as e:
                    await default.background_error(self, '`automod punishment execution (mute)`', e, message.guild, message.channel)
                    return await message.channel.send(error_msg)
            elif action == 2:
                if not message.guild.me.guild_permissions.manage_roles:
                    return
                try:
                    if muterole and muterole not in message.author.roles and muterole.position < message.guild.me.top_role.position:
                        await message.author.add_roles(muterole, reason=audit_reason)
                        await default.execute_temporary(self, 1, message.author, message.guild.me, message.guild, muterole, time, reason)
                        time = btime.human_timedelta(time.dt, source=message.created_at, suffix=None)
                        self.batch_messages[(message.guild.id, message.channel.id)].append(_("{0} Muted **{1}** for {2}, reason: {3}.").format(self.bot.settings['emojis']['logs']['memberedit'], message.author, time, reason))
                    elif not muterole:
                        if not message.author.permissions_in(message.channel).send_messages:
                            return
                        time = None
                        await self.update_channel_permissions(message, action)
                    elif muterole in message.author.roles:
                        return
                    else:
                        time = None
                        await self.update_channel_permissions(message, action)
                except Exception as e:
                    await default.background_error(self, '`automod punishment execution (tempmute)`', e, message.guild, message.channel)
                    return await message.channel.send(error_msg)
            elif action == 3:
                if not message.guild.me.guild_permissions.kick_members:
                    return
                try:
                    if message.author.top_role.position < message.guild.me.top_role.position:
                        await message.guild.kick(message.author, reason=audit_reason)
                        self.batch_messages[(message.guild.id, message.channel.id)].append(_("{0} Kicked **{1}** for {2}.").format(self.bot.settings['emojis']['logs']['memberedit'], message.author, reason))
                    else:
                        await self.update_channel_permissions(message, action)
                    time = None
                except Exception as e:
                    await default.background_error(self, '`automod punishment execution (kick)`', e, message.guild, message.channel)
                    return await message.channel.send(error_msg)
            elif action == 4:
                if not message.guild.me.guild_permissions.ban_members:
                    return
                try:
                    if message.author.top_role.position < message.guild.me.top_role.position:
                        await message.guild.ban(message.author, reason=audit_reason)
                        await default.execute_temporary(self, 2, message.author, message.guild.me, message.guild, None, None, reason)
                        self.batch_messages[(message.guild.id, message.channel.id)].append(_("{0} Banned **{1}** for {2}.").format(self.bot.settings['emojis']['logs']['ban'], message.author, reason))
                    else:
                        await self.update_channel_permissions(message, action)
                    time = None
                except Exception as e:
                    await default.background_error(self, '`automod punishment execution (ban)`', e, message.guild, message.channel)
                    return await message.channel.send(error_msg)
            elif action == 5:
                if not message.guild.me.guild_permissions.ban_members:
                    return
                try:
                    if message.author.top_role.position < message.guild.me.top_role.position:
                        await message.guild.ban(message.author, reason=audit_reason)
                        await default.execute_temporary(self, 2, message.author, message.guild.me, message.guild, None, time, reason)
                        time = btime.human_timedelta(time.dt, source=message.created_at, suffix=None)
                        self.batch_messages[(message.guild.id, message.channel.id)].append(_("{0} Banned **{1}** for {2}, reason: {3}.").format(self.bot.settings['emojis']['logs']['ban'], message.author, time, reason))
                    else:
                        time = None
                        await self.update_channel_permissions(message, action)
                except Exception as e:
                    await default.background_error(self, '`automod punishment execution (tempban)`', e, message.guild, message.channel)
                    return await message.channel.send(error_msg)
            elif action == 6:
                if not message.guild.me.guild_permissions.kick_members:
                    return
                try:
                    self.bot.join_counter.update({message.id})
                    if self.bot.join_counter[message.id] >= 5:
                        del self.bot.join_counter[message.id]
                        return await self.execute_punishment(9, message, audit_reason)
                    await message.guild.kick(message, reason=audit_reason)
                    logchannel = message.guild.get_channel(anti_raid['channel'])
                    if anti_raid['dm']:
                        with suppress(Exception):
                            await message.send(_("{0} {1} has anti raid mode activated, please try joining again later.").format(self.bot.settings['emojis']['misc']['warn'], message.guild))
                    time = None
                except Exception as e:
                    return await default.background_error(self, '`automod punishment execution (raidmode kick)`', e, message.guild, message.channel if hasattr(message, 'channel') else logchannel)
            elif action == 7:
                if not message.guild.me.guild_permissions.ban_members:
                    return
                try:
                    await message.guild.ban(message, reason=audit_reason)
                    logchannel = message.guild.get_channel(anti_raid['channel'])
                    if anti_raid['dm']:
                        with suppress(Exception):
                            await message.send(_("{0} {1} has anti raid mode activated, you're not allowed to join that server.").format(self.bot.settings['emojis']['misc']['warn'], message.guild))
                    time = None
                except Exception as e:
                    return await default.background_error(self, '`automod punishment execution (raidmode ban)`', e, message.guild, message.channel if hasattr(message, 'channel') else logchannel)
            elif action == 8:
                if not message.guild.me.guild_permissions.kick_members:
                    return
                try:
                    self.bot.join_counter.update({message.id})
                    if self.bot.join_counter[message.id] >= 5:
                        del self.bot.join_counter[message.id]
                        return await self.execute_punishment(9, message, audit_reason)
                    await message.guild.kick(message, reason=audit_reason)
                    logchannel = message.guild.get_channel(anti_raid['channel'])
                    if anti_raid['dm']:
                        with suppress(Exception):
                            await message.send(_("{0} {1} has strict anti raid mode activated, please try joining again later.").format(self.bot.settings['emojis']['misc']['warn'], message.guild))
                    time = None
                except Exception as e:
                    return await default.background_error(self, '`automod punishment execution (raidmode kick all)`', e, message.guild, message.channel if hasattr(message, 'channel') else logchannel)
            elif action == 9:
                if not message.guild.me.guild_permissions.ban_members:
                    return
                try:
                    await message.guild.ban(message, reason=audit_reason)
                    logchannel = message.guild.get_channel(anti_raid['channel'])
                    if anti_raid['dm']:
                        with suppress(Exception):
                            await message.send(_("{0} {1} has anti raid mode activated, you're not allowed to join that server.").format(self.bot.settings['emojis']['misc']['warn'], message.guild))
                    time = None
                except Exception as e:
                    return await default.background_error(self, '`automod punishment execution (raidmode ban all)`', e, message.guild, message.channel if hasattr(message, 'channel') else logchannel)
            self.bot.automod_counter.update({message.guild.id})
            count = self.bot.automod_counter.get(message.guild.id, 0)
            if count < 50:
                await asyncio.sleep(1)  # hopefully that's gonna wait between each log
                await logchannel.send(embed=self.embed(member=message if not hasattr(message, 'author') else message.author, reason=reason, action=action, time=time))
            elif count and 49 < count < 51:
                await logchannel.send(_("It seems like your server is experiencing a *huge* raid, to prevent us from getting api banned "
                                        "we'll be banning raiders in the background and will not be sending any logs in this channel."))
            if action in [6, 8]:
                await asyncio.sleep(60)  # delete them from the counter after 60 seconds
                if self.bot.join_counter[message.id] <= 2:
                    del self.bot.join_counter[message.id]

        except Exception as e:
            await default.background_error(self, '`automod punishment execution`', e, message.guild, message.channel if hasattr(message, 'channel') else logchannel)
            if action not in [6, 7, 8, 9]:
                return await message.channel.send(_("{0} I'm not sure what happened, but something broke. Please make sure that my role is above everyone's else, "
                                                    "otherwise you'll see these errors more often. I've also sent this error to my developers.").format(self.bot.settings['emojis']['misc']['warn']))

    async def update_channel_permissions(self, message, action):
        overwrite = message.channel.overwrites_for(message.author)
        overwrite.send_messages = False
        prefix = cm.get(self.bot, 'prefix', message.guild.id)
        await message.channel.set_permissions(message.author, overwrite=overwrite, reason="Automod Action | Was unable to perform another punishment")
        if action in [1, 2]:
            await message.channel.send(_("{0} Mute role was not found, please create the mute role, or set a custom one using `{1}muterole [role]`."
                                         "\n\nManually removed member permissions to send messages in this channel *hopefully*.").format(
                self.bot.settings['emojis']['misc']['warn'], prefix
            ))
        elif action in [3, 4, 5]:
            await message.channel.send(_("{0} Failed to kick/ban the member, are they higher in role hierarchy than me? Put my role at the very top to avoid these type of issues.\n\n"
                                         "Manually removed member permissions to send messages in this channel *hopefully*.").format(
                                             self.bot.settings['emojis']['misc']['warn']
                                         ))

    automodactions = [anti_links, anti_invite, anti_caps, anti_spam, anti_mentions, anti_phishing]
    raidmode = [anti_raid]


def setup(bot):
    bot.add_cog(AutomodEvents(bot))
