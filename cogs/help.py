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
import difflib

from discord.ext import commands
from utils.paginator import Pages
from utils import checks
from db.cache import CacheManager as cm
from utils.components import DropdownView
from utils.default import permissions_converter


def setup(bot):
    bot.help_command = HelpCommand()
    bot.help_command.cog = bot.get_cog('Information')


# noinspection PyUnboundLocalVariable,PyArgumentEqualDefault
class HelpCommand(commands.HelpCommand):
    def __init__(self, *args, **kwargs):
        super().__init__()

        self.command_attrs = {
                         'help': _('Shows help about bot and/or commands'),
                         'brief': _('See cog/command help'),
                         'usage': '[category / command]',
                         'cooldown': commands.CooldownMapping(type=commands.BucketType.user, original=commands.Cooldown(1, 10)),
                         'name': 'help'}
        self.show_hidden = False
        self.verify_checks = True
        self.help_icon = ''
        self.big_icon = ''
        self.message = None

        self.owner_cogs = ['Owner', 'Devishaku', 'Jishaku']
        self.admin_cogs = ['Staff']
        self.booster_cogs = ['Boosters']
        self.ignore_cogs = ["Help", "Events", "CommandError", "Logging", 'Tasks', "AutomodEvents", 'DiscordExtremeList', 'DiscordLabs', 'DiscordLists', 'ShitGG', 'Others']

    def get_command_signature(self, command):
        if command.cog is None:
            return f"None | {command.qualified_name}"
        else:
            return f"{command.cog.qualified_name} | {command.qualified_name}"

    async def command_callback(self, ctx, *, command=None):

        await self.prepare_help_command(ctx, command)

        if command is None:
            mapping = self.get_bot_mapping()
            return await self.send_bot_help(mapping)

        # Check if it's a cog
        cog = ctx.bot.get_cog(command.title())
        if cog is not None:
            return await self.send_cog_help(cog)

        maybe_coro = discord.utils.maybe_coroutine

        # If it's not a cog then it's a command.
        # Since we want to have detailed errors when someone
        # passes an invalid subcommand, we need to walk through
        # the command group chain ourselves.
        keys = command.split(' ')
        cmd = ctx.bot.all_commands.get(keys[0])
        if cmd is None:
            string = await maybe_coro(self.command_not_found, self.remove_mentions(keys[0]))
            return await self.send_error_message(string)

        for key in keys[1:]:
            try:
                found = cmd.all_commands.get(key)
            except AttributeError:
                string = await maybe_coro(self.subcommand_not_found, cmd, self.remove_mentions(key))
                return await self.send_error_message(string)
            else:
                if found is None:
                    string = await maybe_coro(self.subcommand_not_found, cmd, self.remove_mentions(key))
                    return await self.send_error_message(string)
                cmd = found

        if isinstance(cmd, commands.Group):
            return await self.send_group_help(cmd)
        else:
            return await self.send_command_help(cmd)

    async def send_bot_help(self, mapping):  # sourcery no-metrics
        """ See bot help """
        ctx = self.context

        Moksej = f"[{self.context.bot.get_user(345457928972533773)}](https://discord.com/users/345457928972533773)"

        support = self.context.bot.support
        invite = self.context.bot.invite
        if self.context.guild is not None:
            p = cm.get(self.context.bot, 'prefix', self.context.guild.id)
            prefix = _("**Prefix:** `{0}`").format(p)
        else:
            prefix = _("**Prefix:** `!`")
        s = _("Support")
        i = _("Bot invite")
        boats = "[discord.boats](https://discord.boats/bot/667117267405766696/vote)"
        privacy = "[Privacy Policy](https://dredd-bot.xyz/privacy)"

        emb = discord.Embed(color=self.context.bot.settings['colors']['embed_color'])
        emojis = self.context.bot.settings['emojis']
        emb.description = (f"{emojis['social']['discord']} [{s}]({support}) | {emojis['avatars']['main']} [{i}]({invite}) "
                           f"| {emojis['misc']['boats']} {boats} | {emojis['social']['privacy']} {privacy}\n\n**Made by:** {Moksej}\n{prefix}\n\n")

        exts, to_sort, options = [], [], []
        for extension in set(self.context.bot.cogs.values()):
            if extension.qualified_name in self.ignore_cogs:
                continue
            if extension.qualified_name == "Devishaku":
                continue
            if extension.qualified_name in self.owner_cogs and not await self.context.bot.is_owner(self.context.author):
                continue
            if extension.qualified_name in self.admin_cogs and not await self.context.bot.is_admin(self.context.author):
                continue
            if extension.qualified_name in self.booster_cogs and not await self.context.bot.is_booster(self.context.author):
                continue
            if await checks.cog_disabled(self.context, str(extension.qualified_name)):
                continue
            to_sort.append(extension.qualified_name)

        to_sort.sort()
        for extension in to_sort:
            cog = self.context.bot.get_cog(extension)
            exts.append(f"{cog.help_icon} **{cog.qualified_name}**")
            options.append(discord.SelectOption(label=cog.qualified_name, emoji=cog.help_icon))

        emb.set_author(icon_url=self.context.bot.user.avatar.url, name=_("{0} Help").format(self.context.bot.user.name))
        emb.set_thumbnail(url=self.context.bot.user.avatar.url)
        updates = self.context.bot.updates
        emb.add_field(name=_("Categories:"), value="\n".join(exts) + "\n\u200b")
        emb.add_field(name=_("\n{0} **Latest news - {1}**").format(
            self.context.bot.settings['emojis']['misc']['announce'], updates['announced'].__format__('%d %b %Y')
        ),
                             value=f"{updates['update']}")

        if ctx.guild:
            emb.set_footer(text=_("You can also navigate through the dropdown below to view commands in each category."))

        options.append(discord.SelectOption(label="Stop", emoji="<:stop:820332883470319637>"))
        view = DropdownView(ctx=self.context, placeholder="Select a category...", options=options, cls=self)

        self.message = await ctx.send(embed=emb, view=view)

    async def send_command_help(self, command):

        if command.cog_name in self.ignore_cogs:
            return await self.send_error_message(await self.command_not_found(command.name))

        if command.cog_name in self.owner_cogs and not await self.context.bot.is_owner(self.context.author):
            return await self.send_error_message(await self.command_not_found(command.name))

        if command.cog_name in self.admin_cogs and not await self.context.bot.is_admin(self.context.author):
            return await self.send_error_message(await self.command_not_found(command.name))

        if command.cog_name in self.booster_cogs and not await self.context.bot.is_booster(self.context.author):
            return await self.send_error_message(await self.command_not_found(command.name))

        if await checks.cog_disabled(self.context, command.cog_name):
            return await self.send_error_message(await self.command_not_found(command.name))

        if await checks.is_disabled(self.context, command) and not await self.context.bot.is_admin(self.context.author):
            return await self.send_error_message(await self.command_not_found(command.name))

        if command.hidden is True and not await self.context.bot.is_admin(self.context.author):
            return await self.send_error_message(await self.command_not_found(command.name))

        aliases = _("Aliases: ") + '`' + '`, `'.join(command.aliases) + "`" if command.aliases else _('No aliases were found.')
        required_user_perms = None if not hasattr(command, 'required_permissions') else _("Required permissions for you: ") + '`' + '`, `'.join(permissions_converter(self.context, command.required_permissions.keys())) + '`'
        required_bot_perms = None if not hasattr(command, 'bot_required_permissions') else _("Required permissions for me: ") + '`' + '`, `'.join(permissions_converter(self.context, command.bot_required_permissions.keys())) + '`'

        desc = _(command.callback.__doc__) if command.callback.__doc__ else _(command.help) or _('No help was provided...')
        desc += f"\n*{aliases}*"
        if required_user_perms:  # only depend on user permissions
            desc += f"\n{required_user_perms}\n{required_bot_perms if required_bot_perms else ''}"
        try:
            await command.can_run(self.context)
        except Exception:
            desc += _("\n\n*Either you or I don't have permissions to run this command in this channel*")

        for check in command.checks:
            if check.__qualname__.startswith('test_command'):
                desc += _("\n{0} This command is in an early beta and can only be used in whitelisted servers.").format(
                    self.context.bot.settings['emojis']['misc']['beta']
                )

        emb = discord.Embed(color=self.context.bot.settings['colors']['embed_color'], description=desc)
        emb.set_author(name=self.get_command_signature(command), icon_url=self.context.bot.user.avatar.url)
        emb.title = f'{self.context.prefix}{command.qualified_name} {command.signature}'
        emb.set_thumbnail(url=command.cog.big_icon)

        await self.context.send(embed=emb)

    async def send_group_help(self, group):
        if group.cog_name in self.ignore_cogs:
            return await self.send_error_message(await self.command_not_found(group.name))
        if group.cog_name in self.owner_cogs and not await self.context.bot.is_owner(self.context.author):
            return await self.send_error_message(await self.command_not_found(group.name))
        if group.cog_name in self.admin_cogs and not await self.context.bot.is_admin(self.context.author):
            return await self.send_error_message(await self.command_not_found(group.name))
        if await checks.cog_disabled(self.context, group.cog_name):
            return await self.send_error_message(await self.command_not_found(group.name))

        if group.cog_name in self.booster_cogs and not await self.context.bot.is_booster(self.context.author):
            return await self.send_error_message(self.command_not_found(group.name))  # type: ignore

        sub_cmd_list = ""
        for num, group_command in enumerate(group.commands, start=1):
            if await checks.is_disabled(self.context, group) and not await self.context.bot.is_admin(self.context.author):
                return await self.send_error_message(await self.command_not_found(group))  # type: ignore
            if group_command.root_parent.qualified_name != 'jishaku':
                brief = _(group_command.brief)
                sub_cmd_list += f"`[{num}]` `{group_command.name}` - {brief or '...'}\n"
            else:
                sub_cmd_list += '`' + group_command.name + '`, '
            if group_command.root_parent == self.context.bot.get_command('jishaku'):
                cmdsignature = f"{group} [subcommands]..."
            else:
                cmdsignature = f"{group} <subcommands>..."

        aliases = _("Aliases: ") + '`' + '`, `'.join(group_command.root_parent.aliases) + "`" if group_command.root_parent.aliases else _('No aliases were found.')
        required_user_perms = None if not hasattr(group_command, 'required_permissions') else _("Required permissions for you: ") + '`' + '`, `'.join(permissions_converter(self.context, group_command.required_permissions.keys())) + '`'
        required_bot_perms = None if not hasattr(group_command, 'bot_required_permissions') else _("Required permissions for me: ") + '`' + '`, `'.join(permissions_converter(self.context, group_command.bot_required_permissions.keys())) + '`'

        desc = _(group.callback.__doc__) if group.callback.__doc__ else _(group.help) or _("No help was provided...")
        desc += f"\n*{aliases}*"
        if required_user_perms:  # only depend on user permissions
            desc += f"\n{required_user_perms}\n{required_bot_perms if required_bot_perms else ''}"
        try:
            await group.can_run(self.context)
        except Exception:
            desc += _("\n\n*Either you or I don't have permissions to run this command in this channel*")

        for check in group.checks:
            if check.__qualname__.startswith('test_command'):
                desc += _("\n<:beta:860234962749095956> This command is in an early beta and can be used only in whitelisted servers.")

        if group_command.root_parent.qualified_name == 'jishaku':
            sub_cmd_list = sub_cmd_list[:-2]

        emb = discord.Embed(color=self.context.bot.settings['colors']['embed_color'], description=f"{desc}")
        emb.set_author(name=self.get_command_signature(group), icon_url=self.context.bot.user.avatar.url)
        emb.title = f'{self.context.prefix}{cmdsignature}'
        emb.add_field(name=_("Subcommands: ({0})").format(len(group.commands)), value=sub_cmd_list, inline=False)
        emb.set_thumbnail(url=group.cog.big_icon)

        await self.context.send(embed=emb)

    async def send_cog_help(self, cog):
        if cog.qualified_name in self.ignore_cogs:
            return await self.send_error_message(await self.command_not_found(cog.qualified_name.lower()))
        if cog.qualified_name in self.owner_cogs and not await self.context.bot.is_owner(self.context.author):
            return await self.send_error_message(await self.command_not_found(cog.qualified_name.lower()))
        if cog.qualified_name in self.admin_cogs and not await self.context.bot.is_admin(self.context.author):
            return await self.send_error_message(await self.command_not_found(cog.qualified_name.lower()))
        if cog.qualified_name in self.booster_cogs and not await self.context.bot.is_booster(self.context.author):
            return await self.send_error_message(await self.command_not_found(cog.qualified_name.lower()))
        if await checks.cog_disabled(self.context, cog.qualified_name):
            return await self.send_error_message(await self.command_not_found(cog.qualified_name.lower()))

        commands = []
        # if cog.aliases:
        #     commands.append(_("**Category aliases:** {0}\n").format('`' + '`, `'.join(cog.aliases) + '`'))
        c = 0
        for cmd in cog.get_commands():
            if cmd.hidden and not await self.context.bot.is_admin(self.context.author):
                continue
            if await checks.is_disabled(self.context, cmd) and not await self.context.bot.is_admin(self.context.author):
                continue
            brief = _('No information.') if cmd.short_doc is None else _(cmd.short_doc)
            if not cmd.hidden or not await checks.is_disabled(self.context, cmd):
                c += 1
            elif await self.context.bot.is_admin(self.context.author):
                c += 1
            commands.append(f"`{cmd.qualified_name}` - {brief}\n")

        paginator = Pages(self.context,
                          title=f"{cog.qualified_name.title()} ({c})",
                          thumbnail=cog.big_icon,
                          entries=commands,
                          embed_color=self.context.bot.settings['colors']['embed_color'],
                          show_entry_count=False,
                          home=True,
                          author=self.context.author,
                          help_command=self)

        await paginator.paginate()

    async def command_not_found(self, string):
        close = []
        for i in self.context.bot.commands:
            try:
                if not await checks.is_disabled(self.context, i.name) and difflib.SequenceMatcher(None, string, i.name).ratio() > 0.5:
                    if i.cog_name in self.owner_cogs and not await self.context.bot.is_owner(self.context.author):
                        continue
                    if i.cog_name in self.admin_cogs and not await self.context.bot.is_admin(self.context.author):
                        continue
                    if i.cog_name in self.booster_cogs and not await self.context.bot.is_booster(self.context.author):
                        continue
                    if i.hidden:
                        continue
                    close.append(i.name)
            except Exception:
                pass

        hints = [f"`[{num}]` {cmd}" for num, cmd in enumerate(close, start=1)]
        return _('No command called "{0}" was found.{1}{2}').format(string, _("\n\nDid you possibly mean:\n") if close != [] else '', '\n'.join(hints))

    async def delete_original(self):
        await self.message.delete()
