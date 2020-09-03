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
import json
from discord.ext import commands
from utils import default
from db import emotes
from utils.checks import test_command
from utils.default import color_picker
from utils.caches import CacheManager as cm

class Managment(commands.Cog, name="Management"):

    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:settingss:695707235833085982>"
        self.big_icon = "https://cdn.discordapp.com/emojis/695707235833085982.png?v=1"
        self.color = color_picker('colors')

    
    async def bot_check(self, ctx):
        
        if await self.bot.is_admin(ctx.author):
            return True
        
        if not ctx.guild:
            return True

        if ctx.guild and ctx.author.guild_permissions.administrator:
            return True

        if ctx.command.parent:
            if await self.bot.db.fetchval("select * from guilddisabled where command = $1 AND guild_id = $2", str(ctx.command.parent), ctx.guild.id):
                await ctx.send(f"{emotes.warning} | `{ctx.command.parent}` and it's corresponding subcommands are disabled in this server")
                return False
            elif await self.bot.db.fetchval("select * from guilddisabled where command = $1 AND guild_id = $2", str(f"{ctx.command.parent} {ctx.command.name}"), ctx.guild.id):
                await ctx.send(f"{emotes.warning} | `{ctx.command.parent} {ctx.command.name}` is disabled in this server.")
                return False
        else:
            if await self.bot.db.fetchval("select * from guilddisabled where command = $1 AND guild_id = $2", str(ctx.command.name), ctx.guild.id):
                await ctx.send(f"{emotes.warning} | `{ctx.command.name}` is disabled in this server.")
                return False
        return True

    def cog_check(self, ctx):
        if not ctx.guild:
            return False
        return True


    @commands.command(brief="Change the bot's prefix")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def prefix(self, ctx, prefix: str = None):
        """ Change bot's prefix in the server """

        prefixs = await self.bot.db.fetchval("SELECT prefix FROM guilds WHERE guild_id = $1", ctx.guild.id)
        if prefix is None:
            return await ctx.send(f"Your server prefix is `{prefixs}`")

        elif prefix and len(prefix) < 6:
            await self.bot.db.execute("UPDATE guilds SET prefix = $1 WHERE guild_id = $2", prefix, ctx.guild.id)
            self.bot.prefixes[ctx.guild.id] = prefix
            await ctx.send(f"Changed server prefix to `{prefix}`!")
        else:
            await ctx.send(f"{emotes.warning} Prefix is too long!")

    @commands.command(brief="Check the server settings", aliases=['guildsettings', 'settings'])
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def serversettings(self, ctx):
        """ Show all guild settings whether they're enabled or disabled """

        db_check1 = await self.bot.db.fetchval("SELECT guild_id FROM msgdelete WHERE guild_id = $1", ctx.guild.id)
        db_check2 = await self.bot.db.fetchval("SELECT guild_id FROM moderation WHERE guild_id = $1", ctx.guild.id)
        db_check3 = await self.bot.db.fetchval("SELECT guild_id FROM msgedit WHERE guild_id = $1", ctx.guild.id)
        db_check4 = await self.bot.db.fetchval("SELECT guild_id FROM joinlog WHERE guild_id = $1", ctx.guild.id)
        db_check6 = await self.bot.db.fetchval("SELECT guild_id FROM memberupdate WHERE guild_id = $1", ctx.guild.id)
        db_check7 = await self.bot.db.fetchval("SELECT guild_id FROM joinmsg WHERE guild_id = $1", ctx.guild.id)
        db_check8 = await self.bot.db.fetchval("SELECT guild_id FROM joinrole WHERE guild_id = $1", ctx.guild.id)
        db_check9 = await self.bot.db.fetchval("SELECT guild_id FROM leavemsg WHERE guild_id = $1", ctx.guild.id)
        db_check10 = await self.bot.db.fetchval("SELECT guild_id FROM automodaction WHERE guild_id = $1", ctx.guild.id)
        joinmsg = await self.bot.db.fetchval("SELECT msg FROM joinmsg WHERE guild_id = $1", ctx.guild.id)
        leavemsg = await self.bot.db.fetchval("SELECT msg FROM leavemsg WHERE guild_id = $1", ctx.guild.id)
        embed_join = await self.bot.db.fetchval("SELECT embed FROM joinmsg WHERE guild_id = $1", ctx.guild.id)
        embed_leave = await self.bot.db.fetchval("SELECT embed FROM leavemsg WHERE guild_id = $1", ctx.guild.id)
        raidmode = await self.bot.db.fetchval("SELECT raidmode FROM raidmode WHERE guild_id = $1", ctx.guild.id)
        raidmodedm = await self.bot.db.fetchval("SELECT dm FROM raidmode WHERE guild_id = $1", ctx.guild.id)
        dehoist = await self.bot.db.fetchval("SELECT * FROM antidehoist WHERE guild_id = $1", ctx.guild.id)

        mention = '{{member.mention}}'
        members = '{{server.members}}'
        if db_check7:
            msg = "{0} {1} joined the server! There are {2} members in the server now.".format(emotes.joined, mention, members)
        elif not db_check7:
            msg = 'Welcoming messages are disabled'
        
        if db_check9:
            msg1 = "{0} {1} left the server... There are {2} members left in the server.".format(emotes.left, mention, members)
        elif not db_check9:
            msg1 = 'Leaving messages are disabled'
        if not embed_join:
            joinmsg = joinmsg or msg
        elif embed_join:
            joinmsg = f"Welcoming messages are embedded\nYou can view them by invoking `{ctx.prefix}embedded welcoming`"
        
        if not embed_leave:
            leavemsg = leavemsg or msg1
        elif embed_leave:
            leavemsg = f"Leaving messages are embedded\nYou can view them by invoking `{ctx.prefix}embedded leaving`"

        logs  = f"{f'{emotes.setting_no}' if db_check3 is None else f'{emotes.setting_yes}'} Edited messages\n"
        logs += f"{f'{emotes.setting_no}' if db_check1 is None else f'{emotes.setting_yes}'} Deleted messages\n"
        logs += f"{f'{emotes.setting_no}' if db_check2 is None else f'{emotes.setting_yes}'} Moderation\n"
        logs += f"{f'{emotes.setting_no}' if db_check4 is None else f'{emotes.setting_yes}'} Member Joins\n"
        logs += f"{f'{emotes.setting_no}' if db_check6 is None else f'{emotes.setting_yes}'} Member Updates\n"
        logs += f"{f'{emotes.setting_no}' if db_check10 is None else f'{emotes.setting_yes}'} Automod actions\n"
        logs += f"{f'{emotes.setting_no}' if dehoist is None else f'{emotes.setting_yes}'} Dehoisting\n"

        settings = f"{f'{emotes.setting_no}' if db_check8 is None else f'{emotes.setting_yes}'} Role On Join\n"
        settings += f"{f'{emotes.setting_no}' if db_check7 is None else f'{emotes.setting_yes}'} Welcoming Messages\n"
        settings += f"{f'{emotes.setting_no}' if db_check9 is None else f'{emotes.setting_yes}'} Leaving Messages\n"
        settings += f"{f'{emotes.setting_no}' if raidmode is False else f'{emotes.setting_yes}'} Raid mode\n"
        if raidmode is True:
            settings += f"{f'{emotes.setting_no}' if raidmodedm is False else f'{emotes.setting_yes}'} Raid mode DM"

        welcoming = f"**Join message:**\n{joinmsg}\n"
        welcoming += f"**Leave message:**\n{leavemsg}"


        embed = discord.Embed(color=self.color['embed_color'], description=f"{emotes.log_settings} **{ctx.guild}** server settings")
        embed.add_field(name="Logs:", value=logs, inline=False)
        embed.add_field(name="Settings:", value=settings, inline=False)
        embed.add_field(name="Welcoming & Leaving:", value=welcoming, inline=False)

        await ctx.send(embed=embed)
    
    @commands.command(brief="Enable or disable logging")
    @commands.has_permissions(manage_guild=True)
    async def togglelog(self, ctx, option = None, *, channel: discord.TextChannel = None):
        """ Toggle log for the given option.  
        Leaving channel empty will disable the log. 
        It is highly recommended for bot to have view audit logs permissions as well"""

        options = ["msgdelete", "msgedit", "moderation", "joinlog", "joinmsg", "leavemsg", "memberupdate", "antidehoist"]
        optionsmsg = f'`joinlog`, `memberupdate`, `msgedit`, `msgdelete`, `moderation`, `joinmsg`, `leavemsg`, `antidehoist`'

        if option is None or option.lower() not in options:
            e = discord.Embed(color=self.color['embed_color'],
                              title=f"{emotes.warning} Invalid option was given. Here are all the valid options:",
                              description=optionsmsg)
            #e.set_footer(text=f"© {self.bot.user}")
            return await ctx.send(embed=e)


        db_check = await self.bot.db.fetchval(f"SELECT guild_id FROM {option} WHERE guild_id = $1", ctx.guild.id)           

            
        if channel is None:
            await self.bot.db.execute(f"DELETE FROM {option} WHERE guild_id = $1", ctx.guild.id)
            if option.lower() == 'msgedit':
                if db_check is None:
                    return await ctx.send(f"{emotes.red_mark} Message edit logs aren't enabled in this server", delete_after=20)
                self.bot.msgedit.pop(ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Message edit logs have been disabled in this server", delete_after=20)
            elif option.lower() == 'msgdelete':
                if db_check is None:
                    return await ctx.send(f"{emotes.red_mark} Message delete logs aren't enabled in this server", delete_after=20)
                self.bot.msgdelete.pop(ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Message delete logs have been disabled in this server", delete_after=20)              
            elif option.lower() == 'moderation':
                if db_check is None:
                    return await ctx.send(f"{emotes.red_mark} Moderation logs aren't enabled in this server", delete_after=20)
                self.bot.moderation.pop(ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Moderation have been disabled in this server", delete_after=20)
            elif option.lower() == 'joinlog':
                if db_check is None:
                    return await ctx.send(f"{emotes.red_mark} Join logs aren't enabled in this server", delete_after=20)
                self.bot.joinlog.pop(ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Join logs have been disabled in this server", delete_after=20)
            elif option.lower() == 'joinmsg':
                if db_check is None:
                    return await ctx.send(f"{emotes.red_mark} Join messages logs aren't enabled in this server", delete_after=20)
                self.bot.joinmsg.pop(ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Join messages logs have been disabled in this server", delete_after=20)
            elif option.lower() == 'leavemsg':
                if db_check is None:
                    return await ctx.send(f"{emotes.red_mark} Leave messages logs aren't enabled in this server", delete_after=20)
                self.bot.leavemsg.pop(ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Leave messages logs have been disabled in this server", delete_after=20)
            elif option.lower() == 'memberupdate':
                if db_check is None:
                    return await ctx.send(f"{emotes.red_mark} Member update logs aren't enabled in this server", delete_after=20)
                self.bot.memberupdate.pop(ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Member update logs have been disabled in this server", delete_after=20)
            elif option.lower() == 'antidehoist':
                if db_check is None:
                    return await ctx.send(f"{emotes.red_mark} Dehoist logs aren't enabled in this server", delete_after=20)
                self.bot.antidehoist.pop(ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Dehoist logs have been disabled in this server", delete_after=20)

        elif channel is not None:
            if channel.permissions_for(ctx.guild.me).send_messages == False:
                return await ctx.send(f"{emotes.warning} I can't let you do that! I don't have permissions to talk in {channel.mention}")
            elif channel.permissions_for(ctx.guild.me).send_messages:
                if db_check is None:
                    await self.bot.db.execute(f"INSERT INTO {option}(guild_id, channel_id) VALUES ($1, $2)", ctx.guild.id, channel.id)
                if db_check is not None:
                    await self.bot.db.execute(f"UPDATE {option} SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
                if option.lower() == 'msgedit':
                    if db_check is not None:
                        self.bot.msgedit[ctx.guild.id] = channel.id
                        return await ctx.send(f"{emotes.white_mark} Message edit logs will be sent to {channel.mention} from now on!", delete_after=20)
                    self.bot.msgedit[ctx.guild.id] = channel.id
                    await ctx.send(f"{emotes.white_mark} Message edit logs have been enabled in this server and will be sent to {channel.mention}!", delete_after=20)
                elif option.lower() == 'msgdelete':
                    if db_check is not None:
                        self.bot.msgdelete[ctx.guild.id] = channel.id
                        return await ctx.send(f"{emotes.white_mark} Message delete logs will be sent to {channel.mention} from now on!", delete_after=20)
                    self.bot.msgdelete[ctx.guild.id] = channel.id
                    await ctx.send(f"{emotes.white_mark} Message delete logs have been enabled in this server and will be sent to {channel.mention}!", delete_after=20)
                elif option.lower() == 'moderation':
                    if db_check is not None:
                        self.bot.moderation[ctx.guild.id] = channel.id
                        return await ctx.send(f"{emotes.white_mark} Moderation logs will be sent to {channel.mention} from now on!", delete_after=20)
                    self.bot.moderation[ctx.guild.id] = channel.id
                    await ctx.send(f"{emotes.white_mark} Moderation logs have been enabled in this server and will be sent to {channel.mention}!", delete_after=20)
                elif option.lower() == 'joinlog':
                    if db_check is not None:
                        self.bot.joinlog[ctx.guild.id] = channel.id
                        return await ctx.send(f"{emotes.white_mark} Join logs will be sent to {channel.mention} from now on!", delete_after=20)
                    self.bot.joinlog[ctx.guild.id] = channel.id
                    await ctx.send(f"{emotes.white_mark} Join logs have been enabled in this server and will be sent to {channel.mention}!", delete_after=20)
                elif option.lower() == 'joinmsg':
                    if db_check is not None:
                        self.bot.joinmsg[ctx.guild.id]['channel'] = channel.id
                        return await ctx.send(f"{emotes.white_mark} Welcoming messages will be sent to {channel.mention} from now on!", delete_after=20)
                    self.bot.joinmsg[ctx.guild.id] = {'channel': channel.id, 'bot_joins': False, 'embed': False, 'message': None}
                    await ctx.send(f"{emotes.white_mark} Welcoming messages have been enabled in this server and will be sent to {channel.mention}! You can change the welcoming message by typing `{ctx.prefix}togglemsg welcoming [message]`", delete_after=20)
                elif option.lower() == 'leavemsg':
                    if db_check is not None:
                        self.bot.leavemsg[ctx.guild.id]['channel'] = channel.id
                        return await ctx.send(f"{emotes.white_mark} Leaving messages will be sent to {channel.mention} from now on!", delete_after=20)
                    self.bot.leavemsg[ctx.guild.id] = {'channel': channel.id, 'bot_joins': False, 'embed': False, 'message': None}
                    await ctx.send(f"{emotes.white_mark} Leaving messages have been enabled in this server and will be sent to {channel.mention}! You can change the leaving message by typing `{ctx.prefix}togglemsg leaving [message]`", delete_after=20)
                elif option.lower() == 'memberupdate':
                    if db_check is not None:
                        self.bot.memberupdate[ctx.guild.id] = channel.id
                        return await ctx.send(f"{emotes.white_mark} Member update logs will be sent to {channel.mention} from now on!", delete_after=20)
                    self.bot.memberupdate[ctx.guild.id] = channel.id
                    await ctx.send(f"{emotes.white_mark} Member update logs have been enabled in this server and will be sent to {channel.mention}!", delete_after=20)
                elif option.lower() == 'antidehoist':
                    if db_check is not None:
                        self.bot.antidehoist[ctx.guild.id] = {'channel': channel.id, 'nickname': None}
                        return await ctx.send(f"{emotes.white_mark} Dehoist logs will be sent to {channel.mention} from now on!", delete_after=20)
                    self.bot.antidehoist[ctx.guild.id] = {'channel': channel.id, 'nickname': None}
                    await ctx.send(f"{emotes.white_mark} Dehoist logs have been enabled in this server and will be sent to {channel.mention}!", delete_after=20)

    @commands.group(brief="Manage welcoming and leaving messages")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def togglemsg(self, ctx):
        """ Setup welcoming and leaving messages in your server. 
        `{{member.mention}}` - Mentions a member that joined/left
        `{{member.name}}` - Displays name of member that joined/left
        `{{server.name}}` - Displays server name
        `{{server.members}}` - Displays how many members server has """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @togglemsg.command()
    async def welcoming(self, ctx, *, message: str = None):
        """ Set welcoming message """

        db_check = await self.bot.db.fetchval("SELECT * FROM joinmsg WHERE guild_id = $1", ctx.guild.id)
        embed_check = await self.bot.db.fetchval("SELECT embed FROM joinmsg WHERE guild_id = $1", ctx.guild.id)

        if db_check:
            if message is None:
                await self.bot.db.execute("UPDATE joinmsg SET msg = $1 WHERE guild_id = $2", None, ctx.guild.id)
                self.bot.joinmsg[ctx.guild.id]['message'] = message
                await ctx.send(f"{emotes.white_mark} Changed welcoming message to default one.")
            elif message and not len(message) > 250 and not embed_check:
                await self.bot.db.execute("UPDATE joinmsg SET msg = $1 WHERE guild_id = $2", message, ctx.guild.id)
                self.bot.joinmsg[ctx.guild.id]['message'] = message
                await ctx.send(f"{emotes.white_mark} Changed welcoming message to `{message}`")
            elif message and embed_check == True:
                try:
                    jsonify = json.loads(message)
                except:
                    return await ctx.send(f"{emotes.warning} To setup welcoming message you need to use embeds format as you have embedded welcoming messages enabled. You can visit this website to make yourself an embed: <https://embedbuilder.nadekobot.me/>")
                if "title" in jsonify:
                    if len(jsonify['title']) > 256:
                        return await ctx.send(f"{emotes.warning} Titles can only be 256 characters long and yours is {len(jsonify['title'])} characters")
                await self.bot.db.execute("UPDATE joinmsg SET msg = $1 WHERE guild_id = $2", message, ctx.guild.id)
                self.bot.joinmsg[ctx.guild.id]['message'] = message
                await ctx.send(content='Your embed will look like this: (if it\'s not displayed - your code is invalid, you can set it up here: <https://embedbuilder.nadekobot.me/>)', embed=discord.Embed.from_dict(jsonify))
            else:
                await ctx.send(f"{emotes.red_mark} Was unable to change welcoming message because it is {len(message)}/250 characters long.")
        elif db_check is None:
            return await ctx.send(f"{emotes.red_mark} Please enable welcoming messages first by typing `{ctx.prefix}togglelog joinmsg [channel mention]`")

    @togglemsg.command()
    async def leaving(self, ctx, *, message: str = None):
        """ Set leaving message """

        db_check = await self.bot.db.fetchval("SELECT * FROM leavemsg WHERE guild_id = $1", ctx.guild.id)
        embed_check = await self.bot.db.fetchval("SELECT embed FROM leavemsg WHERE guild_id = $1", ctx.guild.id)

        if db_check:
            if message is None:
                await self.bot.db.execute("UPDATE leavemsg SET msg = $1 WHERE guild_id = $2", None, ctx.guild.id)
                self.bot.leavemsg[ctx.guild.id]['message'] = message
                await ctx.send(f"{emotes.white_mark} Changed leaving message to default one.")
            elif message and not len(message) > 250 and not embed_check:
                await self.bot.db.execute("UPDATE leavemsg SET msg = $1 WHERE guild_id = $2", message, ctx.guild.id)
                self.bot.leavemsg[ctx.guild.id]['message'] = message
                await ctx.send(f"{emotes.white_mark} Changed leaving message to `{message}`")
            elif message and embed_check == True:
                try:
                    jsonify = json.loads(message)
                except:
                    return await ctx.send(f"{emotes.warning} To setup leaving message you need to use embeds format as you have embedded welcoming messages enabled. You can visit this website to make yourself an embed: <https://embedbuilder.nadekobot.me/>")
                if "title" in jsonify:
                    if len(jsonify['title']) > 256:
                        return await ctx.send(f"{emotes.warning} Titles can only be 256 characters long and yours is {len(jsonify['title'])} characters")
                await self.bot.db.execute("UPDATE leavemsg SET msg = $1 WHERE guild_id = $2", message, ctx.guild.id)
                self.bot.leavemsg[ctx.guild.id]['message'] = message
                await ctx.send(content='Your embed will look like this: (if it\'s not displayed - your code is invalid, you can set it up here: <https://embedbuilder.nadekobot.me/>)', embed=discord.Embed.from_dict(jsonify))
            else:
                await ctx.send(f"{emotes.red_mark} Was unable to change leaving message because it is {len(message)}/250 characters long.")
        elif db_check is None:
            return await ctx.send(f"{emotes.red_mark} Please enable leaving messages first by typing `{ctx.prefix}togglelog leavemsg [channel mention]`")
    
    @togglemsg.command(name='joinbots')
    async def togglemsg_joinbots(self, ctx):
        """ Toggle bot joins """
        check = cm.get_cache(self.bot, ctx.guild.id, 'joinmsg')
        
        if check is None:
            await ctx.send(f"{emotes.red_mark} You aren't logging member joins, please enable that by typing `{ctx.prefix}togglelog joinmsg [channel mention]`")
        elif check['bot_joins'] == False:
            await self.bot.db.execute("UPDATE joinmsg SET bot_join = $1 WHERE guild_id = $2", True, ctx.guild.id)
            self.bot.joinmsg[ctx.guild.id]['bot_joins'] = True
            await ctx.send(f"{emotes.white_mark} Bot joins will now be logged!")
        elif check['bot_joins'] == True:
            await self.bot.db.execute("UPDATE joinmsg SET bot_join = $1 WHERE guild_id = $2", False, ctx.guild.id)
            self.bot.joinmsg[ctx.guild.id]['bot_joins'] = False
            await ctx.send(f"{emotes.white_mark} Bot joins won't be logged anymore!")
            
    
    @togglemsg.command(name='leavebots')
    async def togglemsg_leavebots(self, ctx):
        """ Toggle bot leaves """
        check = cm.get_cache(self.bot, ctx.guild.id, 'leavemsg')

        if check is None:
            await ctx.send(f"{emotes.red_mark} You aren't logging member leaves, please enable that by typing `{ctx.prefix}togglelog leavemsg [channel mention]`")
        elif check['bot_joins'] == False:
            await self.bot.db.execute("UPDATE leavemsg SET bot_join = $1 WHERE guild_id = $2", True, ctx.guild.id)
            self.bot.leavemsg[ctx.guild.id]['bot_joins'] = True
            await ctx.send(f"{emotes.white_mark} Bot leaves will now be logged!")
        elif check['bot_joins'] == True:
            await self.bot.db.execute("UPDATE leavemsg SET bot_join = $1 WHERE guild_id = $2", False, ctx.guild.id)
            self.bot.leavemsg[ctx.guild.id]['bot_joins'] = False
            await ctx.send(f"{emotes.white_mark} Bot leaves won't be logged anymore!")
            

    @togglemsg.command(name='joinembed')
    async def togglemsg_joinembed(self, ctx):
        """ Enable or disable embedded welcoming messages """
        check = await self.bot.db.fetchval("SELECT embed FROM joinmsg WHERE guild_id = $1", ctx.guild.id)
        checks = await self.bot.db.fetchval('SELECT * FROM leavemsg WHERE guild_id = $1', ctx.guild.id)
        if not checks:
            return await ctx.send(f"{emotes.warning} Please enable welcoming messages first!")
        if not check:
            await self.bot.db.execute("UPDATE joinmsg SET embed = $1, msg = null WHERE guild_id = $2", True, ctx.guild.id)
            self.bot.joinmsg[ctx.guild.id]['embed'] = True
            self.bot.joinmsg[ctx.guild.id]['message'] = None
            await ctx.send(f"{emotes.white_mark} Welcoming messages will now be embedded! You can change the embed content using `{ctx.prefix}togglemsg welcoming`")
        elif check == True:
            await self.bot.db.execute("UPDATE joinmsg SET embed = $1, msg = null WHERE guild_id = $2", False, ctx.guild.id)
            self.bot.joinmsg[ctx.guild.id]['embed'] = False
            self.bot.joinmsg[ctx.guild.id]['message'] = None
            await ctx.send(f"{emotes.white_mark} Welcoming messages won't be embedded anymore!")
    
    @togglemsg.command(name='leaveembed')
    async def togglemsg_leaveembed(self, ctx):
        """ Enable or disable embedded leaving messages """
        check = await self.bot.db.fetchval("SELECT embed FROM leavemsg WHERE guild_id = $1", ctx.guild.id)
        checks = await self.bot.db.fetchval('SELECT * FROM leavemsg WHERE guild_id = $1', ctx.guild.id)
        if not checks:
            return await ctx.send(f"{emotes.warning} Please enable leaving messages first!")
        if not check:
            await self.bot.db.execute("UPDATE leavemsg SET embed = $1, msg = null WHERE guild_id = $2", True, ctx.guild.id)
            self.bot.leavemsg[ctx.guild.id]['embed'] = True
            self.bot.leavemsg[ctx.guild.id]['message'] = None
            await ctx.send(f"{emotes.white_mark} Leaving messages will now be embedded! You can change the embed content using `{ctx.prefix}togglemsg leaving`")
        elif check == True:
            await self.bot.db.execute("UPDATE leavemsg SET embed = $1, msg = null WHERE guild_id = $2", False, ctx.guild.id)
            self.bot.leavemsg[ctx.guild.id]['embed'] = False
            self.bot.leavemsg[ctx.guild.id]['message'] = None
            await ctx.send(f"{emotes.white_mark} Leaving messages won't be embedded anymore!")

    @commands.group(brief="Manage role on join", description="Setup and toggle role on join")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def joinrole(self, ctx):
        """ Toggle role that will be given to new members """

        if ctx.invoked_subcommand is None:
            db_check = await self.bot.db.fetchval("SELECT guild_id FROM joinrole WHERE guild_id = $1", ctx.guild.id)
            role = await self.bot.db.fetchval("SELECT role_id FROM joinrole WHERE guild_id = $1", ctx.guild.id)
            bots = await self.bot.db.fetchval("SELECT bots FROM joinrole WHERE guild_id = $1", ctx.guild.id)

            if db_check is None:
                return await ctx.send(f"Role on join is disabled in this server.")
            if role and bots:
                roled = ctx.guild.get_role(role)
                roledd = ctx.guild.get_role(bots)
                return await ctx.send(f"**{roled.mention}** ({roled.id}) is role that new members will get and **{roledd.mention}** ({roledd.id}) is role that bots will get!", delete_after=30)
            elif role and not bots:
                roled = ctx.guild.get_role(role)
                return await ctx.send(f"**{roled.mention}** ({roled.id}) is role that new members will get!", delete_after=30)
            elif bots and not role:
                roledd = ctx.guild.get_role(bots)
                return await ctx.send(f"**{roledd.mention}** ({roledd.id}) is role that bots will get!", delete_after=30)

    @joinrole.command(brief="Set role on join for people", description="Set role that new members will get when they join", name="people")
    async def joinrole_people(self, ctx, role: discord.Role):
        """ Choose what role will be given to new members"""

        if role.position == ctx.guild.me.top_role.position or role.position > ctx.guild.me.top_role.position:
            return await ctx.send(f"{emotes.red_mark} The role you've tried to setup is higher than my role. Please make sure I'm above the role you're trying to setup.")

        else:
            db_check = await self.bot.db.fetchval("SELECT guild_id FROM joinrole WHERE guild_id = $1", ctx.guild.id)
            cache = cm.get_cache(self.bot, ctx.guild.id, 'joinrole')
            user_role = await self.bot.db.fetchval("SELECT role_id FROM joinrole WHERE guild_id = $1", ctx.guild.id)

            if db_check is None:
                await self.bot.db.execute(f"INSERT INTO joinrole(guild_id, role_id) VALUES ($1, $2)", ctx.guild.id, role.id)
                if cache:
                    cache['people'] = role.id
                else:
                    self.bot.joinrole[ctx.guild.id] = {'people': role.id, 'bots': None}
                await ctx.send(f"{emotes.white_mark} **{role.mention}** will be given to new members! Use `{ctx.prefix}joinrole toggle` to **disable** it or `{ctx.prefix}joinrole people` to change it", delete_after=30)
            if db_check is not None:
                if user_role is None:
                    await self.bot.db.execute(f"UPDATE joinrole SET role_id = $1 WHERE guild_id = $2", role.id, ctx.guild.id)
                    if cache:
                        cache['people'] = role.id
                    else:
                        self.bot.joinrole[ctx.guild.id] = {'people': role.id, 'bots': None}
                    await ctx.send(f"{emotes.white_mark} **{role.mention}** will be given to members! Use `{ctx.prefix}joinrole toggle` to disable it or `{ctx.prefix}joinrole people` to change it", delete_after=30)
                elif user_role is not None:
                    await self.bot.db.execute(f"UPDATE joinrole SET role_id = $1 WHERE guild_id = $2", role.id, ctx.guild.id)
                    if cache:
                        cache['people'] = role.id
                    else:
                        self.bot.joinrole[ctx.guild.id] = {'people': role.id, 'bots': None}
                    await ctx.send(f"{emotes.white_mark} **{role.mention}** will be given to members from now one! Use `{ctx.prefix}joinrole toggle` to disable it or `{ctx.prefix}joinrole people` to change it", delete_after=30)

    @joinrole.command(brief="Set role on join for bots", description="Set role that bots will get when they join", name="bots")
    async def joinrole_bots(self, ctx, role: discord.Role):
        """ Choose what role will be given to bots"""

        if role.position == ctx.guild.me.top_role.position or role.position > ctx.guild.me.top_role.position:
            return await ctx.send(f"{emotes.red_mark} The role you've tried to setup is higher than my role. Please make sure I'm above the role you're trying to setup.")

        else:
            db_check = await self.bot.db.fetchval("SELECT guild_id FROM joinrole WHERE guild_id = $1", ctx.guild.id)
            cache = cm.get_cache(self.bot, ctx.guild.id, 'joinrole')
            bot_role = await self.bot.db.fetchval("SELECT bots FROM joinrole WHERE guild_id = $1", ctx.guild.id)
                
            if db_check is None:
                await self.bot.db.execute(f"INSERT INTO joinrole(guild_id, bots) VALUES ($1, $2)", ctx.guild.id, role.id)
                if cache:
                    cache['bots'] = role.id
                else:
                    self.bot.joinrole[ctx.guild.id] = {'people': None, 'bots': role.id}
                await ctx.send(f"{emotes.white_mark} **{role.mention}** will be given to bots! Use `{ctx.prefix}joinrole toggle` to **disable** it or `{ctx.prefix}joinrole bots` to change it", delete_after=30)
            if db_check is not None:
                if bot_role is None:
                    await self.bot.db.execute(f"UPDATE joinrole SET bots = $1 WHERE guild_id = $2", role.id, ctx.guild.id)
                    if cache:
                        cache['bots'] = role.id
                    else:
                        self.bot.joinrole[ctx.guild.id] = {'people': None, 'bots': role.id}
                    await ctx.send(f"{emotes.white_mark} **{role.mention}** will be given to bots! Use `{ctx.prefix}joinrole toggle` to disable it or `{ctx.prefix}joinrole bots` to change it", delete_after=30)
                elif bot_role is not None:
                    await self.bot.db.execute(f"UPDATE joinrole SET bots = $1 WHERE guild_id = $2", role.id, ctx.guild.id)
                    if cache:
                        cache['bots'] = role.id
                    else:
                        self.bot.joinrole[ctx.guild.id] = {'people': None, 'bots': role.id}
                    await ctx.send(f"{emotes.white_mark} **{role.mention}** will be given to bots from now one! Use `{ctx.prefix}joinrole toggle` to disable it or `{ctx.prefix}joinrole bots` to change it", delete_after=30)
    
    @joinrole.command(brief="Disable role on join", description="Disable role on join so new members wouldn't be assigned to it when they join", name="toggle")
    async def joinrole_toggle(self, ctx):
        """ Toggle the join role. It is automatically set to `ON` """
        db_check = await self.bot.db.fetchval("SELECT guild_id FROM joinrole WHERE guild_id = $1", ctx.guild.id)
        cache = cm.get_cache(self.bot, ctx.guild.id, 'joinrole')

        if db_check is None:
            return await ctx.send(f"{emotes.red_mark} You don't have any role set yet. Use `{ctx.prefix}joinrole people/bots` to setup the role", delete_after=30)
        if db_check is not None:
            await self.bot.db.execute(f"DELETE FROM joinrole WHERE guild_id = $1", ctx.guild.id)
            self.bot.joinrole.pop(ctx.guild.id)
            await ctx.send(f"{emotes.white_mark} Role on join has been disabled. Use `{ctx.prefix}joinrole people/bots` to enable it back on", delete_after=30)

    @commands.command(brief='Disable a command in your server', aliases=['disablecmd'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def disablecommand(self, ctx, *, command):
        """ Disable command in your server so others couldn't use it
        Once you've disabled it, the command will be locked to server administrators only"""
        cant_disable = ["help", "jishaku", "dev", "disablecmd", "enablecmd", 'admin']
        cmd = self.bot.get_command(command)
        if cmd is None:
            embed = discord.Embed(color=self.color['logembed_color'], description=f"{emotes.red_mark} Command **{command}** doesn't exist.")
            return await ctx.send(embed=embed)

        if cmd.name in cant_disable:
            embed = discord.Embed(color=self.color['logembed_color'], description=f"{emotes.red_mark} Why are you trying to disable **{cmd.name}** you dum dum.")
            return await ctx.send(embed=embed)

        if cmd.parent and str(cmd.parent) not in cant_disable:
            if await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(f"{cmd.parent} {cmd.name}"), ctx.guild.id) is None:
                await self.bot.db.execute("INSERT INTO guilddisabled(guild_id, command) VALUES ($1, $2)", ctx.guild.id, str(f"{cmd.parent} {cmd.name}"))
                return await ctx.send(f"{emotes.white_mark} Okay. **{cmd.parent} {cmd.name}** was disabled.")
            elif await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 and guild_id = $2", str(f"{cmd.parent} {cmd.name}"), ctx.guild.id):
                return await ctx.send(f"{emotes.warning} | `{cmd.parent} {cmd.name}` is already disabled")
        elif cmd.parent and str(cmd.parent) in cant_disable:
            return await ctx.send(f"{emotes.red_mark} You can't do that, sorry!")
        elif not cmd.parent:
            if await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(cmd.name), ctx.guild.id) is None:
                await self.bot.db.execute("INSERT INTO guilddisabled(guild_id, command) VALUES ($1, $2)", ctx.guild.id, str(cmd.name))
                return await ctx.send(f"{emotes.white_mark} Okay. **{cmd.name}** was disabled.")
            elif await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(cmd.name), ctx.guild.id):
                return await ctx.send(f"{emotes.warning} | `{cmd.name}` is already disabled")

    @commands.command(brief='Enable command in your server', aliases=['enablecmd'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def enablecommand(self, ctx,*, command):
        """ Enable disabled command in your servers so others could use it """
        cmd = self.bot.get_command(command)

        if cmd is None:
            return await ctx.send(f"{emotes.red_mark} Command **{command}** doesn't exist.")

        if cmd.parent:
            if await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(f"{cmd.parent} {cmd.name}"), ctx.guild.id) is None:
                return await ctx.send(f"{emotes.warning} | `{cmd.parent} {cmd.name}` is not disabled!")
            elif await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(f"{cmd.parent} {cmd.name}"), ctx.guild.id):
                await self.bot.db.execute("DELETE FROM guilddisabled WHERE command = $1 AND guild_id =$2", str(f"{cmd.parent} {cmd.name}"), ctx.guild.id)
                return await ctx.send(f"{emotes.white_mark} | `{cmd.parent} {cmd.name}` is now enabled!")
        elif not cmd.parent:
            if await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(cmd.name), ctx.guild.id) is None:
                return await ctx.send(f"{emotes.warning} | `{cmd.name}` is not disabled!")
            elif await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(cmd.name), ctx.guild.id):
                await self.bot.db.execute("DELETE FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(cmd.name), ctx.guild.id)
                return await ctx.send(f"{emotes.white_mark} | `{cmd.name}` is now enabled!")
    
    @commands.group(brief='Manage server raid mode', invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(kick_members=True)
    async def raidmode(self, ctx):
        """ Raid is happening in your server? Turn on anti-raider! It'll kick every new member that joins. 
        It'll also inform them in DMs that server is currently in anti-raid mode and doesn't allow new members!
        DMs can also be toggled on and off. They're always on by default"""

        raid_check = await self.bot.db.fetchval("SELECT raidmode FROM raidmode WHERE guild_id = $1", ctx.guild.id)

        if raid_check == False:
            await self.bot.db.execute("UPDATE raidmode SET raidmode = $1 WHERE guild_id = $2", True, ctx.guild.id)
            self.bot.raidmode[ctx.guild.id]['raidmode'] = True
            await ctx.send(f"{emotes.white_mark} Raid mode was activated! New members will get kicked with a message in their DMs")
        elif raid_check == True:
            await self.bot.db.execute("UPDATE raidmode SET raidmode = $1, dm = $2 WHERE guild_id = $3", False, True, ctx.guild.id)
            self.bot.raidmode[ctx.guild.id]['raidmode'] = False
            self.bot.raidmode[ctx.guild.id]['dm'] = True
            await ctx.send(f"{emotes.white_mark} Raid mode was deactivated! New members won't be kicked anymore.")
        
    @raidmode.command(name='toggledm', aliases=['dm'], brief='Toggle off/on the DM message')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def raidmode_toggledm(self, ctx):
        """ Toggle DMs on or off if you want user to get informed about the anti raid mode being enabled
        
        Note: It's on by default!"""
        dm_check = await self.bot.db.fetchval("SELECT dm FROM raidmode WHERE guild_id = $1", ctx.guild.id)

        if dm_check == False:
            await self.bot.db.execute("UPDATE raidmode SET dm = $1 WHERE guild_id = $2", True, ctx.guild.id)
            self.bot.raidmode[ctx.guild.id]['dm'] = True
            return await ctx.send(f"{emotes.white_mark} DMs are now enabled! Users will get DMed anti-raid message")
        elif dm_check == True:
            await self.bot.db.execute("UPDATE raidmode SET dm = $1 WHERE guild_id = $2", False, ctx.guild.id)
            self.bot.raidmode[ctx.guild.id]['dm'] = False
            return await ctx.send(f"{emotes.white_mark} DMs are now disabled! Users won't get DMed anti-raid message")
        else:
            return
    
    @commands.group(brief='See how welcoming and leaving embeds look', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def embedded(self, ctx):
        """ Check how your embedded leaving and welcoming messages looks like """
        await ctx.send_help(ctx.command)

    @embedded.command(name='welcoming')
    @commands.has_permissions(manage_guild=True)
    async def embedded_welcoming(self, ctx):
        """ Check how your embedded welcoming message looks like """
        check = await self.bot.db.fetchval("SELECT embed FROM joinmsg WHERE guild_id = $1", ctx.guild.id)
        embedded = await self.bot.db.fetchval("SELECT msg FROM joinmsg WHERE guild_id = $1", ctx.guild.id)

        if not check:
            return await ctx.send(f"{emotes.warning} You don't have embedded welcoming messages enabled. You can do that by invoking `{ctx.prefix}togglemsg joinembed`")

        elif check:
            if embedded:
                todict = json.loads(embedded)
                await ctx.send(content=f'Your embed looks like this: (If it\'s not being displayed your code is incorrect and you need to change it using `{ctx.prefix}togglemsg welcoming <dict>`)', embed=discord.Embed.from_dict(todict))
            elif not embedded:
                todict = {
                    "plainText": "{{member.mention}}",
                    "title": "Welcome to {{server.name}}",
                    "description": "You are member #{{server.members}} in this server!",
                    "color": 6215030
                    }
                await ctx.send(content='Your embed looks like this', embed=discord.Embed.from_dict(todict))
    
    @embedded.command(name='leaving')
    @commands.has_permissions(manage_guild=True)
    async def embedded_leaving(self, ctx):
        """ Check how your embedded leaving message looks like """
        check = await self.bot.db.fetchval("SELECT embed FROM leavemsg WHERE guild_id = $1", ctx.guild.id)
        embedded = await self.bot.db.fetchval("SELECT msg FROM leavemsg WHERE guild_id = $1", ctx.guild.id)

        if not check:
            return await ctx.send(f"{emotes.warning} You don't have embedded leaving messages enabled. You can do that by invoking `{ctx.prefix}togglemsg leavembed`")

        elif check:
            if embedded:
                todict = json.loads(embedded)
                await ctx.send(content=f'Your embed looks like this: (If it\'s not being displayed your code is incorrect and you need to change it using `{ctx.prefix}togglemsg leaving <dict>`)', embed=discord.Embed.from_dict(todict))
            elif not embedded:
                todict = {
                    "description": "{{member.name}} left the server! There are now {{server.members}} members left!",
                    "color": 13579316
                    }
                await ctx.send(content='Your embed looks like this', embed=discord.Embed.from_dict(todict))
    
    @commands.command(name='antidehoistnick', aliases=['dehoistnick', 'dnick', 'dehnick'], brief='Change automatic nickname for dehoisters')
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def antidehoistnick(self, ctx, new_nick: str):
        """ You can change a nickname that hoisters will be automatically dehoisted to """
        check = await self.bot.db.fetchval("SELECT * FROM antidehoist WHERE guild_id =$1", ctx.guild.id)

        if not check:
            return await ctx.send(f"{emotes.warning} You don't have anti-dehoists enabled. Please enable them using `{ctx.prefix}togglelog antidehoist <channel>`")

        else:
            await self.bot.db.execute("UPDATE antidehoist SET new_nick = $1 WHERE guild_id = $2", new_nick, ctx.guild.id)
            self.bot.antidehoist[ctx.guild.id]['nickname'] = new_nick
            await ctx.send(f"{emotes.white_mark} Hoisters will be automatically dehoisted to {new_nick} now")

def setup(bot):
    bot.add_cog(Managment(bot))

        