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
import traceback

from discord.ext import commands
from datetime import datetime
from db import emotes


class CommandError(commands.Cog, name="Cmds", command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        self.bot = bot
        self._last_result = None

    @commands.Cog.listener()
    async def on_command(self, ctx):
        if ctx.guild is not None:
            try:
                print(f"{ctx.guild.name} | {ctx.author} > {ctx.message.clean_content}")
            except:
                print(f"{ctx.guild.id} | {ctx.author.id} > {ctx.message.clean_content}")
        else:
            print(f"DM channel | {ctx.author} > {ctx.message.content}")
    
    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        if ctx.command.parent:
            cmd = f'{ctx.command.parent} {ctx.command.name}'
        else:
            cmd = ctx.command.name

        if not cmd in self.bot.cmdUsage:
            self.bot.cmdUsage[cmd] = 1
        else:
            self.bot.cmdUsage[cmd] += 1

        if not str(ctx.author.id) in self.bot.cmdUsers:
            self.bot.cmdUsers[str(ctx.author.id)] = 1
        else:
            self.bot.cmdUsers[str(ctx.author.id)] += 1

        if ctx.guild and str(ctx.guild.id) not in self.bot.guildUsage:
            self.bot.guildUsage[str(ctx.guild.id)] = 1
        elif ctx.guild and str(ctx.guild.id) in self.bot.guildUsage:
            self.bot.guildUsage[str(ctx.guild.id)] += 1


    @commands.Cog.listener()
    async def on_command_error(self, ctx, exc):

        if isinstance(exc, commands.NSFWChannelRequired):
            file = discord.File("img/nsfwerror.png", filename="nsfwerror.png")
            embed = discord.Embed(color=self.bot.logging_color, description=f"{emotes.other_nsfw} This command is marked NSFW. Please make this channel NSFW in channel settings")
            embed.set_image(url='attachment://nsfwerror.png')
            return await ctx.send(file=file, embed=embed, delete_after=20)
        if isinstance(exc, commands.CommandNotFound):
            return
        if isinstance(exc, commands.NotOwner):
            return await ctx.send(f"{emotes.bot_owner} | This command is owner-locked", delete_after=20)
        if isinstance(exc, commands.CommandInvokeError):
            ctx.command.reset_cooldown(ctx)
            exc = exc.original
        if isinstance(exc, commands.BadArgument):
            cleaned = discord.utils.escape_mentions(str(exc))
            clear = await commands.clean_content().convert(ctx, str(exc))
            return await ctx.send(f"{emotes.red_mark} | {cleaned}", delete_after=20)
        if isinstance(exc, commands.MissingPermissions):
            perms = "`" + '`, `'.join(exc.missing_perms) + "`" 
            embed = discord.Embed(color=self.bot.logging_color, description=f"{emotes.red_mark} You're missing {perms} permissions")
            return await ctx.send(f"{emotes.red_mark} | You're missing {perms} permissions", delete_after=20)
        if isinstance(exc, commands.BotMissingPermissions):
            perms = "`" + '`, `'.join(exc.missing_perms) + "`" 
            embed = discord.Embed(color=self.bot.logging_color, description=f"{emotes.red_mark} I'm missing {perms} permissions")
            return await ctx.send(f"{emotes.red_mark} | I'm missing {perms} permissions", delete_after=20)
        if isinstance(exc, commands.CheckFailure):
            return
        if isinstance(exc, commands.TooManyArguments):
            if isinstance(ctx.command, commands.Group):
                return
        if isinstance(exc, commands.CommandOnCooldown):
            if await self.bot.is_owner(ctx.author):
                ctx.command.reset_cooldown(ctx)
                return await ctx.reinvoke()                
            log = self.bot.get_channel(691654772360740924)
            embed = discord.Embed(colour=self.bot.logembed_color)
            embed.title = "**User is on cooldown**"
            embed.description = f"""**User:** {ctx.author} ({ctx.author.id})
Cooldown resets in **{exc.retry_after:.0f}** seconds."""
            await log.send(embed=embed)
            return await ctx.send(f"{emotes.timer} | You're on cooldown, try again in **{exc.retry_after:.0f}** seconds", delete_after=20)

        ctx.command.reset_cooldown(ctx)
        if isinstance(exc, commands.MissingRequiredArgument):
            embed = discord.Embed(color=self.bot.logging_color, description=f"{emotes.red_mark} You're missing an argument - **{(exc.param.name)}**")
            return await ctx.send(f"{emotes.red_mark} | You're missing an argument - **{(exc.param.name)}**", delete_after=20)
        
        support = await self.bot.db.fetchval("SELECT * FROM support")

        if ctx.guild is None:
            guild = "DM"
            guild_id = 'DM channel'
            channel = 'DM channel'
            channel_id = 'DM channel'
        else:
            guild = ctx.guild
            guild_id = ctx.guild.id
            channel = ctx.channel
            channel_id = ctx.channel.id

        tb = traceback.format_exception(type(exc), exc, exc.__traceback__) 
        tbe = "".join(tb) + ""
        log = self.bot.get_channel(675742172015755274)
        embed = discord.Embed(
            title=f"{emotes.error} Error occured while executing command!", color=self.bot.logembed_color, timestamp=datetime.utcnow())
        embed.description = f'''```py
{tbe}
```'''
        embed.add_field(name='Error information:', value=f'''`{ctx.message.clean_content}`
**Server:** {guild} **ID:** {guild_id}
**Channel:** {channel} **ID:** {channel_id};
**Author:** {ctx.author} **ID:** {ctx.author.id}''')
        try:
            await log.send(embed=embed)
        except Exception:
            print(tb)
            e = discord.Ember(color=self.bot.logembed_color, timestamp=datetime.utcnow())
            e.title = f"{emotes.error} Error too long!"
            e.description = f"```py\n{exc}```"
            e.add_field(name='Error information:', value=f'''`{ctx.message.clean_content}`
**Server:** {guild} **ID:** {guild_id}
**Channel:** {channel} **ID:** {channel_id};
**Author:** {ctx.author} **ID:** {ctx.author.id}''')
            await log.send(embed=e)

        e = discord.Embed(color=self.bot.error_color, timestamp=datetime.utcnow(), description=f'{emotes.error} An error occured while executing command `{ctx.command}`\n[Join support server]({support})')
        e.add_field(name="Error info:", value=f"""```py
{exc}```""")
        e.set_footer(text=f"Developer(s) were notified about this issue")
        await ctx.send(embed=e, delete_after=30)
        return


def setup(bot):
    bot.add_cog(CommandError(bot))
