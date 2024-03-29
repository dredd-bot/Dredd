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

import discord
import asyncio
import re
import logging as log

from discord.ext import commands

from time import time
from db.cache import CacheManager as CM
from utils import btime, checks, default, logger as logging, components
from datetime import datetime, timedelta, timezone
from contextlib import suppress

dredd_logger = log.getLogger("dredd")

LINKS = re.compile(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|%[0-9a-fA-F][0-9a-fA-F])+")
INVITE = re.compile(r'discord(?:\.com/invite|app\.com/invite|\.gg)/?([a-zA-Z0-9\-]{2,32})')


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_icon = ''

        self.persistent_views_added = False

        self.cooldown_bot_mentions = commands.CooldownMapping.from_cooldown(1, 10.0, commands.BucketType.channel)
        self.cooldown_afk_mentions = commands.CooldownMapping.from_cooldown(5, 10.0, commands.BucketType.channel)

    async def bot_check(self, ctx):
        if await ctx.bot.is_admin(ctx.author):
            return True

        if ctx.guild and ctx.guild.id == 835844760194908160:
            return True

        if ctx.bot.user.id == 663122720044875796 and ctx.guild.data.beta:  # type: ignore
            return True

        if ctx.bot.user.id == 663122720044875796 and not await ctx.bot.is_owner(ctx.author):  # type: ignore
            return False

        blacklist = await ctx.bot.is_blacklisted(ctx.author)
        if blacklist and blacklist['type'] == 2:
            return False

        if await checks.lockdown(ctx):
            return False

        if await checks.bot_disabled(ctx):
            return False

        if await checks.guild_disabled(ctx):
            return False

        if ctx.command.cog and ctx.command.qualified_name != self.bot.get_command('help').qualified_name and await checks.cog_disabled(ctx, str(ctx.command.cog.qualified_name)):
            return False

        return True

    @commands.Cog.listener()
    async def on_ready(self):
        boot_time = btime.human_timedelta(self.bot.uptime, suffix=None)
        m = "Logged in as:"
        m += "\nName: {0} ({0.id})".format(self.bot.user)
        m += f"\nTime taken to boot: {boot_time}"
        print(m)
        await self.bot.change_presence(status='online', activity=discord.Activity(type=discord.ActivityType.playing, name="-help or @Dredd help"))
        dredd_logger.info(f"[BOT] Booted up, boot time - {boot_time}")

        if not self.persistent_views_added:
            view, _ = components.create_self_roles()
            self.bot.add_view(view)
            dredd_logger.info("[BOT] Successfully added reaction roles view.")
            self.persistent_views_added = True

        support_guild = self.bot.get_guild(self.bot.settings['servers']['main'])
        await support_guild.chunk(cache=True)
        print(f"{support_guild} chunked")

    @commands.Cog.listener()
    async def on_message(self, message):  # sourcery no-metrics
        if message.author.bot:
            return

        ctx = await self.bot.get_context(message)
        if not ctx.valid:
            await logging.new_log(self.bot, time(), 9, 1)

        if ctx.guild and not ctx.valid:
            if message.content.lower() in [f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>"]:
                current = message.created_at.timestamp()
                content_bucket = self.cooldown_bot_mentions.get_bucket(message)
                if content_bucket.update_rate_limit(current):
                    return
                if message.mention_everyone or message.reference or message.role_mentions:
                    return
                prefix = CM.get(self.bot, 'prefix', message.guild.id)
                if not prefix:  # If bot was invited when it was offline, or if for some reason the data was lost
                    self.bot.dispatch('guild_join', message.guild)
                    prefix = '-'
                return await message.channel.send(_("My prefix in this server is `{0}` or {1}!").format(prefix, self.bot.user.mention))

        elif ctx.guild is None:
            if self.bot.user.id == 663122720044875796 and not await self.bot.is_owner(message.author):
                return
            check = CM.get(self.bot, 'dms', message.author.id)
            blacklist = CM.get(self.bot, 'blacklist', message.author.id)
            if blacklist or not self.bot.log_dm:
                return
            if check is None:
                e = discord.Embed(color=self.bot.settings['colors']['embed_color'], title=f'Hey {message.author.name}!')
                e.description = _("I appreciate you for using me! You can also use my commands here in DMs with a prefix `!`,"
                                  " but if you aren't using any commands - the DM will be logged in my [support server]({0}),"
                                  " so please don't send me any sensitive information.").format(self.bot.support)
                e.set_thumbnail(url=self.bot.user.avatar.url)
                await self.bot.db.execute("INSERT INTO dms(user_id, name) VALUES($1, $2)", message.author.id, message.author.name)
                self.bot.dms[message.author.id] = message.author.name
                await message.author.send(embed=e)
            if ctx.valid:
                return

            if message.content.lower().startswith("-"):
                await message.author.send(_("Hey! Not sure if you know yet, but my prefix in DM's is `!`"))

            if message.stickers:
                message.content += f" *{message.stickers[0].description}*"

            if not message.content and message.activity:  # ignore invites if message content is empty
                return

            logchannel = self.bot.get_channel(self.bot.settings['channels']['dm'])
            dmid = ''.join(
                f"{num}"
                for num in self.bot.dm
                if self.bot.dm[num] == message.author.id
            )

            if not dmid:
                total_dms = len(self.bot.dm)
                self.bot.dm[total_dms + 1] = message.author.id
                dmid = total_dms + 1

            invites = INVITE.findall(message.content)
            links = LINKS.findall(message.content)
            if invites:
                for invite in invites:
                    message.content = message.content.replace(invite, f"{self.bot.support.split('/')[3]}")
            if links:
                for link in links:
                    message.content = message.content.replace(link, '[link](https://cdn.dreddbot.xyz/iOGRhc)')

            msgembed = discord.Embed(
                description=message.content, color=discord.Color.blurple(), timestamp=datetime.now(timezone.utc))
            msgembed.set_author(name=f"New DM from: {message.author} | #{dmid}", icon_url=message.author.avatar.url if message.author.avatar else message.author.display_avatar.url)
            msgembed.set_footer(text=f"User ID: {message.author.id}")
            # They've sent an image/gif/file
            if message.attachments:
                attachment_url = message.attachments[0].url
                msgembed.set_image(url=attachment_url)
            content = f"Message ID: {message.id}"
            await logchannel.send(content=content, embed=msgembed)

            if self.bot.auto_reply:
                the_reply = await default.dm_reply(self, message.content)
                try:
                    await message.reply(the_reply)
                    ai_reply = discord.Embed(description=the_reply,
                                             color=0x81C969,
                                             timestamp=datetime.now(timezone.utc))
                    ai_reply.set_author(name=f"I've sent a DM to {message.author} | #{dmid}", icon_url=message.author.avatar.url if message.author.avatar else message.author.display_avatar.url)
                    ai_reply.set_footer(text=f"User ID: {message.author.id}")
                    await logchannel.send(content='Chatbot has replied to this DM', embed=ai_reply)
                except Exception as e:
                    await logchannel.send(content=f'Failed to send a DM to {message.author} ({message.author.id}) - #{dmid}\n**Error:** {e}')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        try:
            check = CM.get(self.bot, 'rr', payload.message_id)
            if not check:
                return
            if payload.member.bot:
                return

            guild = self.bot.get_guild(payload.guild_id)
            channel = guild.get_channel(check['channel'])
            message = await channel.fetch_message(payload.message_id)
            if str(payload.emoji) not in check['dict']:
                return await message.remove_reaction(payload.emoji, payload.member)
            if check['required_role'] and check['required_role'] not in [x.id for x in payload.member.roles]:
                return await message.remove_reaction(payload.emoji, payload.member)

            if check['max_roles'] and check['max_roles'] < len(message.reactions):
                members, count = [], 0
                for reaction in message.reactions:
                    if payload.member in await reaction.users().flatten():
                        count += 1
                if count > check['max_roles']:
                    return await message.remove_reaction(payload.emoji, payload.member)

            for item in check['dict']:
                if str(payload.emoji) == item:
                    await payload.member.add_roles(discord.Object(id=check['dict'][item]), reason='Reaction Roles')
        except Exception as e:
            await default.background_error(self, '`raw reaction add`', e, self.bot.get_guild(payload.guild_id), self.bot.get_channel(payload))

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        try:
            check = CM.get(self.bot, 'rr', payload.message_id)
            if not check:
                return

            with suppress(Exception):
                if str(payload.emoji) not in check['dict']:
                    the_emoji = self.bot.get_emoji(payload.emoji.id)  # type: ignore
                    if the_emoji.animated:
                        payload.emoji = f"<a:{payload.emoji.name}:{payload.emoji.id}>"  # type: ignore
                        if str(payload.emoji) not in check['dict']:
                            return

            guild = self.bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)

            for item in check['dict']:
                if str(payload.emoji) == item:
                    await member.remove_roles(discord.Object(id=check['dict'][item]), reason='Reaction Roles')
        except Exception as e:
            await default.background_error(self, '`raw reaction remove`', e, self.bot.get_guild(payload.guild_id), self.bot.get_channel(payload))

    # noinspection PyDunderSlots
    @commands.Cog.listener()
    async def on_guild_join(self, guild):  # sourcery no-metrics
        check = CM.get(self.bot, 'blacklist', guild.id)
        check_delete_data = CM.get(self.bot, 'guilds_data', guild.id)

        if check and check['type'] == 3:
            try:
                to_send = sorted([chan for chan in guild.channels if chan.permissions_for(
                    guild.me).send_messages and isinstance(chan, discord.TextChannel)], key=lambda x: x.position)[0]
                if check['liftable'] == 0:
                    msg = _("If you are the server owner and would like to appeal, you can [join the support server]({0}).").format(
                        self.bot.support
                    )
                else:
                    msg = _("Unfortunately, this server's blacklist state cannot be removed.")
                if to_send.permissions_for(guild.me).embed_links:
                    e = discord.Embed(color=self.bot.settings['colors']['error_color'], timestamp=datetime.now(timezone.utc))
                    e.description = _("""Hey!\nThis server is blacklisted, so I will not be staying in the server anymore. {0}\n\n**Blacklist reason:** {1}""").format(
                        msg, check['reason']
                    )
                    e.set_thumbnail(url=self.bot.gif_pfp)
                    e.set_author(name=_("Blacklist issue occured!"), icon_url=self.bot.user.avatar.url)
                    await to_send.send(embed=e)
                else:
                    message = _("""Hey!\nThis server is blacklisted, thus why I will not be staying here anymore. {0}\n\n**Blacklisting reason:** {1}""").format(
                        msg, check['reason']
                    )
                    await to_send.send(message)
            except IndexError:
                pass
            return await guild.leave()

        with suppress(Exception):
            head = {"Authorization": self.bot.config.DREDD_API_TOKEN, "Client": self.bot.config.DREDD_API_CLIENT}
            body = {"guilds": len(self.bot.guilds), "users": sum(x.member_count for x in self.bot.guilds)}
            await self.bot.session.post('https://dreddbot.xyz/api/stats', headers=head, json=body)
            print("Updated the stats - guild join")

        prefix = self.bot.settings['default']['prefix']
        await self.bot.db.execute("INSERT INTO guilds(guild_id, prefix, language) VALUES($1, $2, $3) ON CONFLICT (guild_id) DO UPDATE SET prefix = $2 WHERE guilds.guild_id = $1", guild.id, prefix, 'en_US')
        self.bot.prefix[guild.id] = prefix
        Zenpa = self.bot.get_user(373863656607318018) or "Zenpa#6736"
        Moksej = self.bot.get_user(345457928972533773) or "Moksej#3335"
        support = self.bot.support
        to_send = ''
        try:
            to_send = sorted([chan for chan in guild.channels if chan.permissions_for(
                guild.me).send_messages and isinstance(chan, discord.TextChannel)], key=lambda x: x.position)[0]
        except IndexError:
            pass
        if to_send and to_send.permissions_for(guild.me).embed_links:  # We can embed!
            e = discord.Embed(
                color=self.bot.settings['colors']['embed_color'], title="A cool bot has spawned in!")
            e.description = _("Thank you for inviting me to this server!"  # not sure why I made this a translatable string, it's english all the time lmao, unless they reinvite it within 30 days and have another language set
                              "\nTo get started - you can see my commands by using `{0}help [category/command]`."
                              " In order to change my prefix you can use `{0}prefix [prefix]`."
                              "If you'll need any help you can join the [support server]({1}). You can also contact `{2}` or `{3}` if you'll need any help.").format(
                                    prefix, support, Moksej, Zenpa
                                )
            e.set_image(url=self.bot.settings['banners']['default'])
            try:
                await to_send.send(embed=e)
            except Exception:
                pass
        elif to_send and not to_send.permissions_for(guild.me).send_messages:  # We were invited without embed perms...
            msg = _("Thank you for inviting me to this server!"
                    "\nTo get started - you can see my commands by using `{0}help [category/command]`."
                    " In order to change my prefix, you can use `{0}prefix [prefix]`. "
                    "If you'll need any help you can join the <{1}>. You can also contact `{2}` or `{3}` if you'll need any help.").format(
                        prefix, support, Moksej, Zenpa
                    )
            try:
                await to_send.send(msg)
            except Exception:
                pass
        # await guild.chunk(cache=True)
        bots = len(guild.bots)
        tch = len(guild.text_channels)
        vch = len(guild.voice_channels)
        ratio = 'Unknown'
        with suppress(Exception):
            ratio = f'{int(100 / guild.member_count * bots)}'
        owner = guild.owner
        e = discord.Embed(timestamp=datetime.now(timezone.utc))
        e.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else self.bot.user.display_avatar.url)
        chan = self.bot.get_channel(self.bot.settings['channels']['joins-leaves'])
        e.color = self.bot.settings['colors']['approve_color']  # type: ignore
        e.title = 'I\'ve joined a new guild'
        e.description = f"""
**Guild:** {guild.name} ({guild.id})
**Owner:** [{owner}](https://discord.com/users/{owner.id}) ({owner.id})
**Created at:** {btime.human_timedelta(guild.created_at, source=datetime.utcnow())}
**Members:** {len(guild.humans)} users and {bots} bots (Total: {guild.member_count})
**Users/Bots ratio:** {ratio}%
**Channels:** {tch} text / {vch} voice
**Icon url:** [Click here]({guild.icon.url if guild.icon else self.bot.user.display_avatar.url})
"""
        e.set_footer(text=f"I'm in {len(self.bot.guilds)} guilds now")
        msg = await chan.send(embed=e)
        await logging.new_log(self.bot, time(), 1, 1)
        try:
            if check_delete_data:
                self.bot.guilds_data.pop(guild.id, None)
                await self.bot.db.execute("DELETE FROM delete_data WHERE guild_id = $1", guild.id)
                await msg.edit(content="\n*Guild data was saved successfully.*")
        except Exception as err:
            moksej = self.bot.get_user(345457928972533773)
            all_mentions = discord.AllowedMentions(users=True, everyone=False, roles=False)
            await chan.send(f"{moksej.mention} most likely failed to save data and the timer is still going\n`{err}`", allowed_mentions=all_mentions)

    # noinspection PyDunderSlots
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):  # sourcery no-metrics
        # I'm using asyncio.sleep() here just to
        # make sure the events don't bug out and
        # acidentally delete the data from the db.
        # from my testing on_guild_remove would sometimes
        # get dispatched before on_guild_join. (if server kicks new members immediately)
        # That was basically updating the data in the db and then immediately
        # deleting it. Ex here: https://cdn.dreddbot.xyz/tI0o2y
        if guild.name is None:
            return

        await asyncio.sleep(3)

        check = CM.get(self.bot, 'blacklist', guild.id)

        bots = len(guild.bots)
        tch = len(guild.text_channels)
        vch = len(guild.voice_channels)
        ratio = 'Unknown'
        with suppress(Exception):
            if hasattr(guild, 'member_count'):
                ratio = f'{int(100 / guild.member_count * bots)}'
            else:
                ratio = f'{int(100 / len(guild.members) * bots)}'
        e = discord.Embed(timestamp=datetime.now(timezone.utc))
        e.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else self.bot.user.display_avatar.url)
        with suppress(Exception):
            head = {"Authorization": self.bot.config.DREDD_API_TOKEN, "Client": self.bot.config.DREDD_API_CLIENT}
            body = {"guilds": len(self.bot.guilds), "users": sum(x.member_count for x in self.bot.guilds)}
            await self.bot.session.post('https://dreddbot.xyz/api/stats', headers=head, json=body)
            print("Updated the stats - guild leave")

        if check and check['type'] == 3:
            mod = self.bot.get_user(check['dev'])
            reason = check['reason']
            lift = f"{'Yes' if check['liftable'] == 0 else 'No'}"
            e.color = self.bot.settings['colors']['error_color']  # type: ignore
            e.title = 'Blacklisted server left'
            e.description = f"""
**Guild:** {guild.name} ({guild.id})
**Owner:** [{guild.owner}](https://discord.com/users/{guild.owner.id}) ({guild.owner.id})
**Created at:** {btime.human_timedelta(guild.created_at, source=datetime.utcnow())}
**Members:** {len(guild.humans)} users and {len(guild.bots)} bots (Total: {guild.member_count if hasattr(guild, 'member_count') else len(guild.members)})
**Users/Bots ratio:** {ratio}%
**Channels:** {tch} text / {vch} voice
**Icon url:** [Click here]({guild.icon.url if guild.icon else self.bot.user.display_avatar.url})
"""
            e.add_field(name='Blacklist info:', value=f"Blacklisted by **{mod}** {btime.human_timedelta(check['issued'], source=datetime.now())}.\n**Reason:** {reason}\n**Liftable:** {lift}")
            chan = self.bot.get_channel(self.bot.settings['channels']['joins-leaves'])
            return await chan.send(embed=e)
        else:
            e.title = 'I\'ve left a guild'
            e.description = f"""
**Guild:** {guild.name} ({guild.id})
**Members:** {len(guild.humans)} users and {len(guild.bots)} bots (Total: {guild.member_count if hasattr(guild, 'member_count') else len(guild.members)})
**Users/Bots ratio:** {ratio}%
**Icon url:** [Click here]({guild.icon.url if guild.icon else self.bot.user.display_avatar.url})
"""
            chan = self.bot.get_channel(self.bot.settings['channels']['joins-leaves'])
            all_mentions = discord.AllowedMentions(users=True, everyone=False, roles=False)
            partner_main_chat = self.bot.get_channel(self.bot.settings['channels']['partners-chat'])
            partners_check = await self.bot.db.fetch("SELECT * FROM partners WHERE _id = $1", guild.id)
            if partners_check:
                await partner_main_chat.send(f"{guild.owner.mention} Hey! I was kicked from your server ({guild.name}) whilst being partnered. "
                                             f"You have 48 hours to reinvite me to that server or I'll be with unpartnering you.\n"
                                             f"> • Must have Dredd in the server\n Thanks!", allowed_mentions=all_mentions)
            e.color = self.bot.settings['colors']['deny_color']  # type: ignore
            e.set_footer(text=f"I'm in {len(self.bot.guilds)} guilds now")
            msg = await chan.send(embed=e)
            await logging.new_log(self.bot, time(), 2, 1)

            try:
                time_when = datetime.utcnow() + timedelta(days=30)
                self.bot.guilds_data[guild.id] = time_when
                await self.bot.db.execute("INSERT INTO delete_data VALUES($1, $2) ON CONFLICT (guild_id) DO UPDATE SET delete_at = $2 WHERE delete_data.guild_id = $1", guild.id, time_when)
                await msg.edit(content='Inserted data into the db and will delete it automatically in 30 days.')
            except Exception as err:
                moksej = self.bot.get_user(345457928972533773)
                await msg.reply(f"{moksej.mention} failed to insert data into automatic 30 days timer\n`{err}`", allowed_mentions=all_mentions)

    # other events
    @commands.Cog.listener('on_message')
    async def on_del_add(self, message):
        return
        # await self.bot.wait_until_ready()
        #
        # if message.channel.id == 603800402013585408 and message.author.id == 568254611354419211:
        #     e = discord.Embed(color=self.bot.settings['colors']['embed_color'], timestamp=datetime.now(timezone.utc))
        #     if 'added bot' in message.content.lower():
        #         e.title = 'New bot added!'
        #         e.description = message.content
        #         e.add_field(name='Jump to original', value=f"[Jump]({message.jump_url})")
        #         mok = self.bot.get_user(345457928972533773)
        #         return await mok.send(embed=e)
        #     elif 'resubmitted bot' in message.content.lower():
        #         e.title = 'Bot resubmitted!'
        #         e.description = message.content
        #         e.add_field(name='Jump to original', value=f"[Jump]({message.jump_url})")
        #         mok = self.bot.get_user(345457928972533773)
        #         return await mok.send(embed=e)

    @commands.Cog.listener('on_member_update')
    async def nicknames_logging(self, before, after):
        await self.bot.wait_until_ready()

        if before.bot:
            return

        if before.nick != after.nick:
            if CM.get(self.bot, 'nicks_op', f'{before.id} - {before.guild.id}'):  # type: ignore
                return
            nick = before.nick or before.name
            await self.bot.db.execute("INSERT INTO nicknames(user_id, guild_id, nickname, time) VALUES($1, $2, $3, $4)", after.id, after.guild.id, nick, datetime.now())

    @commands.Cog.listener('on_message')
    async def afk_status(self, message):
        await self.bot.wait_until_ready()

        if message.author.bot:
            return

        if not message.guild:
            return

        afks = CM.get(self.bot, 'afk', f'{message.guild.id}, {message.author.id}')  # type: ignore
        afks2 = CM.get(self.bot, 'afk', f'{message.author.id}')  # type: ignore
        if afks:
            await message.channel.send(_("Welcome back {0}! You were away for **{1}**. Your AFK state has been removed.").format(
                    message.author.mention, btime.human_timedelta(afks['time'], source=datetime.utcnow(), suffix=None)), allowed_mentions=discord.AllowedMentions(users=True))
            await self.bot.db.execute("DELETE FROM afk WHERE user_id = $1 AND guild_id = $2", message.author.id, message.guild.id)
            self.bot.afk.pop(f'{message.guild.id}, {message.author.id}')
        elif afks2:
            await message.channel.send(_("Welcome back {0}! You were away for **{1}**. Your AFK state has been removed.").format(
                    message.author.mention, btime.human_timedelta(afks2['time'], source=datetime.utcnow(), suffix=None)), allowed_mentions=discord.AllowedMentions(users=True))
            await self.bot.db.execute("DELETE FROM afk WHERE user_id = $1", message.author.id)
            self.bot.afk.pop(f'{message.author.id}')

        to_send = ''
        for user in message.mentions:
            check = CM.get(self.bot, 'afk', f'{message.guild.id}, {user.id}')  # type: ignore
            check2 = CM.get(self.bot, 'afk', f'{user.id}')  # type: ignore
            if check or check2:
                check = check or check2
                afkmsg = check['note']
                afkmsg = afkmsg.strip()
                member = message.guild.get_member(user.id)
                to_send += (_("Hey! **{0}** has been AFK for **{1}**"
                              " for - **{2}**.").format(
                                member.display_name, btime.human_timedelta(check['time'], source=datetime.utcnow(), suffix=None),
                                afkmsg
                            ))

                current = message.created_at.timestamp()
                content_bucket = self.cooldown_afk_mentions.get_bucket(message)
                if content_bucket.update_rate_limit(current):
                    return

                try:
                    await message.reply(f"{to_send}", allowed_mentions=discord.AllowedMentions(replied_user=True))
                except Exception:
                    try:
                        await message.author.send(to_send)
                    except Exception:
                        return

    @commands.Cog.listener('on_message_delete')
    async def snipes_logging(self, message):
        await self.bot.wait_until_ready()

        if CM.get(self.bot, 'snipes_op', message.author.id):
            return

        if not message.guild:
            return

        if message.stickers:
            message.content += _("\n*Sticker* - {0}").format(message.stickers[0].name)

        self.bot.snipes[message.channel.id] = {'message': message.content, 'deleted_at': discord.utils.utcnow(), 'author': message.author.id, 'nsfw': message.channel.is_nsfw()}

    @commands.Cog.listener('on_raw_message_delete')
    async def reaction_roles_delete(self, payload):
        if self.bot.cache.get_message(self.bot, payload.message_id):
            await self.bot.db.execute("DELETE FROM reactionroles WHERE message_id = $1", payload.message_id)
            self.bot.rr.pop(payload.message_id, None)

    @commands.Cog.listener('on_guild_channel_delete')
    async def reaction_roles_channel_delete(self, channel):
        await self.bot.db.execute("DELETE FROM reactionroles WHERE channel_id = $1", channel.id)


def setup(bot):
    bot.add_cog(Events(bot))
