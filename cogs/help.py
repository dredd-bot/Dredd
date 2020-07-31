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
import itertools
from discord.ext import commands
from utils.paginator import Pages
from db import emotes

def setup(bot):
    bot.help_command = HelpCommand()


class HelpCommand(commands.HelpCommand):
    def __init__(self, *args, **kwargs):
        self.show_hidden = False
        super().__init__(command_attrs={
	    		'help': 'Shows help about bot and/or commands',
                'brief': 'See cog/command help',
                'usage': '[category / command]',
                'cooldown': commands.Cooldown(1, 3, commands.BucketType.user),
                'name': 'help'})
        self.verify_checks = True
        

        self.owner_cogs = ['Devishaku', 'Music', 'Owner', "Economy", "Music"]
        self.admin_cogs = ['Staff']
        self.ignore_cogs = ["Help", "Events", "Cmds", "Logs", "dredd", 'DBL', 'BG', 'StatcordPost', "AutomodEvents", "Eventss"]
    
    def get_command_signature(self, command):
        if command.cog is None:
            return f"(None) / {command.qualified_name}"
        else:
            return f"({command.cog.qualified_name}) / {command.qualified_name}"

    async def command_callback(self, ctx, *, command=None):
        """|coro|
        The actual implementation of the help command.
        It is not recommended to override this method and instead change
        the behaviour through the methods that actually get dispatched.
        - :meth:`send_bot_help`
        - :meth:`send_cog_help`
        - :meth:`send_group_help`
        - :meth:`send_command_help`
        - :meth:`get_destination`
        - :meth:`command_not_found`
        - :meth:`subcommand_not_found`
        - :meth:`send_error_message`
        - :meth:`on_help_command_error`
        - :meth:`prepare_help_command`
        """
        
        await self.prepare_help_command(ctx, command)
        bot = ctx.bot

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
        
    async def send_bot_help(self, mapping):
        """ See bot help """

        Moksej = self.context.bot.get_user(345457928972533773)        

        support = self.context.bot.support
        invite = self.context.bot.invite
        if self.context.guild is not None:
            p = await self.context.bot.db.fetchval("SELECT prefix FROM guilds WHERE guild_id = $1", self.context.guild.id)
            prefix = f"**Bot prefix in this server:** `{p}`"
        elif self.context.guild is None:
            prefix = "**Bot prefix in DM's:** `!`"
        s = "Support"
        i = "Bot invite"
        dbl = "[top.gg](https://top.gg/bot/667117267405766696/vote)"
        boats = "[discord.boats](https://discord.boats/bot/667117267405766696/vote)"
        privacy = "[Privacy Policy](https://github.com/TheMoksej/Dredd/blob/master/PrivacyPolicy.md)"

        def check(m):
            return m.author == self.context.author
        
        emb = discord.Embed(color=self.context.bot.embed_color)
        emb.description = f"\n**This bot was made by:** {Moksej}\n{prefix}\n"


        cogs = ""
        for extension in self.context.bot.cogs.values():
            if extension.qualified_name in self.ignore_cogs:
                continue
            if extension.qualified_name == "Devishaku":
                continue
            if extension.qualified_name in self.owner_cogs and not await self.context.bot.is_owner(self.context.author):
                continue
            if extension.qualified_name in self.admin_cogs and not await self.context.bot.is_admin(self.context.author):
                continue
            #c = f"`" + f"`, `".join([c.qualified_name for c in set(extension.get_commands())]) + '`'
            # entries = await self.filter_commands(set(extension.get_commands()), sort=True)
            # return await self.context.send(entries)
            # emb.add_field(name=f"{extension.help_icon} **{extension.qualified_name}**", value=c, inline=False)
            cogs += f"{extension.help_icon} **{extension.qualified_name}**\n"
        
        updates = await self.context.bot.db.fetchval('SELECT * FROM updates')
        emb.add_field(name="**Categories:**", value=f"{cogs}")
        emb.add_field(name="\u200b", value="\u200b")
        emb.add_field(name='📰 **Latest news**', value=f"{updates}", inline=True)
        emb.add_field(name='**Useful links**', value=f"{emotes.social_discord} [{s}]({support}) | {emotes.pfp_normal} [{i}]({invite}) | {emotes.dbl} {dbl} | {emotes.boats} {boats} | {emotes.discord_privacy} {privacy}", inline=False)
        emb.set_footer(text=f"- You can type {self.clean_prefix}help <command> to see that command help and {self.clean_prefix}help <category> to see that category commands")

        await self.context.send(embed=emb)

    
    async def send_command_help(self, command):

        if command.cog_name in self.ignore_cogs:
            return await self.send_error_message(self.command_not_found(command.name))
        
        if command.cog_name in self.owner_cogs and not await self.context.bot.is_owner(self.context.author):
            return await self.send_error_message(self.command_not_found(command.name))
        
        if command.cog_name in self.admin_cogs and not await self.context.bot.is_admin(self.context.author):
            return await self.send_error_message(self.command_not_found(command.name))

        if self.context.guild and await self.context.bot.db.fetchval("SELECT * FROM guilddisabled WHERE guild_id = $1 AND command = $2", self.context.guild.id, str(command)) and self.context.author.guild_permissions.administrator == False and not await self.context.bot.is_owner(self.context.author):
            return await self.send_error_message(f"{emotes.warning} Command is disabled in this server, which is why I can't show you the help of it.")
        
        if await self.context.bot.db.fetchval("SELECT * FROM cmds WHERE command = $1", str(command)) and not await self.context.bot.is_admin(self.context.author):
            return await self.send_error_message(f"{emotes.warning} This command is temporarily disabled for maintenance.")
        
        if command.hidden == True:
            return await self.send_error_message(self.command_not_found(command.name))

        aliases = "`" + '`, `'.join(command.aliases) + "`"
        if aliases == "``":
            aliases = "No aliases were found"
        
        if command.help:
            desc = f"{command.help}"
        else:
            desc = "No help provided..."


        emb = discord.Embed(color=self.context.bot.embed_color, description=desc)
        emb.title = self.get_command_signature(command)
        emb.add_field(name="Usage:\n", value=f"{self.clean_prefix}{command.qualified_name} {command.signature}")
        emb.add_field(name="Aliases:\n", value=aliases)
        emb.set_thumbnail(url='https://cdn.discordapp.com/attachments/679705242124025897/680397954699231259/dredd_em.png')
           
        await self.context.send(embed=emb)
  
    async def send_group_help(self, group):          

        if group.cog_name in self.ignore_cogs:
            return await self.send_error_message(self.command_not_found(group.name))
        if group.cog_name in self.owner_cogs and not await self.context.bot.is_owner(self.context.author):
            return await self.send_error_message(self.command_not_found(group.name))
        if group.cog_name in self.admin_cogs and not await self.context.bot.is_admin(self.context.author):
            return await self.send_error_message(self.command_not_found(group.name))

        sub_cmd_list = ""
        for group_command in group.commands:
            if self.context.guild and await self.context.bot.db.fetchval("SELECT * FROM guilddisabled WHERE guild_id = $1 AND command = $2", self.context.guild.id, str(group_command.root_parent)) and self.context.author.guild_permissions.administrator == False and not await self.context.bot.is_owner(self.context.author):
                return await self.send_error_message(f"{emotes.warning} Command is disabled in this server, which is why I can't show you the help of it.")
            sub_cmd_list += '**' + group_command.name + f'**, '
            if group_command.root_parent == "jishaku":
                cmdsignature = f"{group_command.root_parent} [subcommands]..."
            else:
                cmdsignature = f"{group_command.root_parent} <subcommands>..."
        aliases = "`" + '`, `'.join(group_command.root_parent.aliases) + "`"     
        if aliases == "``":
            aliases = "No aliases were found"

        if group_command.root_parent.help:
            desc = f"{group_command.root_parent.help}"
        else:
            desc = "No help provided..."

        
        emb = discord.Embed(color=self.context.bot.embed_color, description=f"{desc}")
        emb.title = self.get_command_signature(group_command.root_parent)
        emb.add_field(name="Usage:\n", value=f"{self.clean_prefix}{cmdsignature}")
        emb.add_field(name="Aliases:\n", value=aliases)
        emb.add_field(name=f"Subcommands: ({len(group.commands)})", value=sub_cmd_list[:-2], inline=False)
        emb.set_thumbnail(url='https://cdn.discordapp.com/attachments/679705242124025897/680397954699231259/dredd_em.png')
        
       
        await self.context.send(embed=emb)

    async def send_cog_help(self, cog):
        if cog.qualified_name in self.ignore_cogs:
            return
        if cog.qualified_name in self.owner_cogs and not await self.context.bot.is_owner(self.context.author):
            return
        if cog.qualified_name in self.admin_cogs and not await self.context.bot.is_admin(self.context.author):
            return

        commands = []
        c = 0
        for cmd in cog.get_commands():
            if cmd.hidden:
                continue
            if await self.context.bot.db.fetchval("SELECT * FROM guilddisabled WHERE guild_id = $1 AND command = $2", self.context.guild.id, str(cmd)):
                continue
            if cmd.short_doc is None:
                brief = 'No info'
            else:
                brief = cmd.short_doc
            
            if not cmd.hidden or not await self.context.bot.db.fetchval("SELECT * FROM guilddisabled WHERE guild_id = $1 AND command = $2", self.context.guild.id, str(cmd)):
                c += 1

            commands.append(f"`{cmd.qualified_name}` - {brief}\n")

        paginator = Pages(self.context,
                          title=f"{cog.qualified_name.title()} ({c})",
                          thumbnail=cog.big_icon,
                          entries=commands,
                          per_page = 12,
                          embed_color=self.context.bot.embed_color,
                          show_entry_count=False,
                          author=self.context.author)

        await paginator.paginate()

    
    

    def command_not_found(self, string):
        return 'No command called "{}" found.'.format(string)
