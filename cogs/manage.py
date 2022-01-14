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
import asyncio

import discord
import json
import typing

from discord.ext import commands
from discord.utils import escape_markdown

from utils import default, i18n, components, enums
from utils.checks import admin, moderator, is_guild_disabled
from utils.paginator import Pages
from contextlib import suppress
from utils.i18n import locale_doc, current_locale


# noinspection PyUnboundLocalVariable,PyUnusedLocal
class Manage(commands.Cog, name='Management'):
    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:settingss:695707235833085982>"
        self.big_icon = "https://cdn.discordapp.com/emojis/695707235833085982.png?v=1"

    @staticmethod
    def create_views(ctx, channel, current_setup):
        view, values = components.create_self_roles(ctx.guild, current_setup["components_style"], current_setup["payload"])
        return view, values

    @staticmethod
    async def add_reactions(message, reactions) -> None:
        for value in reactions:
            for reaction in value:
                await message.add_reaction(reaction)

    @staticmethod
    def make_dict(values) -> dict:
        raw_dict = {}
        for item in values:
            for v in item:
                raw_dict[v] = item[v]

        return raw_dict

    @staticmethod
    def message_views(message) -> int:
        if message and not message.rr:
            if message.components:
                return sum(
                    5 if isinstance(view, discord.components.SelectMenu) else 1
                    for view in message.components[0].children
                )
            return len(message.reactions)
        return 0

    @staticmethod
    def message_content(current_setup):
        if current_setup["message_style"]["type"] == enums.ReactionRolesMessageType.embed:
            embed = discord.Embed.from_dict(current_setup["message_style"]["payload"])
            content = current_setup["message_style"]["payload"].get("plainText", None)
        else:
            content, embed = current_setup["message_style"]["payload"], None

        return content, embed

    async def execute_message(self, ctx, current_setup: dict, **kwargs):
        if current_setup["message_type"] == enums.ReactionRolesType.new_message:  # noqa
            channel = current_setup["channel"]
            message_content, embed = self.message_content(current_setup)
            if current_setup["use_components"]:
                view, values = components.create_self_roles(ctx.guild, current_setup["components_style"], current_setup["payload"])
                message = await channel.send(message_content, embed=embed, view=view)
            else:
                message = await channel.send(message_content, embed=embed)
                roles = values = current_setup["payload"]
                await self.add_reactions(message, roles)
                values = self.make_dict(values)

            raw_dict = self.make_dict(current_setup["payload"])
            query = "INSERT INTO reactionroles VALUES($1, $2, $3, $4, $5, $6, $7)"
            await self.bot.db.execute(query, ctx.guild.id, channel.id, message.id, json.dumps(values), current_setup["limits"]["required_role"], current_setup["limits"]["max_roles"], json.dumps(raw_dict))
            self.bot.rr[message.id] = {'guild': ctx.guild.id, 'channel': channel.id, 'dict': values, 'required_role': current_setup["limits"]["required_role"],
                                       'max_roles': current_setup["limits"]["max_roles"], 'raw_dict': raw_dict}

        elif current_setup["message_type"] == enums.ReactionRolesType.existing_message:
            channel = current_setup["channel"]
            message = current_setup["message"]
            author = current_setup["author"]
            if author == enums.ReactionRolesAuthor.user or (current_setup["use_components"] is False and current_setup["using_components"] is False):
                roles = values = current_setup["payload"]
                await self.add_reactions(message, roles)
                values = self.make_dict(values)
            else:
                view, values = components.create_self_roles(ctx.guild, current_setup["components_style"], current_setup["payload"])
                with suppress(Exception):
                    await message.clear_reactions()
                await message.edit(view=view)

            if current_setup["message_style"]["edit_old"] is True:
                message_content, embed = self.message_content(current_setup)
                await message.edit(message_content, embed=embed)

            raw_dict = self.make_dict(current_setup["payload"])
            if message.rr:
                query = "UPDATE reactionroles SET components_dict = $1, raw_dict = $2, required_role_id = $3, max_roles = $4 WHERE message_id = $5"
                await self.bot.db.execute(query, json.dumps(values), json.dumps(raw_dict), current_setup["limits"]["required_role"], current_setup["limits"]["max_roles"], message.id)
                self.bot.rr[message.id]['dict'] = values
                self.bot.rr[message.id]['raw_dict'] = raw_dict
                self.bot.rr[message.id]['required_role'] = current_setup["limits"]["required_role"]
                self.bot.rr[message.id]['max_roles'] = current_setup["limits"]["max_roles"]
            else:
                query = "INSERT INTO reactionroles VALUES($1, $2, $3, $4, $5, $6, $7)"
                await self.bot.db.execute(query, ctx.guild.id, channel.id, message.id, json.dumps(values), current_setup["limits"]["required_role"], current_setup["limits"]["max_roles"], json.dumps(raw_dict))
                self.bot.rr[message.id] = {'guild': ctx.guild.id, 'channel': channel.id, 'dict': values, 'required_role': current_setup["limits"]["required_role"],
                                           'max_roles': current_setup["limits"]["max_roles"], 'raw_dict': raw_dict}

        return message, values

    async def interactive_reaction_roles(self, ctx, message_type: enums.ReactionRolesType, **kwargs):  # get the channel, determine if to use reactions or components

        def check(m):
            return m.author == ctx.author and m.channel.id == ctx.channel.id

        try:
            self.bot.rr_setup[(ctx.author.id, ctx.channel.id)]["message_type"] = enums.ReactionRolesType(int(message_type))
            if int(message_type) == int(enums.ReactionRolesType.new_message):
                use_components = None
                while True:
                    get_channel = await ctx.channel.send(_("What channel should I send the message to?"))
                    channel = await self.bot.wait_for('message', check=check, timeout=60.0)
                    if channel.content.lower() == 'cancel':
                        return await get_channel.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                    try:
                        channel = await commands.TextChannelConverter().convert(ctx, channel.content)
                        if not channel.can_send:  # type: ignore
                            await get_channel.edit(content=_("I can't send messages in that channel, please give me permissions to send messages in that channel or choose another channel."))
                        else:
                            channel = self.bot.rr_setup[(ctx.author.id, ctx.channel.id)]["channel"] = channel
                            self.bot.rr_setup[(ctx.author.id, ctx.channel.id)]["author"] = enums.ReactionRolesAuthor(0)
                            break
                    except Exception:
                        await get_channel.edit(content=_("Can't find that channel, if that's even a channel."))

                view = components.ReactionRolesConfirmComponents(self, ctx, 60, self.bot.rr_setup.get((ctx.author.id, ctx.channel.id)))
                return await ctx.channel.send(_("Would you like to use Discord message components (buttons) for the new reaction roles setup? If no, normal reactions will be used instead."), view=view)

            setup_message = using_components = None
            while True:
                existing_message_check = await ctx.channel.send(_("Send the link of the message you want to use for reaction roles."))
                setup_message = await self.bot.wait_for('message', check=check, timeout=60.0)
                if setup_message.content.lower() == 'cancel':
                    self.bot.rr_setup.pop((ctx.author.id, ctx.channel.id), None)
                    return await existing_message_check.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                elif setup_message.content.lower().startswith('https://'):
                    url = setup_message.content.split('/')
                    try:
                        channel = self.bot.rr_setup[(ctx.author.id, ctx.channel.id)]["channel"] = ctx.guild.get_channel(int(url[5]))
                        message = self.bot.rr_setup[(ctx.author.id, ctx.channel.id)]["message"] = await channel.fetch_message(int(url[6]))
                        self.bot.rr_setup[(ctx.author.id, ctx.channel.id)]["author"] = enums.ReactionRolesAuthor(0) if message.author == ctx.guild.me else enums.ReactionRolesAuthor(1)
                        if message.author.bot and message.author == ctx.guild.me:
                            self.bot.rr_setup[(ctx.author.id, ctx.channel.id)]["using_components"] = using_components = bool(message.components)
                        break
                    except Exception as e:
                        await existing_message_check.edit(content=_("Can't find that message, please make sure the link is valid and I can see the channel, message history."))
                else:
                    await existing_message_check.edit(content=_("Invalid answer, try again."))

            if using_components is False:
                view = components.ReactionRolesConfirmComponents(self, ctx, 60, self.bot.rr_setup.get((ctx.author.id, ctx.channel.id)))
                return await ctx.channel.send(_("It seems like you're using the old system for reaction roles if any, would you like to switch to a new one using Discord message components (buttons)?"), view=view)
            elif using_components is True:
                view = components.ReactionRolesComponentsStyle(self, ctx, 60, self.bot.rr_setup.get((ctx.author.id, ctx.channel.id)))
                e = discord.Embed(title="Reaction Roles Setup", color=self.bot.settings['colors']['embed_color'])
                e.description = _("Should buttons display label only, emoji only or both? This action is irreversible!")
                e.image = self.bot.rr_image
                return await ctx.channel.send(embed=e, view=view)

            await self.interactive_reaction_roles_2(ctx, self.bot.rr_setup.get((ctx.author.id, ctx.channel.id)))

        except asyncio.exceptions.TimeoutError:
            return await ctx.channel.send(_("You ran out of time, cancelling command."), delete_after=10)

        except Exception as e:
            return await ctx.channel.send(_("{0} Command failed with an error, please report this in our support server: `{error}`").format(
                self.bot.settings['emojis']['misc']['warn'], error=e
            ))

    async def interactive_reaction_roles_2(self, ctx, current_setup: dict):

        def check(m):
            return m.author == ctx.author and m.channel.id == ctx.channel.id

        payload = {}
        if current_setup["message_type"] == enums.ReactionRolesType.existing_message:
            database_payload = await self.bot.db.fetchval("SELECT raw_dict FROM reactionroles WHERE message_id = $1", current_setup["message"].id)
            if database_payload:
                payload = json.loads(database_payload)
        while True:
            try:
                while True:
                    emoji = cancelled = done = None
                    get_emoji = await ctx.channel.send(_("Please send a **single** emoji that you'd like to use. If you're done, send `done`"))

                    limit = 25 if current_setup["use_components"] or current_setup["using_components"] else 20
                    if self.message_views(current_setup["message"]) + len(payload) <= limit:
                        reaction_to_use = await self.bot.wait_for('message', check=check, timeout=60.0)

                        if reaction_to_use.content.lower() == 'cancel':
                            cancelled = True
                            await get_emoji.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                        elif reaction_to_use.content.lower() == "done" and len(payload) != 0:
                            current_setup["payload"] = [payload]
                            cancelled = done = True
                        else:
                            if payload.get(reaction_to_use.content):
                                await get_emoji.edit(content=_("That emoji is already being used for reaction roles"))
                            else:
                                try:
                                    await get_emoji.add_reaction(reaction_to_use.content)
                                    emoji = reaction_to_use.content
                                    await get_emoji.delete()
                                except Exception:
                                    await get_emoji.edit(content=_("Invalid emoji, try again."))
                    else:
                        await get_emoji.edit(content=_("You've hit the max limit of reactions/buttons to be used on a message."))
                        cancelled = done = True
                        current_setup["payload"] = [payload]

                    if emoji is None and cancelled is not True:
                        continue
                    elif emoji is not None:
                        get_role = await ctx.channel.send(_("Please send a role that you'd like to assign to emoji - {0}").format(emoji))
                        role_to_use = await self.bot.wait_for('message', check=check, timeout=60.0)

                        if role_to_use.content.lower() == 'cancel':
                            await get_role.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                            cancelled = True
                        else:
                            try:
                                role: discord.Role = await commands.RoleConverter().convert(ctx, role_to_use.content)
                                if role.id in payload.values():
                                    await get_role.edit(content=_("That role is already used in the reaction role, please choose another role."), delete_after=15)
                                else:
                                    if role.is_integration() or role.is_bot_managed() or role.is_default():
                                        await get_role.edit(content=_("Can't use that role."))
                                    if role.position < ctx.guild.me.top_role.position:
                                        payload[emoji] = role.id
                                        current_setup["payload"] = [payload]
                                        await get_role.delete()
                                    else:
                                        await get_role.edit(content=_("The role you've provided is higher in the role hierarchy, please make sure I can access the role."))
                            except Exception:
                                await get_role.edit(content=_("Invalid role, try again."))

                    if cancelled is True:
                        assert True is False

            except asyncio.exceptions.TimeoutError:
                cancelled, done = True, False
                return await ctx.channel.send(_("You ran out of time, cancelling command."), delete_after=10)

            except AssertionError:
                break

            except Exception as e:
                print(e)
                cancelled, done = True, False
                break

        if cancelled and done is not True:
            return

        try:
            while True:
                should_require_role = await ctx.channel.send(_("What role do users need in order to access the reaction roles? `None` if no role should be required."))
                required_role = await self.bot.wait_for('message', check=check, timeout=60.0)

                if required_role.content.lower() == 'cancel':
                    return await should_require_role.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                elif required_role.content.lower() == 'none':
                    break
                try:
                    role = await commands.RoleConverter().convert(ctx, required_role.content)
                    if role.id in payload.values():
                        await should_require_role.edit(content=_("That role is already used in the reaction role, please choose another role."), delete_after=15)
                    elif role.is_integration() or role.is_bot_managed() or role.is_default():
                        await required_role.edit(content=_("Can't use that role."))
                    else:
                        current_setup["limits"]["required_role"] = role.id
                        await should_require_role.delete()
                        break
                except Exception:
                    await should_require_role.edit(content=_("Invalid role, try again."))

            while True:
                roles_limit_check = await ctx.channel.send(_("How many roles should users be able to get from the reaction role? Send {0} if all.").format(len(payload)))
                roles_limit = await self.bot.wait_for('message', check=check, timeout=60.0)

                if roles_limit.content.lower() == 'cancel':
                    return await roles_limit_check.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                try:
                    num = current_setup["limits"]["max_roles"] = max(min(int(roles_limit.content), len(payload)), 1)  # default at 1 if number is too huge/is negative
                    await roles_limit_check.edit(content=_("Set the max number of roles to **{0}**").format(num))
                    break
                except Exception:
                    await roles_limit_check.edit(content=_("Answer must be a number or `cancel` to cancel."))

        except asyncio.exceptions.TimeoutError:
            return await ctx.channel.send(_("You ran out of time, cancelling command."), delete_after=10)

        except Exception as e:
            return await ctx.channel.send(_("{0} Command failed with an error, please report this in our support server: `{error}`").format(
                self.bot.settings['emojis']['misc']['warn'], error=e
            ))

        if current_setup["message_type"] == enums.ReactionRolesType.existing_message:
            if current_setup["author"] == enums.ReactionRolesAuthor.bot:
                while True:
                    should_edit_message = await ctx.channel.send(_("Do you want to edit the reaction roles setup message as well (if current message is fully custom, you will have to recreate it as it is going to be fully "
                                                                   "re-done)? `y` or `n`"))
                    edit_message = await self.bot.wait_for('message', check=check, timeout=60.0)

                    if edit_message.content.lower() == 'cancel':
                        return await should_edit_message.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                    try:
                        if edit_message.content.lower() == 'n':
                            break
                        current_setup["message_style"]["edit_old"] = True
                        view = components.ReactionRolesMessage(self, ctx, 60, current_setup)
                        return await ctx.channel.send(_("Would you like me to send a normal or embedded message?"), view=view)
                    except Exception:
                        await should_edit_message.edit(content=_("Invalid role, try again."))
            message, values = await self.execute_message(ctx, current_setup=current_setup)
            return await ctx.channel.send(_("{0} Successfully created reaction roles setup!").format(ctx.bot.settings['emojis']['misc']['white-mark']), delete_after=15)
        else:
            view = components.ReactionRolesMessage(self, ctx, 60, current_setup)
            return await ctx.channel.send(_("Would you like me to send a normal or embedded message?"), view=view)

    async def perform_action(self, value: bool, interaction: discord.Interaction, current_setup: dict, ctx) -> None:

        def check(m):
            return m.author == ctx.author and m.channel.id == ctx.channel.id

        if value is True:
            if current_setup["message_style"]["type"] == enums.ReactionRolesMessageType.embed:
                view = components.ReactionRolesEmbedView(self, ctx, 60, current_setup)
                return await ctx.send(_("Customize your embed."), view=view)
            while True:
                try:
                    value = await ctx.channel.send(_("What should the message be?"))
                    get_value = await ctx.bot.wait_for('message', check=check, timeout=60.0)

                    if get_value.content.lower() == "cancel":
                        return await value.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                    elif len(get_value.content) > 2000:
                        await value.edit(content=_("You've hit the characters limit: {0}/{1}").format(len(get_value.content), 2000))
                    else:
                        current_setup["message_style"]["payload"] = get_value.content
                        message, values = await self.execute_message(ctx, current_setup=current_setup)
                        return await ctx.channel.send(_("{0} Successfully created reaction roles setup!").format(ctx.bot.settings['emojis']['misc']['white-mark']), delete_after=15)
                except asyncio.exceptions.TimeoutError:
                    return await ctx.channel.send(_("You ran out of time, cancelling command."), delete_after=10)
        elif value is False:
            roles = []
            for value in current_setup["payload"]:
                for emoji in value:
                    roles.append((emoji, value[emoji]))
            list_of_roles = [f"{emoji} - <@&{role}>\n" for emoji, role in roles]
            current_setup["message_style"]["message"] = f"Interact with the reactions below to get the corresponding role(s).\n{''.join(list_of_roles)}"
            message, values = await self.execute_message(ctx, current_setup=current_setup)
            return await ctx.channel.send(_("{0} Successfully created reaction roles setup!").format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=15)

    @commands.group(brief=_("Manage bot's prefix in the server"),
                    invoke_without_command=True)
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.member)
    @locale_doc
    async def prefix(self, ctx):
        _(""" View and manage your server's prefix """)

        prefix = self.bot.cache.get(self.bot, 'prefix', ctx.guild.id)

        if prefix:
            text = _('If you want to change my prefix you can do so by invoking `{0}prefix set <new prefix>`').format(ctx.prefix)
            return await ctx.send(_("My prefix in this server is `{0}`\n"
                                    "{1}").format(escape_markdown(prefix, as_needed=True), text if ctx.author.guild_permissions.manage_guild else ''))
        else:
            self.bot.prefix[ctx.guild.id] = self.bot.settings['default']['prefix']
            try:
                await self.bot.db.execute("INSERT INTO guilds VALUES($1, $2)", ctx.guild.id, self.bot.settings['default']['prefix'])
            except Exception:
                pass
            return await ctx.send(_("I don't have a custom prefix in this server! The default prefix is `{0}`").format(self.bot.settings['default']['prefix']))

    @prefix.command(name='set',
                    aliases=['change'],
                    brief=_("Change my prefix in the server"))
    @commands.guild_only()
    @admin(manage_guild=True)
    @locale_doc
    async def prefix_set(self, ctx, prefix: str):
        _(""" Change my prefix in the server """)

        if len(prefix) > 7:
            return await ctx.send(_("{0} A prefix can only be 7 characters long! You're {1} characters over.").format(self.bot.settings['emojis']['misc']['warn'], len(prefix) - 7))
        query = """UPDATE guilds
                    SET prefix = $1
                    WHERE guild_id = $2"""
        await self.bot.db.execute(query, prefix, ctx.guild.id)
        self.bot.prefix[ctx.guild.id] = prefix
        await ctx.send(_("{0} Changed my prefix in this server to `{1}`").format(self.bot.settings['emojis']['misc']['white-mark'], prefix))

    @commands.command(name='set-language', brief=_("Change bot's language in the server"), aliases=['setlanguage', 'setlang'])
    @admin(manage_guild=True)
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.member)
    @locale_doc
    async def setlanguage(self, ctx, language: str):
        _(""" Change the bot's language in the current server to your prefered one (if available) """)

        if language not in i18n.locales:
            return await ctx.send(_("{0} Looks like that language doesn't exist, available languages are: {1}").format(
                self.bot.settings['emojis']['misc']['warn'], '`' + '`, `'.join(i18n.locales) + '`',
            ))
        current_locale.set(language)
        await self.bot.db.execute("UPDATE guilds SET language = $1 WHERE guild_id = $2", language, ctx.guild.id)
        self.bot.translations[ctx.guild.id] = language
        await ctx.send(_("{0} Changed the bot language to `{1}`").format(self.bot.settings['emojis']['misc']['white-mark'], language))

    @commands.group(brief=_("A rough overview on server settings"),
                    aliases=['settings', 'guildsettings'],
                    invoke_without_command=True)
    @commands.guild_only()
    @locale_doc
    async def serversettings(self, ctx):
        _(""" Rough overview on server settings, such as logging and more. """)

        logs = default.server_logs(ctx, ctx.guild, simple=False)
        muterole = await default.get_muterole(ctx, ctx.guild)
        prefix = self.bot.cache.get(self.bot, 'prefix', ctx.guild.id)
        language = self.bot.cache.get(self.bot, 'translations', ctx.guild.id)
        mod_role = ctx.guild.get_role(self.bot.cache.get(self.bot, 'mod_role', ctx.guild.id))
        admin_role = ctx.guild.get_role(self.bot.cache.get(self.bot, 'admin_role', ctx.guild.id))
        modrole = mod_role.mention if mod_role else _('Default')
        adminrole = admin_role.mention if admin_role else _('Default')

        embed = discord.Embed(color=self.bot.settings['colors']['embed_color'],
                              title=_("{0} {1} Server Settings").format(self.bot.settings['emojis']['logs']['settings'], ctx.guild.name))
        embed.add_field(name=_('**Logs:**'), value=logs['logs'])
        embed.add_field(name=_('**Settings:**'), value=logs['settings'])
        embed.add_field(name=_('**More:**'), value=_("**Mute role:** {0}\n"
                                                     "**Prefix:** `{1}`\n"
                                                     "**Language:** {2}\n"
                                                     "**Mod role:** {3}\n"
                                                     "**Admin role:** {4}").format(
                                                         muterole.mention if muterole else _('Not found'), prefix, language,
                                                         modrole, adminrole))

        joinmessage = self.bot.cache.get(self.bot, 'joinmessage', ctx.guild.id)
        leavemessage = self.bot.cache.get(self.bot, 'leavemessage', ctx.guild.id)
        if joinmessage:
            if joinmessage['embedded']:
                message = _('Run `{0}serversettings joinembed` to view the welcome embed').format(ctx.prefix)
            else:
                message = joinmessage['message'] or self.bot.settings['default']['join_message_text']
            embed.add_field(name=_('Welcome Message'), value=message, inline=False)

        if leavemessage:
            if leavemessage['embedded']:
                message = _('Run `{0}serversettings leaveembed` to view the leave embed').format(ctx.prefix)
            else:
                message = leavemessage['message'] or self.bot.settings['default']['leave_message_text']
            embed.add_field(name=_('Leave Message'), value=message, inline=False)
        await ctx.send(embed=embed)

    @serversettings.command(name='joinembed', brief=_("View welcoming embed"))
    @commands.guild_only()
    @locale_doc
    async def serversettings_joinembed(self, ctx):
        _(""" View welcoming messages embed """)

        joinmessage = self.bot.cache.get(self.bot, 'joinmessage', ctx.guild.id)
        if not joinmessage:
            return await ctx.send(_("{0} Welcome messages are disabled in this server.").format(self.bot.settings['emojis']['misc']['warn']))

        if not joinmessage['embedded']:
            return await ctx.send(_("{0} Welcome messages do not use embeds in this server.").format(self.bot.settings['emojis']['misc']['warn']))

        message = json.loads(joinmessage['message']) or self.bot.settings['default']['join_message_embed']
        embed = discord.Embed.from_dict(message)
        if not embed:
            return await ctx.send(_("{0} Embed code is invalid, or only plain text is visible. "
                                    "Please make sure you're using the correct format by visiting this website <https://embedbuilder.nadekobot.me/>").format(self.bot.settings['emojis']['misc']['warn']))
        await ctx.send(content=_("Your welcome embed looks like this: *plain text is not displayed*"), embed=embed)

    @serversettings.command(name='leaveembed', brief=_("View leaving embed"))
    @commands.guild_only()
    @locale_doc
    async def serversettings_leaveembed(self, ctx):
        _(""" View leaving messages embed """)

        leavemessage = self.bot.cache.get(self.bot, 'leavemessage', ctx.guild.id)
        if not leavemessage:
            return await ctx.send(_("{0} Leave messages are disabled in this server.").format(self.bot.settings['emojis']['misc']['warn']))

        if not leavemessage['embedded']:
            return await ctx.send(_("{0} Leave messages do not use embeds in this server.").format(self.bot.settings['emojis']['misc']['warn']))

        message = json.loads(leavemessage['message']) or self.bot.settings['default']['leave_message_embed']
        embed = discord.Embed.from_dict(message)
        if not embed:
            return await ctx.send(_("{0} Embed code is invalid, or only plain text is visible. "
                                    "Please make sure you're using the correct format by visiting this website <https://embedbuilder.nadekobot.me/>").format(self.bot.settings['emojis']['misc']['warn']))
        await ctx.send(content=_("Your leave embed looks like this: *plain text is not displayed*"), embed=embed)

    @commands.group(brief=_("Toggle logging on or off"),
                    aliases=['logging'],
                    invoke_without_command=True)
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def togglelog(self, ctx):
        _(""" Base command for managign logging in the server """)
        await ctx.send_help(ctx.command)

    @togglelog.command(aliases=['memberlogging', 'memberlog'], brief=_("Toggle member logging in the server"))
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def memberlogs(self, ctx, channel: discord.TextChannel = None):
        _(""" This enables or disables member logging.
        Member logging includes: avatar changes, nickname changes, username changes. """)

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:  # type: ignore
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        memberlogs = self.bot.cache.get(self.bot, 'memberlog', ctx.guild.id)

        if memberlogs and not channel:
            await self.bot.db.execute("DELETE from memberlog WHERE guild_id = $1", ctx.guild.id)
            self.bot.memberlog.pop(ctx.guild.id)
            return await ctx.send(_("{0} Successfully disabled member logs.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif memberlogs:
            await self.bot.db.execute("UPDATE memberlog SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.memberlog[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Successfully changed the member logging channel. I will now send member updates in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                          channel.mention))
        elif not channel:
            return await ctx.send(_("{0} You don't have member logs enabled in this server."
                                    "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        else:
            await self.bot.db.execute("INSERT INTO memberlog VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.memberlog[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Successfully enabled member logs. I will now send member updates in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                           channel.mention))

    @togglelog.command(aliases=['joinlogging', 'joinlog', 'newmembers', 'memberjoins'], name='joinlogs',
                       brief=_("Toggle join logs in the server"))
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def togglelog_joinlogs(self, ctx, channel: discord.TextChannel = None):
        _(""" This enables or disables new members logging
        New member logging includes: join logging. """)

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:  # type: ignore
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        joinlogs = self.bot.cache.get(self.bot, 'joinlog', ctx.guild.id)

        if joinlogs and not channel:
            await self.bot.db.execute("DELETE from joinlog WHERE guild_id = $1", ctx.guild.id)
            self.bot.joinlog.pop(ctx.guild.id)
            return await ctx.send(_("{0} New members logging was successfully disabled.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif joinlogs:
            await self.bot.db.execute("UPDATE joinlog SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.joinlog[ctx.guild.id] = channel.id
            self.bot.dispatch('member_joinlog', ctx.author)
            return await ctx.send(_("{0} Successfully changed the new member logging channel. I will now send member updates in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                              channel.mention))
        elif not channel:
            return await ctx.send(_("{0} You don't have new member logs enabled in this server."
                                    "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        else:
            await self.bot.db.execute("INSERT INTO joinlog VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.joinlog[ctx.guild.id] = channel.id
            self.bot.dispatch('member_joinlog', ctx.author)
            return await ctx.send(_("{0} Successfully enabled new member logging. I will now send member updates in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                  channel.mention))

    @togglelog.command(aliases=['leavelogging', 'leavelog', 'memberleaves'], name='leavelogs', brief=_("Toggle leave logs in the server"))
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def togglelog_leavelogs(self, ctx, channel: discord.TextChannel = None):
        _(""" This enables or disables member leave logging.
        Member leave logging includes: leave logging. """)

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:  # type: ignore
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        leavelogs = self.bot.cache.get(self.bot, 'leavelog', ctx.guild.id)

        if leavelogs and not channel:
            await self.bot.db.execute("DELETE from leavelog WHERE guild_id = $1", ctx.guild.id)
            self.bot.leavelog.pop(ctx.guild.id)
            return await ctx.send(_("{0} Successfully disabled leave member logs.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif leavelogs:
            await self.bot.db.execute("UPDATE leavelog SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.leavelog[ctx.guild.id] = channel.id
            self.bot.dispatch('member_leavelog', ctx.author)
            return await ctx.send(_("{0} Successfully changed the leave member logging channel. I will now send member updates in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                                channel.mention))
        elif not channel:
            return await ctx.send(_("{0} You don't have leave member logs enabled in this server."
                                    "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        else:
            await self.bot.db.execute("INSERT INTO leavelog VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.leavelog[ctx.guild.id] = channel.id
            self.bot.dispatch('member_leavelog', ctx.author)
            return await ctx.send(_("{0} Successfully changed the leave member logging channel. I will now send member leaves in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                               channel.mention))

    @togglelog.command(aliases=['serverlogs'], name='guildlogs', brief=_("Toggle guild logs in the server"))
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def togglelog_guildlogs(self, ctx, channel: discord.TextChannel = None):
        _(""" This enables or disables guild changes logging.
        Guild changes logging includes: name, region, icon, afk channel, mfa level, verification level, default notifications. """)

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:  # type: ignore
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        guildlogs = self.bot.cache.get(self.bot, 'guildlog', ctx.guild.id)

        if guildlogs and not channel:
            await self.bot.db.execute("DELETE from guildlog WHERE guild_id = $1", ctx.guild.id)
            self.bot.guildlog.pop(ctx.guild.id)
            return await ctx.send(_("{0} Successfully disabled guild log updates.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif guildlogs:
            await self.bot.db.execute("UPDATE guildlog SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.guildlog[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Successfully changed the guild log updates channel. I will now send guild updates in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                            channel.mention))
        elif not channel:
            return await ctx.send(_("{0} You don't have guild update logging enabled in this server."
                                    "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        else:
            await self.bot.db.execute("INSERT INTO guildlog VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.guildlog[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Successfully enabled guild updates logging. I will now send guild updates in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                    channel.mention))

    @togglelog.command(aliases=['msgedits', 'msgedit', 'editmessages'], name='messageedits',
                       brief=_("Toggle edit message logs in the server"))
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def togglelog_messageedits(self, ctx, channel: discord.TextChannel = None):
        _(""" This enables or disables messages edit logging """)

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:  # type: ignore
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        messageedit = self.bot.cache.get(self.bot, 'messageedits', ctx.guild.id)

        if messageedit and not channel:
            await self.bot.db.execute("DELETE from messageedits WHERE guild_id = $1", ctx.guild.id)
            self.bot.messageedits.pop(ctx.guild.id)
            return await ctx.send(_("{0} Successfully disabled edit message logs.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif messageedit:
            await self.bot.db.execute("UPDATE messageedits SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.messageedits[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Successfully updated the logging channel for edited messages to {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                       channel.mention))
        elif not channel:
            return await ctx.send(_("{0} You don't have edit message logs enabled in this server."
                                    "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        else:
            await self.bot.db.execute("INSERT INTO messageedits VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.messageedits[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Enabled edit message logging in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                       channel.mention))

    @togglelog.command(aliases=['msgdeletes', 'msgdelete', 'deletemessages'], name='messagedeletes', brief=_("Toggle delete message logs in the server."))
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def togglelog_messagedeletes(self, ctx, channel: discord.TextChannel = None):
        _(""" This enables or disables messages deleting logging """)

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:  # type: ignore
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        messagedelete = self.bot.cache.get(self.bot, 'messagedeletes', ctx.guild.id)

        if messagedelete and not channel:
            await self.bot.db.execute("DELETE from messagedeletes WHERE guild_id = $1", ctx.guild.id)
            self.bot.messagedeletes.pop(ctx.guild.id)
            return await ctx.send(_("{0} Successfully disabled deleted message logs.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif messagedelete:
            await self.bot.db.execute("UPDATE messagedeletes SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.messagedeletes[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Successfully updated the logging channel for deleted messages to {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                        channel.mention))
        elif not channel:
            return await ctx.send(_("{0} Deleted message logs are currently disabled in this server."
                                    "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        else:
            await self.bot.db.execute("INSERT INTO messagedeletes VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.messagedeletes[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Enabled deleted message logging in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                          channel.mention))

    @togglelog.command(aliases=['modlogs'], name='moderation', brief=_("Toggle moderation logs"))
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def togglelog_moderation(self, ctx, channel: discord.TextChannel = None):
        _(""" This enables or disables moderation logging
        Moderation logging includes: bans, kicks, mutes, unbans, unmutes. """)

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:  # type: ignore
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        moderation = self.bot.cache.get(self.bot, 'moderation', ctx.guild.id)

        if moderation and not channel:
            await self.bot.db.execute("DELETE from moderation WHERE guild_id = $1", ctx.guild.id)
            self.bot.moderation.pop(ctx.guild.id)
            return await ctx.send(_("{0} Moderation logging was successfully disabled.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif moderation:
            await self.bot.db.execute("UPDATE moderation SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.moderation[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Successfully updated the moderation logging channel to {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                              channel.mention))
        elif not channel:
            return await ctx.send(_("{0} Moderation logs are currently disabled in this server."
                                    "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        else:
            await self.bot.db.execute("INSERT INTO moderation VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.moderation[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Enabled moderation logging in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                     channel.mention))

    @togglelog.command(name='all', brief=_("Toggle all the logs in the server"))
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @locale_doc
    async def togglelog_all(self, ctx, channel: discord.TextChannel = None):
        _(""" This enables all the logging """)

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:  # type: ignore
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        options = ['moderation', 'memberlog', 'joinlog', 'leavelog', 'guildlog', 'messageedits', 'messagedeletes']
        if not channel:
            count = 0
            for option in options:
                await self.bot.db.execute("DELETE from {0} WHERE guild_id = $1".format(option), ctx.guild.id)
                data = hasattr(self.bot, option)
                if data:
                    attr = getattr(self.bot, option)
                    try:
                        attr.pop(ctx.guild.id)
                    except Exception:
                        count += 1
            if count == 7:
                return await ctx.send(_("{0} Logs are currently disabled in this server."
                                        "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
            return await ctx.send(_("{0} Successfully disabled logging.").format(self.bot.settings['emojis']['misc']['white-mark']))
        else:
            query = """INSERT INTO {0}(guild_id, channel_id) VALUES($1, $2) ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2 WHERE {0}.guild_id = $1"""
            for option in options:
                await self.bot.db.execute(query.format(option), ctx.guild.id, channel.id)
                data = hasattr(self.bot, option)
                if data:
                    attr = getattr(self.bot, option)
                    attr[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Enabled logging in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                          channel.mention))

    @commands.command(name='anti-hoist', brief=_("Toggle anti hoist"))
    @moderator(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @locale_doc
    async def antihoist(self, ctx, channel: discord.TextChannel = None, new_nickname: str = None):
        _(""" Toggle anti hoist (non-alphabetic characters infront of the name, i.e. `! I'm a hoister`)
        When toggled on it will dehoist members that have just joined the server or have just edited their nickname """)

        check = self.bot.cache.get(self.bot, 'antihoist', ctx.guild.id)

        if new_nickname and len(new_nickname) > 32:
            return await ctx.send(_("{0} Nickname can't be longer than 32 characters over, you're {1} characters over.").format(self.bot.settings['emojis']['misc']['warn'], len(new_nickname) - 32))

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:  # type: ignore
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        if check and not channel:
            await self.bot.db.execute("DELETE from antihoist WHERE guild_id = $1", ctx.guild.id)
            self.bot.antihoist.pop(ctx.guild.id)
            return await ctx.send(_("{0} Anti hoist was successfully disabled.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif check:
            await self.bot.db.execute("UPDATE antihoist SET channel_id = $1, new_nick = $2 WHERE guild_id = $3", channel.id, new_nickname, ctx.guild.id)
            self.bot.antihoist[ctx.guild.id] = {'channel': channel.id, 'nickname': new_nickname}
            return await ctx.send(_("{0} Successfully updated the anti hoist logging channel to {1} and nickname to {2}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                  channel.mention, new_nickname))
        elif not channel:
            return await ctx.send(_("{0} Anti hoisting is currently disabled in this server."
                                    "\n*Hint: If you want to enable it, you need to provide a channel where logging should be sent to and a new nickname*").format(self.bot.settings['emojis']['misc']['warn']))
        else:
            await self.bot.db.execute("INSERT INTO antihoist VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.antihoist[ctx.guild.id] = {'channel': channel.id, 'nickname': new_nickname}
            return await ctx.send(_("{0} Enabled anti hoist logging in {1} and set the new nickname to {2}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                     channel.mention, new_nickname))

    @commands.group(brief=_("Edit the welcoming messages"), invoke_without_command=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    @locale_doc
    async def welcoming(self, ctx):
        _(""" Base command for managing welcoming messages in the server """)
        await ctx.send_help(ctx.command)

    @welcoming.command(name='channel', brief=_("Set the channel for welcoming messages"))
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_channels=True)
    @locale_doc
    async def welcoming_channel(self, ctx, *, channel: discord.TextChannel = None):
        _(""" Set a channel where welcoming messages should be sent to.
        Make sure bot has permissions to send messages in that channel. """)

        if channel and (not channel.can_send or not channel.permissions_for(ctx.guild.me).embed_links):  # type: ignore
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        joinmessages = self.bot.cache.get(self.bot, 'joinmessage', ctx.guild.id)

        if joinmessages and not channel:
            await self.bot.db.execute("DELETE from joinmessage WHERE guild_id = $1", ctx.guild.id)
            self.bot.joinmessage.pop(ctx.guild.id)
            return await ctx.send(_("{0} Disabled welcome messages.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif joinmessages:
            await self.bot.db.execute("UPDATE joinmessage SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.joinmessage[ctx.guild.id]['channel'] = channel.id
            return await ctx.send(_("{0} Enabled welcome messages in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                   channel.mention))
        elif not channel:
            return await ctx.send(_("{0} Welcome messages are currently disabled in this server."
                                    "\n*Hint: If you want to enable them you need to provide a channel where they should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        else:
            query = "INSERT INTO joinmessage(guild_id, embedded, log_bots, channel_id, message) VALUES($1, $2, $3, $4, $5)"
            await self.bot.db.execute(query, ctx.guild.id, False, True, channel.id, None)
            self.bot.joinmessage[ctx.guild.id] = {'message': None, 'embedded': False, 'log_bots': True, 'channel': channel.id}
            return await ctx.send(_("{0} Enabled welcome messages in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                   channel.mention))

    @welcoming.command(name='message',
                       brief=_("Set the welcoming message"),
                       aliases=['msg', 'm'])
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    @locale_doc
    async def welcoming_message(self, ctx, *, message: str = None):  # sourcery no-metrics
        _(""" Set the welcoming messages in the server
        Passing no message will reset your welcoming message to the default one.
         
         Formatting values:
         • `{{member.mention}}` for mention
         • `{{member.tag}}` for name and # 
         • `{{member.id}}` for id
         • `{{member.name}}` for name (markdown escaped)
         • `{{server.name}}` for server name
         • `{{server.members}}` for member count in server
         • `{0}` for member name
         • `{1}` for member count """)

        joinmessage = self.bot.cache.get(self.bot, 'joinmessage', ctx.guild.id)

        if not joinmessage:
            return await ctx.send(_("{0} You cannot set up welcome messages because they are not enabled!"
                                    "To enable them run `{1}welcoming channel [#channel]`").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                   ctx.prefix))

        if not joinmessage['embedded']:
            if not message:
                message = str(self.bot.settings['default']['join_message_text'])

            if joinmessage['message'] == message:
                return await ctx.send(_("{0} Your current welcome message is the same as the new one.").format(self.bot.settings['emojis']['misc']['warn']))
            if len(message) > 1000:
                return await ctx.send(_("{0} Welcome messages can't be longer than 1000 characters. You're {1} character(s) over the limit.").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                                                                     len(message) - 1000))
            await self.bot.db.execute("UPDATE joinmessage SET message = $1 WHERE guild_id = $2", message, ctx.guild.id)
            self.bot.joinmessage[ctx.guild.id]['message'] = message
            await ctx.send(_("{0} **Successfully set your welcome message to:**\n{1}").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                              message))

        else:
            if message:
                try:
                    jsonify = json.loads(message)
                except Exception:
                    return await ctx.send(_("{0} Your sent dict is invalid. Please "
                                            "use <https://embedbuilder.nadekobot.me/> to create an embed dict, then paste the code here.").format(self.bot.settings['emojis']['misc']['warn']))
            else:
                jsonify = self.bot.settings['default']['join_message_embed']

            if joinmessage['message'] == message:
                return await ctx.send(_("{0} Your current welcome message is the same as the new one.").format(self.bot.settings['emojis']['misc']['warn']))

            welcoming_embed = discord.Embed.from_dict(jsonify)
            if not welcoming_embed:
                return await ctx.send(_("{0} Your embed seems to be empty. Please "
                                        "use <https://embedbuilder.nadekobot.me/> to create an embed dict, then paste the code here.").format(self.bot.settings['emojis']['misc']['warn']))
            await self.bot.db.execute("UPDATE joinmessage SET message = $1 WHERE guild_id = $2", message, ctx.guild.id)
            self.bot.joinmessage[ctx.guild.id]['message'] = message
            plainText = '' if 'plainText' not in jsonify else _("\n**Plain Text:** {0}").format(jsonify['plainText'])
            await ctx.send(content=_("**Here is your new welcome embed:**{0}").format(plainText), embed=welcoming_embed)

    @welcoming.command(name='toggle',
                       brief=_("Toggle welcoming messages type"))
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    @locale_doc
    async def welcoming_toggle(self, ctx):
        _(""" Toggle welcoming messages between embedded and plain text. """)

        joinmessage = self.bot.cache.get(self.bot, 'joinmessage', ctx.guild.id)

        if not joinmessage:
            return await ctx.send(_("{0} You cannot set up welcome messages because they are not enabled!"
                                    "To enable them run `{1}welcoming channel [#channel]`").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                   ctx.prefix))

        if joinmessage['embedded']:
            await self.bot.db.execute("UPDATE joinmessage SET embedded = $1, message = $2 WHERE guild_id = $3", False, None, ctx.guild.id)
            self.bot.joinmessage[ctx.guild.id]['embedded'] = False
            self.bot.joinmessage[ctx.guild.id]['message'] = None
            await ctx.send(_("{0} Welcome messages will not be sent in embeds anymore.").format(self.bot.settings['emojis']['misc']['white-mark']))
        else:
            await self.bot.db.execute("UPDATE joinmessage SET embedded = $1, message = $2 WHERE guild_id = $3", True, None, ctx.guild.id)
            self.bot.joinmessage[ctx.guild.id]['embedded'] = True
            self.bot.joinmessage[ctx.guild.id]['message'] = None
            await ctx.send(_("{0} Welcome messages will now be sent in embeds.").format(self.bot.settings['emojis']['misc']['white-mark']))

    @welcoming.command(name='bots',
                       brief=_("Toggle bot welcoming messages"),
                       aliases=['robots', 'bot'])
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    @locale_doc
    async def welcoming_bots(self, ctx):
        _(""" Toggle whether or not bot joins should be logged. """)

        joinmessage = self.bot.cache.get(self.bot, 'joinmessage', ctx.guild.id)

        if not joinmessage:
            return await ctx.send(_("{0} You cannot set up welcome messages because they are not enabled!"
                                    "To enable them run `{1}welcoming channel [#channel]`").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                   ctx.prefix))

        if joinmessage['log_bots']:
            await self.bot.db.execute("UPDATE joinmessage SET log_bots = $1 WHERE guild_id = $2", False, ctx.guild.id)
            self.bot.joinmessage[ctx.guild.id]['log_bots'] = False
            await ctx.send(_("{0} I will no longer welcome bots.").format(self.bot.settings['emojis']['misc']['white-mark']))
        else:
            await self.bot.db.execute("UPDATE joinmessage SET log_bots = $1 WHERE guild_id = $2", True, ctx.guild.id)
            self.bot.joinmessage[ctx.guild.id]['log_bots'] = True
            await ctx.send(_("{0} I will now longer welcome bots.").format(self.bot.settings['emojis']['misc']['white-mark']))

    @commands.group(brief=_("Edit the leaving messages"), invoke_without_command=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    @locale_doc
    async def leaving(self, ctx):
        _(""" Base command for managing leaving messages in the server """)
        await ctx.send_help(ctx.command)

    @leaving.command(name='channel', brief=_("Set the channel for leaving messages"))
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_channels=True)
    @locale_doc
    async def leaving_channel(self, ctx, *, channel: discord.TextChannel = None):
        _(""" Set a channel where leaving messages should be sent to.
        Make sure bot has permissions to send messages in that channel. """)

        if channel and (not channel.can_send or not channel.permissions_for(ctx.guild.me).embed_links):  # type: ignore
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        leavemessages = self.bot.cache.get(self.bot, 'leavemessage', ctx.guild.id)

        if leavemessages and not channel:
            await self.bot.db.execute("DELETE from leavemessage WHERE guild_id = $1", ctx.guild.id)
            self.bot.leavemessage.pop(ctx.guild.id)
            return await ctx.send(_("{0} Leave messages are now disabled.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif leavemessages:
            await self.bot.db.execute("UPDATE leavemessage SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.leavemessage[ctx.guild.id]['channel'] = channel.id
            return await ctx.send(_("{0} I will now send leave messages in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                         channel.mention))
        elif not channel:
            return await ctx.send(_("{0} You don't have leave messages enabled in this server."
                                    "\n*Hint: If you want to enable them, you need to provide a channel where they should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        else:
            query = "INSERT INTO leavemessage(guild_id, embedded, log_bots, channel_id, message) VALUES($1, $2, $3, $4, $5)"
            await self.bot.db.execute(query, ctx.guild.id, False, True, channel.id, None)
            self.bot.leavemessage[ctx.guild.id] = {'message': None, 'embedded': False, 'log_bots': True, 'channel': channel.id}
            return await ctx.send(_("{0} Successfully enabled leave messages. I will now send leave messages in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                              channel.mention))

    @leaving.command(name='message',
                     brief=_("Set the leaving message"),
                     aliases=['msg', 'm'])
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    @locale_doc
    async def leaving_message(self, ctx, *, message: str = None):  # sourcery no-metrics
        _(""" Set the leaving messages in the server
        Passing no message will reset your leaving message to the default one
                 
         Formatting values:
         • `{{member.mention}}` for mention
         • `{{member.tag}}` for name and # 
         • `{{member.id}}` for id
         • `{{member.name}}` for name (markdown escaped)
         • `{{server.name}}` for server name
         • `{{server.members}}` for member count in server
         • `{0}` for member name
         • `{1}` for member count """)

        leavemessage = self.bot.cache.get(self.bot, 'leavemessage', ctx.guild.id)

        if not leavemessage:
            return await ctx.send(_("{0} Why are you trying to set up leave messages without having them toggled on? "
                                    "To enable them run `{1}leaving channel [#channel]`").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                 ctx.prefix))

        if not leavemessage['embedded']:
            if not message:
                message = str(self.bot.settings['default']['leave_message_text'])

            if leavemessage['message'] == message:
                return await ctx.send(_("{0} Your current leave message is the same as the new one.").format(self.bot.settings['emojis']['misc']['warn']))
            if len(message) > 1000:
                return await ctx.send(_("{0} Leave messages can't be longer than 1000 characters. You're {1} character(s) over the limit.").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                                                                   len(message) - 1000))
            await self.bot.db.execute("UPDATE leavemessage SET message = $1 WHERE guild_id = $2", message, ctx.guild.id)
            self.bot.leavemessage[ctx.guild.id]['message'] = message
            await ctx.send(_("{0} **Successfully set your leave message to:**\n{1}").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                            message))

        else:
            if message:
                try:
                    jsonify = json.loads(message)
                except Exception:
                    return await ctx.send(_("{0} Your sent dict is invalid. Please "
                                            "use <https://embedbuilder.nadekobot.me/> to create an embed dict and then paste that code.").format(self.bot.settings['emojis']['misc']['warn']))
            else:
                jsonify = self.bot.settings['default']['leave_message_embed']

            if leavemessage['message'] == message:
                return await ctx.send(_("{0} Your current leave message is the same as the new one.").format(self.bot.settings['emojis']['misc']['warn']))

            leaving_embed = discord.Embed.from_dict(jsonify)
            if not leaving_embed:
                return await ctx.send(_("{0} Your embed seems to be empty. Please "
                                        "use <https://embedbuilder.nadekobot.me/> to create an embed dict and then paste that code.").format(self.bot.settings['emojis']['misc']['warn']))
            await self.bot.db.execute("UPDATE leavemessage SET message = $1 WHERE guild_id = $2", message, ctx.guild.id)
            self.bot.leavemessage[ctx.guild.id]['message'] = message
            plainText = '' if 'plainText' not in jsonify else _("\n**Plain Text:** {0}").format(jsonify['plainText'])
            await ctx.send(content=_("**Here is your new leave member embed message:**{0}").format(plainText), embed=leaving_embed)

    @leaving.command(name='toggle',
                     brief=_("Toggle leaving messages type"))
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    @locale_doc
    async def leaving_toggle(self, ctx):
        _(""" Toggle leaving messages between embedded and plain text. """)

        leavemessage = self.bot.cache.get(self.bot, 'leavemessage', ctx.guild.id)

        if not leavemessage:
            return await ctx.send(_("{0} Why are you trying to setup leaving messages "
                                    "without having them toggled on? To enable them run `{1}leaving channel [#channel]`").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                                                 ctx.prefix))

        if leavemessage['embedded']:
            await self.bot.db.execute("UPDATE leavemessage SET embedded = $1, message = $2 WHERE guild_id = $3", False, None, ctx.guild.id)
            self.bot.leavemessage[ctx.guild.id]['embedded'] = False
            self.bot.leavemessage[ctx.guild.id]['message'] = None
            await ctx.send(_("{0} Leave messages will no longer be sent in embeds.").format(self.bot.settings['emojis']['misc']['white-mark']))
        else:
            await self.bot.db.execute("UPDATE leavemessage SET embedded = $1, message = $2 WHERE guild_id = $3", True, None, ctx.guild.id)
            self.bot.leavemessage[ctx.guild.id]['embedded'] = True
            self.bot.leavemessage[ctx.guild.id]['message'] = None
            await ctx.send(_("{0} Leave messages will now be sent in embeds.").format(self.bot.settings['emojis']['misc']['white-mark']))

    @leaving.command(name='bots',
                     brief=_("Toggle bot leaving"),
                     aliases=['robots', 'bot'])
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    @locale_doc
    async def leaving_bots(self, ctx):
        _(""" Toggle whether or not bot leaves should be logged. """)

        leavemessage = self.bot.cache.get(self.bot, 'leavemessage', ctx.guild.id)

        if not leavemessage:
            return await ctx.send(_("{0} Why are you trying to setup leaving messages "
                                    "without having them toggled on? To enable them run `{1}leaving channel [#channel]`").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                                                 ctx.prefix))

        if leavemessage['log_bots']:
            await self.bot.db.execute("UPDATE leavemessage SET log_bots = $1 WHERE guild_id = $2", False, ctx.guild.id)
            self.bot.leavemessage[ctx.guild.id]['log_bots'] = False
            await ctx.send(_("{0} Bot leave messages have been turned off.").format(self.bot.settings['emojis']['misc']['white-mark']))
        else:
            await self.bot.db.execute("UPDATE leavemessage SET log_bots = $1 WHERE guild_id = $2", True, ctx.guild.id)
            self.bot.leavemessage[ctx.guild.id]['log_bots'] = True
            await ctx.send(_("{0} Bot leave messages have been turned on.").format(self.bot.settings['emojis']['misc']['white-mark']))

    @commands.group(name='joinrole',
                    brief=_("Toggle role on join"),
                    invoke_without_command=True)
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def joinrole(self, ctx):
        _(""" Base command for managing role on join """)
        await ctx.send_help(ctx.command)

    @joinrole.group(name='people',
                    brief=_("Set role on join for users"),
                    aliases=['humans'],
                    invoke_without_command=True)
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def joinrole_people(self, ctx):
        _(""" Choose what role will be given to new users """)

        await ctx.send_help(ctx.command)

    @joinrole_people.command(name='add',
                             brief=_("Add a role on join for people"),
                             aliases=['a'])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def joinrole_people_add(self, ctx, *, role: discord.Role):
        # sourcery skip: remove-redundant-if, remove-unnecessary-else
        _(""" Add a role to role on join for people """)

        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)
        mod_role = self.bot.cache.get(self.bot, 'mod_role', ctx.guild.id)
        admin_role = self.bot.cache.get(self.bot, 'admin_role', ctx.guild.id)

        if not joinrole:
            return await ctx.send(_("{0} Role on join is not enabled in this server, please use "
                                    "`{1}joinrole toggle` to enable it.").format(self.bot.settings['emojis']['misc']['warn'], ctx.prefix))
        elif joinrole:
            if role and role.id in (mod_role, admin_role):
                return await ctx.send(_("{0} You cannot set that role as it is configured as mod or admin role").format(self.bot.settings['emojis']['misc']['warn']))
            if role.position >= ctx.guild.me.top_role.position:
                return await ctx.send(_("{0} The role you're trying to setup is higher in role hierarchy and I cannot access it.").format(
                    self.bot.settings['emojis']['misc']['warn']
                ))
            if role.id in joinrole['people']:
                return await ctx.send(_("{0} That role is already added to role on join list.").format(self.bot.settings['emojis']['misc']['warn']))
            await self.bot.db.execute("INSERT INTO joinrole(guild_id, role) VALUES($1, $2)", ctx.guild.id, role.id)
            if joinrole['people']:
                joinrole['people'].append(role.id)
            elif not joinrole['people']:
                joinrole['people'] = [role.id]

            await ctx.send(_("{0} Added {1} to join role for people.").format(self.bot.settings['emojis']['misc']['white-mark'], role.mention))

    @joinrole_people.command(name='remove',
                             brief=_("Remove a role on join for people"),
                             aliases=['r'])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def joinrole_people_remove(self, ctx, *, role: discord.Role):
        _(""" Remove a role from role on join for people """)

        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)

        if not joinrole:
            return await ctx.send(_("{0} Role on is not enabled in this server, please use "
                                    "`{1}joinrole toggle` to enable it.").format(self.bot.settings['emojis']['misc']['warn'], ctx.prefix))

        if role.id not in joinrole['people']:
            return await ctx.send(_("{0} That role is not added to role on join list.").format(self.bot.settings['emojis']['misc']['warn']))
        await self.bot.db.execute("DELETE FROM joinrole WHERE guild_id = $1 AND role = $2", ctx.guild.id, role.id)
        joinrole['people'].remove(role.id)

        await ctx.send(_("{0} Removed {1} from join role for people.").format(self.bot.settings['emojis']['misc']['white-mark'], role.mention))

    @joinrole_people.command(name='list',
                             brief=_("See all the roles on join for people"),
                             aliases=['l'])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def joinrole_people_list(self, ctx):
        _(""" See all the roles for role on join for people """)

        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)

        if not joinrole:
            return await ctx.send(_("{0} Role on is not enabled in this server, please use "
                                    "`{1}joinrole toggle` to enable it.").format(self.bot.settings['emojis']['misc']['warn'], ctx.prefix))
        elif joinrole['people']:
            list_of_roles = []
            for num, role in enumerate(joinrole['people'], start=1):
                the_role = ctx.guild.get_role(role)

                list_of_roles.append("`[{0}]` {1} ({2})\n".format(num, the_role.mention if the_role else _('Role not found'), role))

            paginator = Pages(ctx,
                              title=_("Role on join for people"),
                              entries=list_of_roles,
                              per_page=15,
                              embed_color=self.bot.settings['colors']['embed_color'],
                              author=ctx.author)
            await paginator.paginate()

        else:
            return await ctx.send(_("{0} There are no role on join roles for people set.").format(self.bot.settings['emojis']['misc']['warn']))

    @joinrole.group(name='bots',
                    brief=_("Set role on join for bots"),
                    aliases=['robots'],
                    invoke_without_command=True)
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def joinrole_bots(self, ctx):
        _(""" Manage role on join for bots """)

        await ctx.send_help(ctx.command)

    @joinrole_bots.command(name='add',
                           brief=_("Add a role on join for bots"),
                           aliases=['a'])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def joinrole_bots_add(self, ctx, *, role: discord.Role):
        _(""" Add a role to role on join for bots """)

        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)
        mod_role = self.bot.cache.get(self.bot, 'mod_role', ctx.guild.id)
        admin_role = self.bot.cache.get(self.bot, 'admin_role', ctx.guild.id)

        if not joinrole:
            return await ctx.send(_("{0} Role on is not enabled in this server, please use "
                                    "`{1}joinrole toggle` to enable it.").format(self.bot.settings['emojis']['misc']['warn'], ctx.prefix))

        if role and role.id in (mod_role, admin_role):
            return await ctx.send(_("{0} You cannot set that role as it is configured as mod or admin role").format(self.bot.settings['emojis']['misc']['warn']))
        if role.position >= ctx.guild.me.top_role.position:
            return await ctx.send(_("{0} The role you're trying to setup is higher in role hierarchy and I cannot access it.").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        if role.id in joinrole['bots']:
            return await ctx.send(_("{0} That role is already added to role on join list.").format(self.bot.settings['emojis']['misc']['warn']))
        await self.bot.db.execute("INSERT INTO joinrole(guild_id, botrole) VALUES($1, $2)", ctx.guild.id, role.id)
        if joinrole['bots']:
            joinrole['bots'].append(role.id)
        else:
            joinrole['bots'] = [role.id]

        await ctx.send(_("{0} Added {1} to join role for bots.").format(self.bot.settings['emojis']['misc']['white-mark'], role.mention))

    @joinrole_bots.command(name='remove',
                           brief=_("Remove a role on join for bots"),
                           aliases=['r'])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def joinrole_bots_remove(self, ctx, *, role: discord.Role):
        _(""" Remove a role from role on join for bots """)

        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)

        if not joinrole:
            return await ctx.send(_("{0} Role on is not enabled in this server, please use "
                                    "`{1}joinrole toggle` to enable it.").format(self.bot.settings['emojis']['misc']['warn'], ctx.prefix))

        if role.id not in joinrole['bots']:
            return await ctx.send(_("{0} That role is not added to role on join list.").format(self.bot.settings['emojis']['misc']['warn']))
        await self.bot.db.execute("DELETE FROM joinrole WHERE guild_id = $1 AND botrole = $2", ctx.guild.id, role.id)
        joinrole['bots'].remove(role.id)

        await ctx.send(_("{0} Removed {1} from join role for bots.").format(self.bot.settings['emojis']['misc']['white-mark'], role.mention))

    @joinrole_bots.command(name='list',
                           brief=_("See all the roles on join for bots"),
                           aliases=['l'])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def joinrole_bots_list(self, ctx):
        _(""" See all the roles for role on join for bots """)

        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)

        if not joinrole:
            return await ctx.send(_("{0} Role on is not enabled in this server, please use "
                                    "`{1}joinrole toggle` to enable it.").format(self.bot.settings['emojis']['misc']['warn'], ctx.prefix))
        elif joinrole['bots']:
            list_of_roles = []
            for num, role in enumerate(joinrole['bots'], start=1):
                the_role = ctx.guild.get_role(role)

                list_of_roles.append("`[{0}]` {1} ({2})\n".format(num, the_role.mention if the_role else _('Role not found'), role))

            paginator = Pages(ctx,
                              title=_("Role on join for bots"),
                              entries=list_of_roles,
                              per_page=15,
                              embed_color=self.bot.settings['colors']['embed_color'],
                              author=ctx.author)
            await paginator.paginate()

        else:
            return await ctx.send(_("{0} There are no role on join roles for bots set.").format(self.bot.settings['emojis']['misc']['warn']))

    @joinrole.command(name='toggle',
                      brief=_("Toggle role on join"),
                      aliases=['tog'])
    @admin(manage_roles=True)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @locale_doc
    async def joinrole_toggle(self, ctx):
        _(""" Toggle role on join on and off """)

        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)

        if not joinrole:
            await self.bot.db.execute("INSERT INTO joinrole(guild_id) VALUES($1)", ctx.guild.id)
            self.bot.joinrole[ctx.guild.id] = {'people': [], 'bots': []}
            await ctx.send(_("{0} Role on join was toggled on, you can now set the roles using "
                             "`{1}joinrole [people|bots] [add|remove] <role>`").format(self.bot.settings['emojis']['misc']['white-mark'], ctx.prefix))
        else:
            await self.bot.db.execute("DELETE FROM joinrole WHERE guild_id = $1", ctx.guild.id)
            self.bot.joinrole.pop(ctx.guild.id)
            await ctx.send(_("{0} I've successfuly disabled role on join.").format(self.bot.settings['emojis']['misc']['white-mark']))

    @commands.command(name='muterole',
                      brief=_("Set a custom mute role"),
                      aliases=['silentrole'])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def muterole(self, ctx, arg: typing.Union[discord.Role, str]):
        _(""" Setup a custom mute role in your server
        You can also reset the mute role by using argument `reset` """)

        mute_role = self.bot.cache.get(self.bot, 'mute_role', ctx.guild.id)

        if isinstance(arg, str):
            if arg == "reset" and mute_role:
                await self.bot.db.execute("DELETE FROM muterole WHERE guild_id = $1", ctx.guild.id)
                self.bot.mute_role.pop(ctx.guild.id)
                await ctx.send(_("{0} The mute role has been reset.").format(self.bot.settings['emojis']['misc']['white-mark']))
            elif arg == "reset":
                await ctx.send(_("{0} You do not have a mute role set up.").format(self.bot.settings['emojis']['misc']['warn']))
            else:
                return await ctx.send(_("{0} That role was not found! If you're trying to reset the mute role, you can use `reset` as the argument.").format(self.bot.settings['emojis']['misc']['warn']))
        if isinstance(arg, discord.Role):
            if arg.position >= ctx.guild.me.top_role.position:
                return await ctx.send(_("{0} The role you're trying to set as the mute role is higher than me in the role hierarchy!\n"
                                        "Please move the role lower in the hierarchy or choose a role in the hierarchy.").format(self.bot.settings['emojis']['misc']['warn']))
            if arg.permissions.send_messages:
                return await ctx.send(_("{0} The role you're trying to set as the mute role has the send messages permission.\n"
                                        "You can only set up roles without the send messages permission.").format(self.bot.settings['emojis']['misc']['warn']))
            if not mute_role:
                await self.bot.db.execute("INSERT INTO muterole(guild_id, role) VALUES($1, $2)", ctx.guild.id, arg.id)
                self.bot.mute_role[ctx.guild.id] = arg.id
                await ctx.send(_("{0} Set the muted role to {1}").format(self.bot.settings['emojis']['misc']['white-mark'], arg.mention))
            else:
                await self.bot.db.execute("UPDATE muterole SET role = $1 WHERE guild_id = $2", arg.id, ctx.guild.id)
                self.bot.mute_role[ctx.guild.id] = arg.id
                await ctx.send(_("{0} Updated the muted role to {1}").format(self.bot.settings['emojis']['misc']['white-mark'], arg.mention))

    @commands.command(name='modrole',
                      brief=_("Set a custom mod role"),
                      aliases=['moderatorrole'])
    @admin(administrator=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @locale_doc
    async def modrole(self, ctx, arg: typing.Union[discord.Role, str]):
        _(""" Setup a custom mod role in your server
        You can also reset the mod role by using argument `reset` """)

        mod_role = self.bot.cache.get(self.bot, 'mod_role', ctx.guild.id)
        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)

        if isinstance(arg, str):
            if arg == "reset" and mod_role:
                await self.bot.db.execute("DELETE FROM modrole WHERE guild_id = $1", ctx.guild.id)
                self.bot.mod_role.pop(ctx.guild.id)
                await ctx.send(_("{0} Successfully reset the moderator role.").format(self.bot.settings['emojis']['misc']['white-mark']))
            elif arg == "reset":
                await ctx.send(_("{0} You don't have a custom moderator role setup.").format(self.bot.settings['emojis']['misc']['warn']))
            else:
                return await ctx.send(_("{0} Role was not found, if you're trying to reset the "
                                        "custom moderator role, you can use `reset` arg.").format(self.bot.settings['emojis']['misc']['warn']))
        if isinstance(arg, discord.Role):
            if not arg.permissions.manage_messages:
                return await ctx.send(_("{0} Due to safety reasons, moderator role must at least have manage messages permissions").format(
                    self.bot.settings['emojis']['misc']['warn']
                ))
            if joinrole and arg.id in (joinrole['people'] or joinrole['bots']):
                return await ctx.send(_("{0} You cannot set that role as it is given to new members").format(self.bot.settings['emojis']['misc']['warn']))
            if not mod_role:
                await self.bot.db.execute("INSERT INTO modrole(guild_id, role) VALUES($1, $2)", ctx.guild.id, arg.id)
                self.bot.mod_role[ctx.guild.id] = arg.id
                await ctx.send(_("{0} Set a custom moderator role to {1}").format(self.bot.settings['emojis']['misc']['white-mark'], arg.mention))
            else:
                await self.bot.db.execute("UPDATE modrole SET role = $1 WHERE guild_id = $2", arg.id, ctx.guild.id)
                self.bot.mod_role[ctx.guild.id] = arg.id
                await ctx.send(_("{0} Changed a custom moderator role to {1}").format(self.bot.settings['emojis']['misc']['white-mark'], arg.mention))

    @commands.command(name='adminrole',
                      brief=_("Set a custom admin role"),
                      aliases=['administratorrole'])
    @admin(administrator=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @locale_doc
    async def adminrole(self, ctx, arg: typing.Union[discord.Role, str]):
        _(""" Setup a custom admin role in your server
        You can also reset the admin role by using argument `reset` """)

        admin_role = self.bot.cache.get(self.bot, 'admin_role', ctx.guild.id)
        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)

        if isinstance(arg, str):
            if arg == "reset" and admin_role:
                await self.bot.db.execute("DELETE FROM adminrole WHERE guild_id = $1", ctx.guild.id)
                self.bot.admin_role.pop(ctx.guild.id)
                await ctx.send(_("{0} I've reset your admin role.").format(self.bot.settings['emojis']['misc']['white-mark']))
            elif arg == "reset":
                await ctx.send(_("{0} You don't have a custom admin role setup.").format(self.bot.settings['emojis']['misc']['warn']))
            else:
                return await ctx.send(_("{0} Role was not found, if you're trying to reset the "
                                        "custom admin role, you can use `reset` arg.").format(self.bot.settings['emojis']['misc']['warn']))
        if isinstance(arg, discord.Role):
            if not arg.permissions.ban_members:
                return await ctx.send(_("{0} Due to safety reasons, admin role must at least have ban members permissions").format(
                    self.bot.settings['emojis']['misc']['warn']
                ))
            if joinrole and arg.id in (joinrole['people'] or joinrole['bots']):
                return await ctx.send(_("{0} You cannot set that role as it is given to new members").format(self.bot.settings['emojis']['misc']['warn']))
            if not admin_role:
                await self.bot.db.execute("INSERT INTO adminrole(guild_id, role) VALUES($1, $2)", ctx.guild.id, arg.id)
                self.bot.admin_role[ctx.guild.id] = arg.id
                await ctx.send(_("{0} Set a custom admin role to {1}").format(self.bot.settings['emojis']['misc']['white-mark'], arg.mention))
            else:
                await self.bot.db.execute("UPDATE adminrole SET role = $1 WHERE guild_id = $2", arg.id, ctx.guild.id)
                self.bot.admin_role[ctx.guild.id] = arg.id
                await ctx.send(_("{0} Changed a custom admin role to {1}").format(self.bot.settings['emojis']['misc']['white-mark'], arg.mention))

    @commands.command(name='disable-command',
                      brief=_("Disable a command in the server"),
                      aliases=['disablecommand', 'discmd'])
    @admin(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def disable_command(self, ctx, *, command: str):
        _(""" Disable a command in the server """)

        cmd = self.bot.get_command(command)

        if not cmd:
            return await ctx.send(_("{0} {1} command was not found.").format(
                self.bot.settings['emojis']['misc']['warn'], command
            ))

        if cmd.qualified_name in ['disable-command', 'disable-category']:
            return await ctx.send(_("{0} You can't disable that command!").format(self.bot.settings['emojis']['misc']['warn']))

        if await is_guild_disabled(ctx, cmd):
            return await ctx.send(_("{0} That command is already disabled.").format(self.bot.settings['emojis']['misc']['warn']))

        command = cmd

        if command.parent:
            if not command.name:
                self.bot.guild_disabled[f"{command.parent}, {ctx.guild.id}"] = str(command.parent)
                await self.bot.db.execute("INSERT INTO guild_disabled(guild_id, command) VALUES($1, $2)", ctx.guild.id, str(command.parent))
                await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent}` and its corresponding subcommands were successfully disabled")
            else:
                self.bot.guild_disabled[f'{command.parent} {command.name}, {ctx.guild.id}'] = str(commands.parent)
                await self.bot.db.execute("INSERT INTO guild_disabled(guild_id, command) VALUES($1, $2)", ctx.guild.id, str(f"{command.parent} {command.name}"))
                await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent} {command.name}` and its corresponding subcommands were successfully disabled")
        else:
            self.bot.guild_disabled[f'{command}, {ctx.guild.id}'] = str(command.name)
            await self.bot.db.execute("INSERT INTO guild_disabled(guild_id, command) VALUES($1, $2)", ctx.guild.id, str(command.name))
            await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command}` was successfully disabled")

    @commands.command(name='enable-command',
                      brief=_("Enable a command in the server"),
                      aliases=['enablecommand', 'enbcmd'])
    @admin(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def enable_command(self, ctx, *, command: str):
        _(""" Enable a command in the server """)

        cmd = self.bot.get_command(command)

        if not cmd:
            return await ctx.send(_("{0} {1} command was not found.").format(
                self.bot.settings['emojis']['misc']['warn'], command
            ))

        if not await is_guild_disabled(ctx, cmd):
            return await ctx.send(_("{0} That command is not disabled.").format(self.bot.settings['emojis']['misc']['warn']))

        command = cmd

        if command.parent:
            if not command.name:
                self.bot.guild_disabled.pop(f"{command.parent}, {ctx.guild.id}")
                await self.bot.db.execute("DELETE FROM guild_disabled WHERE command = $1 AND guild_id = $2", str(command.parent), ctx.guild.id)
                await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent}` and its corresponding subcommands were successfully re-enabled")
            else:
                self.bot.guild_disabled.pop(f"{command.parent} {command.name}, {ctx.guild.id}")
                await self.bot.db.execute("DELETE FROM guild_disabled WHERE command = $1 AND guild_id = $2", str(f"{command.parent} {command.name}"), ctx.guild.id)
                await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent} {command.name}` and its corresponding subcommands were successfully re-enabled")
        else:
            self.bot.guild_disabled.pop(f'{command}, {ctx.guild.id}')
            await self.bot.db.execute("DELETE FROM guild_disabled WHERE command = $1 AND guild_id = $2", str(command), ctx.guild.id)
            await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command}` was successfully re-enabled")

    @commands.command(name='disable-category',
                      brief=_("Disable category in the server"),
                      aliases=['disable-cog', 'disablecog'])
    @admin(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def disable_category(self, ctx, *, category: str):
        _(""" Disable category you don't want people to use in the server """)

        cog = self.bot.get_cog(category.title())

        if not cog:
            return await ctx.send(_("{0} {1} category was not found.").format(
                self.bot.settings['emojis']['misc']['warn'], category.title()
            ))

        cant_disable = ["Help", "Events", "CommandError", "Logging", 'Tasks', "AutomodEvents", 'Management', 'Owner', 'Staff']
        if cog.qualified_name in cant_disable:
            return await ctx.send(_("{0} You can't disable that category!").format(self.bot.settings['emojis']['misc']['warn']))

        if self.bot.cache.get(self.bot, 'cog_disabled', f"{ctx.guild.id}, {cog.qualified_name}"):
            return await ctx.send(_("{0} That category is already disabled.").format(self.bot.settings['emojis']['misc']['warn']))

        self.bot.cog_disabled[f"{ctx.guild.id}, {cog.qualified_name}"] = str(cog.qualified_name)
        await self.bot.db.execute("INSERT INTO cog_disabled(guild_id, cog) VALUES($1, $2)", ctx.guild.id, cog.qualified_name)
        await ctx.send(_("{0} Category {1} was successfully disabled").format(
            self.bot.settings['emojis']['misc']['white-mark'], cog.qualified_name
        ))

    @commands.command(name='enable-category',
                      brief=_("Enable category in the server"),
                      aliases=['enable-cog', 'enablecog'])
    @admin(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def enable_category(self, ctx, *, category: str):
        _(""" Enable category which you've previously disbled """)

        cog = self.bot.get_cog(category.title())

        if not cog:
            return await ctx.send(_("{0} {1} category was not found.").format(
                self.bot.settings['emojis']['misc']['warn'], category.title()
            ))

        if not self.bot.cache.get(self.bot, 'cog_disabled', f"{ctx.guild.id}, {cog.qualified_name}"):
            return await ctx.send(_("{0} That category is not disabled.").format(self.bot.settings['emojis']['misc']['warn']))

        self.bot.cog_disabled.pop(f"{ctx.guild.id}, {cog.qualified_name}")
        await self.bot.db.execute("DELETE FROM cog_disabled WHERE cog = $1 AND guild_id = $2", cog.qualified_name, ctx.guild.id)
        await ctx.send(_("{0} Category {1} was successfully re-enabled").format(
            self.bot.settings['emojis']['misc']['white-mark'], cog.qualified_name
        ))

    @commands.group(name='reaction-roles',
                    brief=_("Setup reaction roles in the server"),
                    aliases=['rr', 'rroles', 'reactroles', 'reactionroles'],
                    invoke_without_command=True)
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True, manage_messages=True)
    @commands.guild_only()
    @locale_doc
    async def reaction_roles(self, ctx):
        _(""" Base command for managing reaction roles """)
        await ctx.send_help(ctx.command)

    @reaction_roles.command(name="setup",
                            brief=_("Setup the reaction roles in your server."),
                            aliases=["set"])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True, manage_messages=True)
    @commands.max_concurrency(1, commands.cooldowns.BucketType.guild)
    @commands.guild_only()
    @locale_doc
    async def reaction_roles_setup(self, ctx):
        _(""" Interactive setup for reaction roles. """)

        self.bot.rr_setup[(ctx.author.id, ctx.channel.id)] = {
            "message_type": enums.ReactionRolesType.unknown,
            "author": enums.ReactionRolesAuthor.unknown,
            "channel": None,
            "message": None,
            "using_components": False,
            "use_components": False,
            "components_style": enums.ReactionRolesComponentDisplay.unknown,
            "limits": {
                "required_role": None,
                "max_roles": None
            },
            "message_style": {
                "type": enums.ReactionRolesMessageType.unknown,
                "payload": None,
                "edit_old": False
            },
            "payload": None
        }

        try:
            message_type_view = components.ReactionRolesView(self, ctx, placeholder=_("Select an option..."), options=[
                discord.SelectOption(label="New message", value=int(enums.ReactionRolesType.new_message), description="Creates a new message for you."),  # type: ignore
                discord.SelectOption(label="Existing message", value=int(enums.ReactionRolesType.existing_message), description="Adds reaction roles to an already existing message."),  # type: ignore
                discord.SelectOption(label="Cancel", value=2, description="Cancel the setup.")  # type: ignore
            ], getting="")
            await ctx.channel.send(_("Do you want me to use an already existing message or set up a new one?"), view=message_type_view)
        except Exception as e:
            return await ctx.send(e)

    @reaction_roles.command(name='list', aliases=['l'], brief=_("Get a list of reaction roles in the server"))
    @admin(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def reaction_roles_list(self, ctx):
        _(""" Get a list of reaction roles in the server """)

        check = await self.bot.db.fetch("SELECT * FROM reactionroles WHERE guild_id = $1", ctx.guild.id)

        if not check:
            raise commands.BadArgument(_("No reaction roles are setup in this server."))

        list_of_messageids = [data["message_id"] for data in check]

        list_of_reactionroles = []
        for messageid in list_of_messageids:
            cache = self.bot.cache.get_message(self.bot, messageid)

            if not cache:
                await self.bot.db.execute("DELETE FROM reactionroles WHERE message_id = $1", messageid)
                continue

            roles = [ctx.guild.get_role(cache.raw_dict[role]) for role in cache.raw_dict]

            channel = ctx.guild.get_channel(cache.channel)
            message = messageid
            with suppress(Exception):
                msg = await channel.fetch_message(messageid)
                message = _("[Jump URL]({0})").format(msg.jump_url)

            roles = ', '.join([x.mention if x else str(x) for x in roles][:10]) + f" (+{len(roles) - 10})" if len(roles) > 10 else ', '.join(x.mention if x else str(x) for x in roles)

            list_of_reactionroles.append(_("**Message:** {0}\n**Channel:** {1}\n**Reactions:** {2}\n**Roles:** {3}\n**Roles limit:** {4}\n**Required role:** {5}\n\n").format(  # sourcery skip
                message, channel.mention if channel else _('Deleted'), ', '.join([x for x in cache.raw_dict][:10]) + f" (+{len(cache.raw_dict) - 10})" if len(cache.raw_dict) > 10 else ', '.join(x for x in cache.raw_dict),
                roles, cache.max_roles,
                ctx.guild.get_role(cache.required_role).mention if ctx.guild.get_role(cache.required_role) else None
            ))

        paginator = Pages(ctx,
                          title=_("Reaction roles in {0}").format(ctx.guild.name),
                          entries=list_of_reactionroles,
                          per_page=3,
                          embed_color=self.bot.settings['colors']['embed_color'],
                          author=ctx.author)
        await paginator.paginate()

    @reaction_roles.command(name='delete', aliases=['del'], brief=_("Delete reaction roles in the server"))
    @admin(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def reaction_roles_delete(self, ctx, message_id: str):
        _(""" Delete reaction roles in the server """)

        if not message_id.isdigit():
            raise commands.BadArgument(_("Message ID must not include letters, only numbers"))

        get_menu = self.bot.cache.get(self.bot, 'rr', int(message_id))

        if not get_menu:
            raise commands.BadArgument(_("Reaction role for that message doesn't exist. Please use `{0}reaction-roles list` to get a list of all the reaction roles").format(ctx.prefix))

        await self.bot.db.execute("DELETE FROM reactionroles WHERE message_id = $1 AND guild_id = $2", int(message_id), ctx.guild.id)
        self.bot.rr.pop(int(message_id))
        channel = ctx.guild.get_channel(get_menu['channel'])
        message = message_id
        if channel:
            try:
                message = await channel.fetch_message(int(message_id))
                await message.clear_reactions()
                if message.author == ctx.guild.me:
                    await message.edit(view=None)
                message = f"<{message.jump_url}>"
            except Exception:
                pass

        await ctx.send(_("{0} Successfully deleted reaction roles for message {1}").format(self.bot.settings['emojis']['misc']['white-mark'], message))


def setup(bot):
    bot.add_cog(Manage(bot))
