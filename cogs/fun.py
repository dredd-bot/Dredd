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
import json
import random
import aiohttp

from discord.ext import commands
from utils.i18n import locale_doc


class fun(commands.Cog, name="Fun"):

    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:funn:747192603564441680>"
        self.big_icon = "https://cdn.discordapp.com/emojis/747192603564441680.png?v=1"

    @commands.command(brief=_("Rate something"))
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def rate(self, ctx, *, thing):
        _(""" Rates what you desire """)

        if len(str(thing)) > 500:
            return await ctx.send(_("{0} The thing is {1} characters over the limit.").format(
                self.bot.settings['emojis']['misc']['warn'],
                len(str(thing)) - 500
            ))

        num = random.randint(0, 100)
        deci = random.randint(0, 9)
        deci = 0 if num == 100 else deci

        if thing in ['Moksej', 'Dredd', '<@345457928972533773>', '<@!345457928972533773>', '<@667117267405766696>', '<@!667117267405766696>']:
            num = 100
            deci = 0

        rating = f"{num}.{deci}"
        await ctx.send(_("I rate {0} **{1}** out of **100**.").format(thing, rating))

    @commands.command(brief=_("Talk with a chat bot"), aliases=['chat', 'cb', 'chat-bot'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def chatbot(self, ctx, *, message: str):
        _(""" Talk about life with a chat bot :) """)

        await ctx.channel.trigger_typing()
        try:
            res = await self.bot.cleverbot.ask(message)
            await ctx.reply(res.text, allowed_mentions=discord.AllowedMentions(replied_user=False))
        except Exception:
            await ctx.reply(_("Looks like the chatbot escaped!"), allowed_mentions=discord.AllowedMentions(replied_user=False))

    @commands.command(brief=_("F in the chat"), aliases=['f'])
    @locale_doc
    async def pressf(self, ctx, *, text: str = None):
        _(""" Press F to pay respect """)

        if text and len(text) > 500:
            return await ctx.send(_("{0} The text is {1} characters over the limit.").format(
                self.bot.settings['emojis']['misc']['warn'],
                len(text) - 500
            ))
        hearts = ['❤', '💛', '💚', '💙', '💜']
        reason = _(" for **{0}** ").format(text) if text else ""
        await ctx.send(_("**{0}** has paid their respect {1}{2}").format(ctx.author.name, reason, random.choice(hearts)), allowed_mentions=discord.AllowedMentions(users=True))

    @commands.command(aliases=['8ball'], brief=_("Ask the almighty 8ball what you desire "))
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def eightball(self, ctx, *, question):
        _(""" Do you have a question? Ask the almighty 8ball what you should do """)

        await ctx.trigger_typing()

        with open("db/lines.json", "r") as f:
            data = json.load(f)

        responses = data["eightball"]

        if len(question) > 500:
            return await ctx.send(_("{0} The question is {1} characters over the limit.").format(
                self.bot.settings['emojis']['misc']['warn'],
                len(question) - 500
            ))

        to_send = _("**You've asked the almighty 8ball a question -** {0}\n\n**The 8ball says:** {1}").format(
            question, random.choice(responses)
        )

        await ctx.send(to_send, allowed_mentions=discord.AllowedMentions(users=True))

    @commands.command(brief=_("Reverse something"))
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def reverse(self, ctx, *, text: str):
        _(""" !poow ,ffuts esreveR. Everything you type after reverse will of course, be reversed """)

        if len(text) > 500:
            return await ctx.send(_("{0} The text you want to reverse is {1} characters over the limit.").format(
                self.bot.settings['emojis']['misc']['warn'],
                len(text) - 500
            ))

        to_send = _("**Text to reverse:** {0}\n\n**Reversed:** {1}").format(
            text, text[::-1]
        )

        await ctx.send(to_send, allowed_mentions=discord.AllowedMentions(users=True))

    @commands.command(brief=_("Choose between multiple choices"))
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def choose(self, ctx, *choices: str):
        _(""" Choose between multiple choices. """)

        if len(choices) > 10 or len(str(choices)) > 500:
            return await ctx.send(_("{0} There are either too many choices (10) or you're over 500 characters.").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        try:
            choice = ', '.join(choices)

            to_send = _("**Available choices:** {0}\n\n**I choose:** {1}").format(
                choice, random.choice(choices)
            )
            await ctx.send(to_send, allowed_mentions=discord.AllowedMentions(users=True))
        except IndexError:
            await ctx.send(_("{0} | I can't choose from an empty list of choices!").format(self.bot.settings['emojis']['misc']['warn']))

    @commands.command(aliases=['howhot'], brief=_("Check someones hotness"))
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def hot(self, ctx, *, user: discord.Member = None):
        _(""" I wonder how hot are you ;p """)

        user = user or ctx.author
        owner = self.bot.get_user(345457928972533773)
        if user == owner:
            return await ctx.send(_("The hot calculator has melted down because of him :fire:"))

        bot = self.bot.get_user(667117267405766696)
        if user == bot:
            return await ctx.send(_("I'm too hot for you 😏"))

        if user is None:
            user = ctx.author

        random.seed(user.id)
        r = random.randint(1, 100)
        hot = r / 1.17

        emoji = "\U0001f494"
        if hot > 25:
            emoji = "\U0001f494"
        if hot > 50:
            emoji = "\U00002764"
        if hot > 75:
            emoji = "\U0001f49e"
        await ctx.send(_("**{0}** is **{1}%** hot. {2}").format(user, f'{hot:.2f}', emoji), allowed_mentions=discord.AllowedMentions(users=True))

    @commands.command(brief=_("Read a random dad joke"))
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def dadjoke(self, ctx):
        _(""" Read a random dad joke """)

        async with aiohttp.ClientSession() as session:
            resp = await session.get("https://icanhazdadjoke.com", headers={"Accept": "text/plain"})
            await ctx.send((await resp.content.read()).decode("utf-8 "))

    @commands.command(brief=_("Roast someone"))
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def roast(self, ctx, member: discord.Member = None, *bypass):
        _(""" Roast someone in the server. """)

        member = member or ctx.author
        owner = self.bot.get_user(345457928972533773)
        if member == owner and not bypass or bypass and not ctx.message.content.lower().endswith(self.bot.settings['bypass']['owner-bypass']):
            return await ctx.send(_("You can't roast Moksej! I'll drop you a hint, though."
                                    " There's a bypass that you can use to roast him ;)"))

        bot = self.bot.get_user(667117267405766696)
        if member == bot:
            return await ctx.send(_("Don't you dare do that!"))

        r = await self.bot.session.get("https://evilinsult.com/generate_insult.php?lang=en&type=text")
        if 500 % (r.status + 1) == 500:
            return await ctx.send(_("Roast api seems to be down, try again later!"))

        await ctx.send(f"{member.name}, {await r.text()}")

    @commands.command(brief="A *~~hidden~~* duck image command.", aliases=['duckmasteral', 'quacky', 'uck', '\U0001f986'], hidden=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def quack(self, ctx):  # You found a secret! Congradulations 🎉
        """ A *~~hidden~~* duck image command.\nPowered by random-d.uk | Not secretly added by Duck <a:BongoCoding:806396390103187526> """

        embed = discord.Embed(title='Quack Quack :duck:', color=discord.Color.orange())
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text='Powered by random-d.uk', icon_url="https://cdn.discordapp.com/avatars/426787835044036610/795ed0c0b2da8d6c37c071dc61e0c77f.png")
        file = random.choice(['jpg', 'gif'])
        if file == 'jpg':
            embed.set_image(url=f'https://random-d.uk/api/{random.randint(1,191)}.jpg')
        elif file == 'gif':
            embed.set_image(url=f'https://random-d.uk/api/{random.randint(1,42)}.gif')
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(fun(bot))
