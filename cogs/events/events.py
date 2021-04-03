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
import asyncio

from discord.ext import commands
from discord.utils import escape_markdown

from db.cache import CacheManager as CM
from utils import btime, checks, default
from datetime import datetime, timedelta


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_icon = ''

    async def bot_check(self, ctx):
        if await ctx.bot.is_admin(ctx.author):
            return True

        blacklist = await ctx.bot.is_blacklisted(ctx.author)
        if blacklist and blacklist['type'] == 2:
            return False

        if await checks.lockdown(ctx):
            return False

        if await checks.bot_disabled(ctx):
            return False

        if await checks.guild_disabled(ctx):
            return False

        if ctx.command.cog:
            if ctx.command.qualified_name != self.bot.get_command('help').qualified_name and await checks.cog_disabled(ctx, str(ctx.command.cog.qualified_name)):
                return False

        if ctx.guild and ctx.guild.id in [709521003759403063, 667065302260908032, 809270378508976148, 611886244925931531]:  # 568567800910839811
            return True

        if ctx.author.id in [361241200080191489, 443217277580738571]:
            return True

        return False

    @commands.Cog.listener()
    async def on_ready(self):
        m = "Logged in as:"
        m += "\nName: {0} ({0.id})".format(self.bot.user)
        m += f"\nTime taken to boot: {btime.human_timedelta(self.bot.uptime, suffix=None)}"
        print(m)
        await self.bot.change_presence(status='idle', activity=discord.Activity(type=discord.ActivityType.playing, name="Dredd v3"))

        support_guild = self.bot.get_guild(self.bot.settings['servers']['main'])
        await support_guild.chunk(cache=True)
        print(f"{support_guild} chunked")

        # for guild in self.bot.guilds:
        #     if guild.id not in self.bot.prefix:
        #         self.bot.dispatch('guild_join', guild)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        ctx = await self.bot.get_context(message)

        if ctx.guild is None:
            check = CM.get(self.bot, 'dms', message.author.id)
            blacklist = CM.get(self.bot, 'blacklist', message.author.id)
            if blacklist:
                return
            if check is None:
                e = discord.Embed(color=self.bot.settings['colors']['embed_color'], title=f'Hey {message.author.name}!')
                e.description = _("I appreciate you for using me! You can also use my commands here in DMs with a prefix `!`,"
                                  " but if you aren't using any commands - the DM will be logged in my [support server]({0}),"
                                  " so please don't send me any sensitive information.").format(self.bot.support)
                e.set_thumbnail(url=self.bot.user.avatar_url)
                await self.bot.db.execute("INSERT INTO dms(user_id, name) VALUES($1, $2)", message.author.id, message.author.name)
                self.bot.dms[message.author.id] = message.author.name
                await message.author.send(embed=e)
            else:
                pass

            if ctx.valid:
                return

            if message.content.lower().startswith("-"):
                await message.author.send(_("Hey! Not sure if you know yet, but my prefix in DM's is `!`"))

            if message.stickers:
                message.content += f" *{message.stickers[0].description}*"

            if not message.content and message.activity:  # ignore invites if message content is empty
                return

            logchannel = self.bot.get_channel(self.bot.settings['channels']['dm'])
            dmid = ''
            for num in self.bot.dm:
                if self.bot.dm[num] == message.author.id:
                    dmid += f"{num}"

            total_dms = len(self.bot.dm)
            if not dmid:
                self.bot.dm[total_dms + 1] = message.author.id
                dmid = total_dms + 1

            msgembed = discord.Embed(
                description=message.content, color=discord.Color.blurple(), timestamp=datetime.utcnow())
            msgembed.set_author(name=f"New DM from: {message.author} | #{dmid}", icon_url=message.author.avatar_url)
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
                                             timestamp=datetime.utcnow())
                    ai_reply.set_author(name=f"I've sent a DM to {message.author} | #{dmid}", icon_url=message.author.avatar_url)
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
            if check['required_role']:
                roles_list = []
                for role in payload.member.roles:
                    roles_list.append(role.id)
                if check['required_role'] not in roles_list:
                    return await message.remove_reaction(payload.emoji, payload.member)

            members, count = [], 0
            if check['max_roles'] and check['max_roles'] < len(message.reactions):
                for reaction in message.reactions:
                    for member in await reaction.users().flatten():
                        if member == payload.member:
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

            try:
                the_emoji = self.bot.get_emoji(payload.emoji.id)
                if the_emoji.animated:
                    payload.emoji = f"<a:{payload.emoji.name}:{payload.emoji.id}>"
                else:
                    pass
            except Exception:
                pass

            guild = self.bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            if str(payload.emoji) not in check['dict']:
                return

            for item in check['dict']:
                if str(payload.emoji) == item:
                    await member.remove_roles(discord.Object(id=check['dict'][item]), reason='Reaction Roles')
        except Exception as e:
            await default.background_error(self, '`raw reaction remove`', e, self.bot.get_guild(payload.guild_id), self.bot.get_channel(payload))

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
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
                    e = discord.Embed(color=self.bot.settings['colors']['error_color'], timestamp=datetime.utcnow())
                    e.description = _("""Hey!\nThis server is blacklisted, so I will not be staying in the server anymore. {0}\n\n**Blacklist reason:** {1}""").format(
                        msg, check['reason']
                    )
                    e.set_thumbnail(url=self.bot.gif_pfp)
                    e.set_author(name=_("Blacklist issue occured!"), icon_url=self.bot.user.avatar_url)
                    await to_send.send(embed=e)
                else:
                    message = _("""Hey!\nThis server is blacklisted, thus why I will not be staying here anymore. {0}\n\n**Blacklisting reason:** {1}""").format(
                        msg, check['reason']
                    )
                    await to_send.send(message)
            except IndexError:
                pass
            return await guild.leave()

        prefix = self.bot.settings['default']['prefix']
        await self.bot.db.execute("INSERT INTO guilds(guild_id, prefix) VALUES($1, $2) ON CONFLICT (guild_id) DO UPDATE SET prefix = $2 WHERE guilds.guild_id = $1", guild.id, prefix)
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
        ratio = f'{int(100 / guild.member_count * bots)}'
        owner = guild.owner
        e = discord.Embed(timestamp=datetime.now())
        e.set_author(name=guild.name, icon_url=guild.icon_url)
        chan = self.bot.get_channel(self.bot.settings['channels']['joins-leaves'])
        e.color = self.bot.settings['colors']['approve_color']
        e.title = 'I\'ve joined a new guild'
        e.description = f"""
**Guild:** {guild.name} ({guild.id})
**Owner:** [{owner}](https://discord.com/users/{owner.id}) ({owner.id})
**Created at:** {btime.human_timedelta(guild.created_at, source=datetime.utcnow())}
**Members:** {len(guild.humans)} users and {bots} bots (Total: {guild.member_count})
**Users/Bots ratio:** {ratio}%
**Channels:** {tch} text / {vch} voice
**Icon url:** [Click here]({guild.icon_url})
"""
        e.set_footer(text=f"I'm in {len(self.bot.guilds)} guilds now")
        msg = await chan.send(embed=e)
        try:
            if check_delete_data:
                self.bot.guilds_data.pop(guild.id, None)
                await self.bot.db.execute("DELETE FROM delete_data WHERE guild_id = $1", guild.id)
                await msg.edit(content="\n*Guild data was saved successfully.*")
        except Exception as err:
            moksej = self.bot.get_user(345457928972533773)
            all_mentions = discord.AllowedMentions(users=True, everyone=False, roles=False)
            await chan.send(f"{moksej.mention} most likely failed to save data and the timer is still going\n`{err}`", allowed_mentions=all_mentions)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # I'm using asyncio.sleep() here just to
        # make sure the events don't bug out and
        # acidentally delete the data from the db.
        # from my testing on_guild_remove would sometimes
        # get dispatched before on_guild_join. (if server kicks new members immediately)
        # That was basically updating the data in the db and then immediately
        # deleting it. Ex here: https://cdn.dredd-bot.xyz/tI0o2y
        await asyncio.sleep(3)

        check = CM.get(self.bot, 'blacklist', guild.id)

        bots = len(guild.bots)
        tch = len(guild.text_channels)
        vch = len(guild.voice_channels)
        ratio = f'{int(100 / guild.member_count * bots)}'
        e = discord.Embed(timestamp=datetime.now())
        e.set_author(name=guild.name, icon_url=guild.icon_url)

        if check and check['type'] == 3:
            mod = self.bot.get_user(check['dev'])
            reason = check['reason']
            lift = f"{'Yes' if check['liftable'] == 0 else 'No'}"
            e.color = self.bot.settings['colors']['error_color']
            e.title = 'Blacklisted server left'
            e.description = f"""
**Guild:** {guild.name} ({guild.id})
**Owner:** [{guild.owner}](https://discord.com/users/{guild.owner.id}) ({guild.owner.id})
**Created at:** {btime.human_timedelta(guild.created_at, source=datetime.utcnow())}
**Members:** {len(guild.humans)} users and {len(guild.bots)} bots (Total: {guild.member_count})
**Users/Bots ratio:** {ratio}%
**Channels:** {tch} text / {vch} voice
**Icon url:** [Click here]({guild.icon_url})
"""
            e.add_field(name='Blacklist info:', value=f"Blacklisted by **{mod}** {btime.human_timedelta(check['issued'])}.\n**Reason:** {reason}\n**Liftable:** {lift}")
            chan = self.bot.get_channel(self.bot.settings['channels']['joins-leaves'])
            return await chan.send(embed=e)
        else:
            e.title = 'I\'ve left a guild'
            e.description = f"""
**Guild:** {guild.name} ({guild.id})
**Members:** {len(guild.humans)} users and {len(guild.bots)} bots (Total: {guild.member_count})
**Users/Bots ratio:** {ratio}%
**Icon url:** [Click here]({guild.icon_url})
"""
            chan = self.bot.get_channel(self.bot.settings['channels']['joins-leaves'])
            all_mentions = discord.AllowedMentions(users=True, everyone=False, roles=False)
            partner_main_chat = self.bot.get_channel(self.bot.settings['channels']['partners-chat'])
            partners_check = await self.bot.db.fetch("SELECT * FROM partners WHERE _id = $1", guild.id)
            if partners_check:
                await partner_main_chat.send(f"{guild.owner.mention} Hey! I was kicked from your server ({guild.name}) whilst being partnered. "
                                             f"You have 48 hours to reinvite me to that server or I'll be with unpartnering you.\n"
                                             f"> • Must have Dredd in the server\n Thanks!", allowed_mentions=all_mentions)
            e.color = self.bot.settings['colors']['deny_color']
            e.set_footer(text=f"I'm in {len(self.bot.guilds)} guilds now")
            msg = await chan.send(embed=e)

            content = ''
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
        await self.bot.wait_until_ready()

        if message.channel.id == 603800402013585408 and message.author.id == 568254611354419211:
            e = discord.Embed(color=self.bot.settings['colors']['embed_color'], timestamp=datetime.now())
            if 'added bot' in message.content.lower():
                e.title = 'New bot added!'
                e.description = message.content
                e.add_field(name='Jump to original', value=f"[Jump]({message.jump_url})")
                mok = self.bot.get_user(345457928972533773)
                return await mok.send(embed=e)
            elif 'resubmitted bot' in message.content.lower():
                e.title = 'Bot resubmitted!'
                e.description = message.content
                e.add_field(name='Jump to original', value=f"[Jump]({message.jump_url})")
                mok = self.bot.get_user(345457928972533773)
                return await mok.send(embed=e)

    @commands.Cog.listener('on_member_update')
    async def status_logging(self, before, after):
        await self.bot.wait_until_ready()

        if not CM.get(self.bot, 'status_op', after.id):
            return

        if before.status != after.status:
            query = """INSERT INTO status(user_id, status_type, since) VALUES($1, $2, $3)
                        ON CONFLICT (user_id) DO UPDATE
                        SET status_type = $2, since = $3
                        WHERE status.user_id = $1"""
            await self.bot.db.execute(query, after.id, after.status.name, datetime.now())

    @commands.Cog.listener('on_member_update')
    async def nicknames_logging(self, before, after):
        await self.bot.wait_until_ready()

        if before.bot:
            return

        if before.nick != after.nick:
            if CM.get(self.bot, 'nicks_op', f'{before.id} - {before.guild.id}'):
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

        afks = CM.get(self.bot, 'afk', f'{str(message.guild.id)}, {str(message.author.id)}')
        if afks:
            await message.channel.send(_("Welcome back {0}! You were away for **{1}**. Your AFK state has been removed.").format(
                    message.author.mention, btime.human_timedelta(afks['time'], suffix=None)), allowed_mentions=discord.AllowedMentions(users=True))
            await self.bot.db.execute("DELETE FROM afk WHERE user_id = $1 AND guild_id = $2", message.author.id, message.guild.id)
            self.bot.afk.pop(f'{str(message.guild.id)}, {str(message.author.id)}')

        to_send = ''
        for user in message.mentions:
            check = CM.get(self.bot, 'afk', f'{str(message.guild.id)}, {str(user.id)}')
            if check:
                afkmsg = check['note']
                afkmsg = afkmsg.strip()
                member = message.guild.get_member(user.id)
                to_send += (_("Hey! **{0}** has been AFK for **{1}**"
                              " for - **{2}**.").format(
                                member.display_name, btime.human_timedelta(check['time'], suffix=None),
                                escape_markdown(afkmsg, as_needed=False)
                            ))
                try:
                    await message.reply(f"{to_send}", allowed_mentions=discord.AllowedMentions(replied_user=True))
                except Exception as e:
                    print(e)
                    try:
                        await message.author.send(_("Hey! {0}").format(to_send))
                    except Exception:
                        return

    @commands.Cog.listener('on_message_delete')
    async def snipes_logging(self, message):
        await self.bot.wait_until_ready()

        if CM.get(self.bot, 'snipes_op', message.author.id):
            return

        if not message.guild:
            return

        if message.stickers != []:
            message.content += _("\n*Sticker* - {0}").format(message.stickers[0].name)

        self.bot.snipes[message.channel.id] = {'message': message.content, 'deleted_at': datetime.now(), 'author': message.author.id, 'nsfw': message.channel.is_nsfw()}


def setup(bot):
    bot.add_cog(Events(bot))
