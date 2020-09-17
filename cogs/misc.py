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
import random
import aiohttp
import math
import json
import typing

from discord.ext import commands
from discord.utils import escape_markdown
from utils.checks import has_voted, is_guild, test_command
from utils.paginator import Pages
from utils.Nullify import clean
from utils import btime
from datetime import datetime
from db import emotes
from utils.default import color_picker
from utils.caches import CacheManager as cm

class misc(commands.Cog, name="Misc"):

    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:etaa:747192603757248544>"
        self.big_icon = "https://cdn.discordapp.com/emojis/747192603757248544.png?v=1"
        self.color = color_picker('colors')

    async def bot_check(self, ctx):
        if await self.bot.is_owner(ctx.author):
            return True

        if self.bot.lockdown == "True":
            e = discord.Embed(color=self.color['deny_color'], description=f"Hello!\nWe're currently under the maintenance and the bot is unavailable for use. You can join the [support server]({self.bot.support}) to know when we'll be available again!", timestamp=datetime.utcnow())
            e.set_author(name=f"Dredd under the maintenance!", icon_url=self.bot.user.avatar_url)
            e.set_thumbnail(url='https://cdn.discordapp.com/attachments/667077166789558288/747132112099868773/normal_3.gif')
            await ctx.send(embed=e)
            return False
        return True

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36"

    MAX_FILE_SIZE = 1024 * 1024 * 20
    TIMEOUT = 20
    NO_IMG = "http://i.imgur.com/62di8EB.jpg"
    CHUNK_SIZE = 512 * 1024

                
    @commands.command(brief="Search the urban dictionary")
    @commands.guild_only()
    @commands.is_nsfw()
    async def urban(self, ctx, *, urban: str):
        """ Search for a term in the urban dictionary """

        async with aiohttp.ClientSession() as cs:
            async with cs.get(f'http://api.urbandictionary.com/v0/define?term={urban}') as r:
                url = await r.json()

        if url is None:
            return await ctx.send("No URL found")

        count = len(url['list'])
        if count == 0:
            return await ctx.send("No results were found.")
        result = url['list'][random.randint(0, count - 1)]

        definition = result['definition']
        example = result['example']
        if len(definition) >= 1000:
                definition = definition[:1000]
                definition = definition.rsplit(' ', 1)[0]
                definition += '...'

        embed = discord.Embed(color=self.color['embed_color'],
                              description=f"**Search:** {result['word']} | **by:** {result['author']}")
        embed.add_field(
            name="Votes:", value=f"\U0001f44d **{result['thumbs_up']}** | \U0001f44e **{result['thumbs_down']}**", inline=False)
        embed.add_field(name="Definition", value=definition, inline=True)
        embed.add_field(name="Example", value=example, inline=True)
        embed.set_footer(text=f"© {self.bot.user}")

        async with ctx.channel.typing():
            await asyncio.sleep(5)
            return await ctx.send(embed=embed)

    @commands.command(brief="Suggest anything", aliases=['idea'])
    async def suggest(self, ctx, *, suggestion: commands.clean_content):
        """ Suggest anything you want to see in the server/bot!
        Suggestion will be sent to support server for people to vote."""

        try:
            await ctx.message.delete()
        except Exception:
            pass

        logchannel = self.bot.get_channel(674929868345180160)

        if len(suggestion) > 384:
            return await ctx.send(f"{emotes.warning} Your suggestion is over 384 characters!")
        elif len(suggestion) < 384:
            ids = await self.bot.db.fetch("SELECT suggestion_id FROM suggestions")
            e = discord.Embed(color=self.color['logging_color'], title=f"New suggestion by {ctx.author.name}! #{len(ids) + 1}", description=f"> {suggestion}", timestamp=datetime.utcnow())
            e.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)
            msg = await logchannel.send(embed=e)
            await msg.add_reaction(f"{emotes.white_mark}")
            await msg.add_reaction(f"{emotes.red_mark}")
            await self.bot.db.execute("INSERT into suggestions(suggestion_info, suggestion_id, user_id, msg_id, approved) VALUES($1, $2, $3, $4, $5)", suggestion, len(ids) + 1, ctx.author.id, msg.id, False)
            await self.bot.db.execute("INSERT INTO track_suggest(user_id, suggestion_id) VALUES($1, $2)", ctx.author.id, len(ids) + 1)
            e = discord.Embed(color=self.color['approve_color'], description=f"You'll get notified in your DMs when the suggestion will be approved or denied\nPeople can also follow this suggestion using `{ctx.prefix}follow suggestion {len(ids) + 1}`\n\n**Suggestion:**\n>>> {suggestion}", timestamp=datetime.utcnow())
            e.set_author(name=f"Suggestion sent as #{len(ids) + 1}", icon_url=ctx.author.avatar_url)
            return await ctx.send(embed=e)

    @commands.group(brief='Follow your or other suggestions')
    async def follow(self, ctx):
        """ You can follow suggestions 
        When they'll get approved or denied you'll get a dm from bot with a result """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @follow.command()
    async def suggestion(self, ctx, suggestionid: int):
        """ Follow suggestions """
        check = await self.bot.db.fetchval("SELECT approved FROM suggestions WHERE suggestion_id = $1", suggestionid)
        tracks = await self.bot.db.fetchval("SELECT * FROM track_suggest WHERE user_id = $1 AND suggestion_id = $2", ctx.author.id, suggestionid)

        if check is None:
            await ctx.send(f"{emotes.warning} Looks like suggestion **#{suggestionid}** doesn't exist.")
        elif check == False and tracks is None:
            await self.bot.db.execute("INSERT INTO track_suggest(user_id, suggestion_id) VALUES($1, $2)", ctx.author.id, suggestionid)
            await ctx.send(f"{emotes.white_mark} Started following suggestion **#{suggestionid}**, you'll get notified when the suggestion will be approved or denied")
        elif check == True:
            await ctx.send(f"{emotes.warning} That suggestion is already approved or denied, you cannot follow it.")
        elif tracks:
            await ctx.send(f"{emotes.red_mark} You're already following suggestion **#{suggestionid}**")
    
    @commands.command(brief='Set your AFK state', aliases=['afk'])
    @commands.guild_only()
    @has_voted()
    async def setafk(self, ctx, *, message: str = None):
        """
        Set your AFK state. Others will get notified when they'll mention you.
        """
        db_check = await self.bot.db.fetchval("SELECT * FROM userafk WHERE guild_id = $1 AND user_id = $2", ctx.guild.id, ctx.author.id)
        if message is None:
            msgs = "I'm AFK :)"
        elif message and len(message) < 128:
            msgs = message
        else:
            return await ctx.send(f"{emotes.red_mark} Your message is too long! You can have max 128 characters and you have {len(message)}.")
        if db_check is None:
            await self.bot.db.execute("INSERT INTO userafk(user_id, guild_id, message, time) VALUES ($1, $2, $3, $4)", ctx.author.id, ctx.guild.id, msgs, datetime.now())
            self.bot.afk_users.append((ctx.author.id, ctx.guild.id, msgs, datetime.now()))
            await ctx.send(f"{emotes.white_mark} | Set your **AFK** state to --> `{msgs}`", delete_after=20)
        else:
            await self.bot.db.execute("UPDATE userafk SET message = $1 WHERE user_id = $2 AND guild_id = $3", msgs, ctx.author.id, ctx.guild.id)
            for user, guild, msg, time in self.bot.afk_users:
                if ctx.author.id == user and ctx.guild.id == guild:
                    self.bot.afk_users.remove((user, guild, msg, time))
                    self.bot.afk_users.append((user, guild, msgs, datetime.now()))
            await ctx.send(f"{emotes.white_mark} | Changed your **AFK** state to --> `{msgs}`", delete_after=20)
            

    @commands.group(brief="Manage your todo list", invoke_without_command=True)
    async def todo(self, ctx):
        ''' Your todo list '''
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)
        
    @todo.command(aliases=['a'])
    async def add(self, ctx, *, todo: commands.clean_content):
        """ Add something to your todo list 
        Time is in UTC """        
        todocheck = await self.bot.db.fetchval("SELECT todo FROM todolist WHERE user_id = $1 AND todo = $2", ctx.author.id, todo)

        if todocheck:
            return await ctx.send(f"{emotes.red_mark} You already have `{todo}` in your todo list")
        await self.bot.db.execute("INSERT INTO todolist(user_id, guild_id, todo, time, jump_to) VALUES ($1, $2, $3, $4, $5)", ctx.author.id, ctx.guild.id, todo, datetime.now(), ctx.message.jump_url)
        if len(todo) > 200:
            todo = todo[:200] + '...'
        await ctx.send(f"{emotes.white_mark} Added `{todo}` to your todo list")
    
    @todo.command(name='list', aliases=['l'])
    async def _list(self, ctx):
        """ Check your todo list """
        todos = []
        for num, todo, in enumerate(await self.bot.db.fetch('SELECT todo FROM todolist WHERE user_id = $1 ORDER BY time ASC', ctx.author.id), start=0):
            if len(todo['todo']) > 195:
                yourtodo = todo['todo'][:190] + '...'
            elif len(todo['todo']) < 195:
                yourtodo = todo['todo']
            todos.append(f"`[{num + 1}]` {yourtodo}\n")

        if len(todos) == 0:
            return await ctx.send(f"{emotes.red_mark} You don't have any todos")

        paginator = Pages(ctx,
                          title=f"Your todo list:",
                          entries=todos,
                          thumbnail=None,
                          per_page = 10,
                          embed_color=ctx.bot.embed_color,
                          show_entry_count=True)
        try:
            await paginator.paginate()
        except discord.HTTPException:
            paginators = Pages(ctx,
                          title=f"Your todo list:",
                          entries=todos,
                          thumbnail=None,
                          per_page = 5,
                          embed_color=ctx.bot.embed_color,
                          show_entry_count=True)
            await paginators.paginate()
    
    @todo.command(aliases=['r'])
    async def remove(self, ctx, *, todoid: str):
        """ Remove todo from your todo list """
    
        todos = await self.bot.db.fetch('SELECT * FROM todolist WHERE user_id = $1 ORDER BY time', ctx.author.id)
        if not todos:
            return await ctx.send(f'{emotes.red_mark} You don\'t have any todos')

        todos = {f'{index + 1}': todo for index, todo in enumerate(todos)}
        todos_to_remove = []

        todo_ids = todoid

        todo_ids = todo_ids.split(' ')
        for todo_id in todo_ids:

            if not todo_id.isdigit():
                return await ctx.send(f'{emotes.red_mark} You\'ve provided a wrong #')
            if todo_id not in todos.keys():
                return await ctx.send(f'{emotes.red_mark} I can\'t find todo `#{todo_id}` in your todo list list.')
            if todo_id in todos_to_remove:
                return await ctx.send(f'{emotes.red_mark} You provided todo `#{todo_id}` more than once.')
            todos_to_remove.append(todo_id)

        query = 'DELETE FROM todolist WHERE user_id = $1 and time = $2'
        entries = [(todos[todo_id]['user_id'], todos[todo_id]['time']) for todo_id in todos_to_remove]
        await self.bot.db.executemany(query, entries)
        dot = '...'
        contents = '\n• '.join([f'{escape_markdown(todos[todo_id]["todo"][:150], as_needed=True)}' for todo_id in todos_to_remove])
        return await ctx.send(f"{emotes.white_mark} Removed **{len(todo_ids)}** todo from your todo list:\n• {contents}")

    @todo.command(aliases=['c'])
    async def clear(self, ctx):
        """ Clear your todo list """

        todos = await self.bot.db.fetch('SELECT * FROM todolist WHERE user_id = $1 ORDER BY time', ctx.author.id)
        if not todos:
            return await ctx.send(f'{emotes.red_mark} You don\'t have any todos')

        def check(r, u):
            return u.id == ctx.author.id and r.message.id == checkmsg.id
            
        try:
            checkmsg = await ctx.send(f"Are you sure you want to clear **{len(todos)}** todos from your todo list?")
            await checkmsg.add_reaction(f"{emotes.white_mark}")
            await checkmsg.add_reaction(f"{emotes.red_mark}")
            react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30)    
            
            if str(react) == f"{emotes.white_mark}":
                try:
                    await checkmsg.clear_reactions()
                except:
                    pass
                await checkmsg.edit(content=f"{emotes.white_mark} Deleted {len(todos)} todos from your todo list", delete_after=15)
                await self.bot.db.execute("DELETE FROM todolist WHERE user_id = $1", ctx.author.id)
                
            if str(react) == f"{emotes.red_mark}":
                try:
                    await checkmsg.clear_reactions()
                except:
                    pass
                await checkmsg.edit(content=f"{emotes.white_mark} I'm not deleting any todos from your todo list.", delete_after=15)

        except asyncio.TimeoutError:
            try:
                await checkmsg.clear_reactions()
            except:
                pass
            await checkmsg.edit(content="Cancelling...", delete_after=15)
        
    @todo.command(aliases=['i'])
    async def info(self, ctx, todoid: str):
        """ Get more information on your todo """
        
        todos = await self.bot.db.fetch('SELECT * FROM todolist WHERE user_id = $1 ORDER BY time', ctx.author.id)
        if not todos:
            return await ctx.send(f'{emotes.red_mark} You don not have any todos.')


        todos = {f'{index + 1}': todo for index, todo in enumerate(todos)}

        if not todoid.isdigit():
            return await ctx.send(f'{emotes.red_mark} You\'ve provided a wrong #')
        if todoid not in todos.keys():
            return await ctx.send(f'{emotes.red_mark} I can\'t find todo `#{todoid}` in your todo list list.')

        todo = todos[todoid]

        e = discord.Embed(color=self.color['embed_color'], title=f'Information on your todo #{todoid}:')
        
        if len(todo['todo']) > 1800:
            thetodo = todo['todo'][:1800] + '...'
        else:
            thetodo = todo['todo']
        e.description = f"""
**Todo content:** {thetodo}

**Added to the todo list:** {btime.human_timedelta(todo['time'])}
{f"[Jump to original message]({todo['jump_to']})" if todo['jump_to'] is not None else "Unable to locate the message"}"""
        # e.add_field(name="Added to todo list:", value=btime.human_timedelta(todo['time']))
        # e.add_field(name=f"Jump to:", value=f"[Jump to original message]({todo['jump_to']})" if todo['jump_to'] is not None else "Unable to locate the message", inline=False)
        await ctx.send(embed=e)

        
    @todo.command(aliases=['e'])
    async def edit(self, ctx, todoid: str, *, content: commands.clean_content):
        """ Edit todo in your todo list """

        todos = await self.bot.db.fetch('SELECT * FROM todolist WHERE user_id = $1 ORDER BY time', ctx.author.id)
        if not todos:
            return await ctx.send(f'{emotes.red_mark} You don not have any todos.')


        todos = {f'{index + 1}': todo for index, todo in enumerate(todos)}

        if not todoid.isdigit():
            return await ctx.send(f'{emotes.red_mark} You\'ve provided wrong id')
        if todoid not in todos.keys():
            return await ctx.send(f'{emotes.red_mark} I can\'t find todo `#{todoid}` in your todo list list.')

        todo_to_edit = todos[todoid]

        todocheck = await self.bot.db.fetchval("SELECT todo FROM todolist WHERE user_id = $1 AND todo = $2", ctx.author.id, content)

        if todocheck:
            return await ctx.send(f"{emotes.red_mark} You already have `{clean(content)}` in your todo list")

        query = 'UPDATE todolist SET todo = $1, jump_to = $2 WHERE user_id = $3 and time = $4'
        await self.bot.db.execute(query, content, ctx.message.jump_url, todo_to_edit['user_id'], todo_to_edit['time'])

        if len(todo_to_edit['todo']) > 150:
            beforetodo = todo_to_edit['todo'][:150] + '...'
        else:
            beforetodo = todo_to_edit['todo']
        if len(content) > 150:
            content = content[:150] + '...'
        else:
            content = content

        return await ctx.send(f"{emotes.white_mark} Changed `{clean(beforetodo)}` to `{clean(content)}` in your todo list")


    @commands.command(brief='Check yours or the users status')
    async def status(self, ctx, member: discord.Member = None):
        """ Check how long have you/others have been online/idle/dnd/offline for.
        You need to be opted in first."""
        member = member or ctx.author

        if member.bot:
            return await ctx.send(f'{emotes.warning} I don\'t log bot statuses')

        black = await self.bot.db.fetchval("SELECT * FROM status_op_out WHERE user_id = $1", member.id)
        author_black = await self.bot.db.fetchval('SELECT * FROM status_op_out WHERE user_id = $1', ctx.author.id)
        if black is None:
            return await ctx.send(f"**{member.name}** is not opted in. {f'Do `{ctx.prefix}status-opt` to opt in.' if member == ctx.author else ''}")

        elif author_black is None:
            return await ctx.send(f"{emotes.warning} You need to be opted in before checking someone's status. You can opt-in by invoking `{ctx.prefix}status-opt`")
        
        
        status = await self.bot.db.fetchval("SELECT time FROM useractivity WHERE user_id = $1", member.id)
        name = await self.bot.db.fetchval("SELECT activity_title FROM useractivity WHERE user_id = $1", member.id)

        if status and name:
            await ctx.send(f"**{member.name}** has been **{name}** for {btime.human_timedelta(status, suffix=None)}.")
        else:
            return await ctx.send('I have nothing logged yet')
    
    @commands.command(name='status-opt', aliases=['statusopt', 'sopt'], brief="Disable or enable status logging")
    async def status_opt(self, ctx):
        """ Opt in yourself so I would log your statuses. You can also opt in"""
        nicks_opout = await self.bot.db.fetchval("SELECT user_id FROM status_op_out WHERE user_id = $1", ctx.author.id)
        if nicks_opout is not None:
            def check(r, u):
                return u.id == ctx.author.id and r.message.id == checkmsg.id
            try:
                checkmsg = await ctx.send(f"Are you sure you want to opt-out? Once you'll opt-out I won't be logging your statuses anymore and all the data that I have stored in my database will also be deleted.")
                await checkmsg.add_reaction(f'{emotes.white_mark}')
                await checkmsg.add_reaction(f'{emotes.red_mark}')
                react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30.0)

                if str(react) == f"{emotes.white_mark}": 
                    await self.bot.db.execute('DELETE FROM status_op_out WHERE user_id = $1', ctx.author.id)
                    self.bot.status_op_out.pop(ctx.author.id)
                    await ctx.channel.send(f"{emotes.white_mark} You're now opted-in! I'll be logging your statuses once again.")
                    await checkmsg.delete()


                if str(react) == f"{emotes.red_mark}":      
                    await checkmsg.delete()
                    await ctx.channel.send("Alright. Not opting you out")
            except Exception as e:
                print(e)
                return
            
        elif nicks_opout is None:
            def check(r, u):
                return u.id == ctx.author.id and r.message.id == checkmsg.id
            try:
                checkmsg = await ctx.send(f"Are you sure you want to opt-in? I'll be logging your activity status and you will opt in.")
                await checkmsg.add_reaction(f'{emotes.white_mark}')
                await checkmsg.add_reaction(f'{emotes.red_mark}')
                react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30.0)

                if str(react) == f"{emotes.white_mark}": 
                    await self.bot.db.execute('INSERT INTO status_op_out(user_id) VALUES($1)', ctx.author.id)
                    self.bot.status_op_out[ctx.author.id] = '.'
                    await self.bot.db.execute("DELETE FROM useractivity WHERE user_id = $1", ctx.author.id)
                    await ctx.channel.send(f"{emotes.white_mark} You're now opted-in! I'll be logging your statuses from now on!")
                    await checkmsg.delete()


                if str(react) == f"{emotes.red_mark}":      
                    await checkmsg.delete()
                    await ctx.channel.send("Alright. Not opting you in")
            except Exception as e:
                print(e)
                return
    
    @commands.group(name='snipe', brief='Gets the most recent deleted message', invoke_without_command=True)
    @commands.guild_only()
    async def snipe(self, ctx, channel: discord.TextChannel = None):
        """ Get the most recent deleted message
        You can pass in the channel mention/name/id so it'd fetch message in that channel """
        channel = channel or ctx.channel

        check = cm.get_cache(self.bot, channel.id, 'snipes')
        if check is None:
            return await ctx.send(f"{emotes.red_mark} Haven't logged anything yet")
        content = check['message']
        if len(content) > 2000:
            content = content[:2000]
            content += '...'
        
        content = content or "*[Content unavailable]*"
        e = discord.Embed(color=self.color['embed_color'])
        a = ctx.guild.get_member(check['author'])
        if a is None:
            return await ctx.send(f"{emotes.warning} Couldn't get that member.")
        e.set_author(name=f"Deleted by {a}", icon_url=a.avatar_url)
        e.description = f"{content}"
        e.set_footer(text=f"Deleted {btime.human_timedelta(check['deleted_at'])} in {channel.name}")

        await ctx.send(embed=e)
    
    @snipe.command(name='op-out', brief='Disable or enable your snipes logging')
    @commands.guild_only()
    async def snipe_opt_out(self, ctx):
        """ Opts you out or in from logging your messages"""

        
        msgs_opout = await self.bot.db.fetchval("SELECT user_id FROM snipe_op_out WHERE user_id = $1", ctx.author.id)
        if msgs_opout is None:
            def check(r, u):
                return u.id == ctx.author.id and r.message.id == checkmsg.id
            try:
                checkmsg = await ctx.send(f"Are you sure you want to opt-out? Once you'll opt-out I won't be logging your deleted messages (snipes) anymore and all the data that I have stored in my database will also be deleted.")
                await checkmsg.add_reaction(f'{emotes.white_mark}')
                await checkmsg.add_reaction(f'{emotes.red_mark}')
                react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30.0)

                if str(react) == f"{emotes.white_mark}": 
                    await self.bot.db.execute('INSERT INTO snipe_op_out(user_id) VALUES($1)', ctx.author.id)
                    self.bot.snipes_op_out[ctx.author.id] = '.'
                    await ctx.channel.send(f"{emotes.white_mark} You're now opted-out! I won't be logging your deleted messages anymore")
                    await checkmsg.delete()


                if str(react) == f"{emotes.red_mark}":      
                    await checkmsg.delete()
                    await ctx.channel.send("Alright. Not opting you out")
            except Exception as e:
                print(e)
                return
            
        elif msgs_opout is not None:
            def check(r, u):
                return u.id == ctx.author.id and r.message.id == checkmsg.id
            try:
                checkmsg = await ctx.send(f"Are you sure you want to opt-in? I'll be logging your deleted messages (snipes) and you will opt in.")
                await checkmsg.add_reaction(f'{emotes.white_mark}')
                await checkmsg.add_reaction(f'{emotes.red_mark}')
                react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30.0)

                if str(react) == f"{emotes.white_mark}": 
                    await self.bot.db.execute("DELETE FROM snipe_op_out WHERE user_id = $1", ctx.author.id)
                    self.bot.snipes_op_out.pop(ctx.author.id)
                    await ctx.channel.send(f"{emotes.white_mark} You're now opted-in! I'll be logging your deleted messages (snipes) once again")
                    await checkmsg.delete()


                if str(react) == f"{emotes.red_mark}":      
                    await checkmsg.delete()
                    await ctx.channel.send("Alright. Not opting you in")
            except Exception as e:
                print(e)
                return

    @commands.command(brief='Get the list of bot partners', aliases=['partners', 'plist'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def partnerslist(self, ctx):
        """ Displays a list of partners """
        partners = await self.bot.db.fetch("SELECT * FROM partners")

        partner = []
        for res in partners:
            user = await self.bot.fetch_user(res['user_id'])
            partner.append(f"**Partner:** {user} ({user.id})" + f"\n**Partnered for:** {btime.human_timedelta(res['partnered_since'], suffix=None)}" + f"\n**Partner type:** {res['partner_type']}" + f"\n**Partnered message:**\n>>> {res['partner_message']}")
        
        paginator = Pages(ctx,
                          title=None,
                          entries=partner,
                          thumbnail=None,
                          per_page = 1,
                          embed_color=ctx.bot.embed_color,
                          show_entry_count=True)
        await paginator.paginate()


    @is_guild(568567800910839811)
    @commands.command(brief="Ice's lmao count", hidden=True)
    async def lmaocount(self, ctx):

        numla = await self.bot.db.fetchval("SELECT count FROM lmaocount WHERE user_id = $1", 302604426781261824)
        numlf = await self.bot.db.fetchval("SELECT lf FROM lmaocount WHERE user_id = $1", 302604426781261824)

        ice = self.bot.get_user(302604426781261824)
        await ctx.send(f"**{ice}** said `lmao` **{numla}** times, and `lmfao` **{numlf}** times.")
    

def setup(bot):
    bot.add_cog(misc(bot))
