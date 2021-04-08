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

import datetime
import re

import parsedatetime as pdt
from dateutil.relativedelta import relativedelta
from discord.ext import commands


class plural:
    def __init__(self, value):
        self.value = value

    def __format__(self, format_spec):
        v = self.value
        singular, sep, plural = format_spec.partition('|')
        plural = plural or f'{singular}s'
        if abs(v) != 1:
            return f'{v} {plural}'
        return f'{v} {singular}'


def human_join(seq, delim=', ', final='or'):
    size = len(seq)
    if size == 0:
        return ''

    if size == 1:
        return seq[0]

    if size == 2:
        return f'{seq[0]} {final} {seq[1]}'

    return delim.join(seq[:-1]) + f' {final} {seq[-1]}'


class HumanTime:
    calendar = pdt.Calendar(version=pdt.VERSION_CONTEXT_STYLE)

    def __init__(self, argument, *, now=None):
        now = now or datetime.datetime.utcnow()
        dt, status = self.calendar.parseDT(argument, sourceTime=now)
        if not status.hasDateOrTime:
            raise commands.BadArgument('invalid time provided, try e.g. "tomorrow" or "3 days"')

        if not status.hasTime:
            # replace it with the current time
            dt = dt.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=now.microsecond)

        self.dt = dt
        self._past = dt < now.replace(tzinfo=None)

    @classmethod
    async def convert(cls, ctx, argument):
        return cls(argument, now=ctx.message.created_at.replace(tzinfo=None))


class ShortTime:
    compiled = re.compile("""(?:(?P<years>[0-9])(?: years?|y))?             # e.g. 2y
                             (?:(?P<months>[0-9]{1,2})(?: months?|mo))?     # e.g. 2months
                             (?:(?P<weeks>[0-9]{1,4})(?: weeks?|w))?        # e.g. 10w
                             (?:(?P<days>[0-9]{1,5})(?: days?|d))?          # e.g. 14d
                             (?:(?P<hours>[0-9]{1,5})(?: hours?|h))?        # e.g. 12h
                             (?:(?P<minutes>[0-9]{1,5})(?: minutes?|m))?    # e.g. 10m
                             (?:(?P<seconds>[0-9]{1,5})(?: seconds?|s))?    # e.g. 15s
                          """, re.VERBOSE)

    def __init__(self, argument, *, now=None):
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            raise commands.BadArgument('invalid time provided')

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        now = now or datetime.datetime.utcnow()
        self.dt = now.replace(tzinfo=None) + relativedelta(**data)

    @classmethod
    async def convert(cls, ctx, argument):
        return cls(argument, now=ctx.message.created_at)


class Time(HumanTime):
    def __init__(self, argument, *, now=None):
        try:
            o = ShortTime(argument, now=now.replace(tzinfo=None))
        except Exception:
            super().__init__(argument)
        else:
            self.dt = o.dt
            self._past = False


class FutureTime(Time):
    def __init__(self, argument, *, now=None):
        super().__init__(argument, now=now.replace(tzinfo=None))

        if self._past:
            raise commands.BadArgument(_("{0} The time you've provided is in the past").format(self.bot.settings['emojis']['misc']['warn']))


class UserFriendlyTime(commands.Converter):
    """That way quotes aren't absolutely necessary."""
    def __init__(self, converter=None, *, default=None):
        if isinstance(converter, type) and issubclass(converter, commands.Converter):
            converter = converter()

        self.converter = converter
        self.default = default

    async def check_constraints(self, ctx, now, remaining):
        if self.dt < now:
            raise commands.BadArgument(_('This time is in the past.'))

        if not remaining:
            if self.default is None:
                raise commands.BadArgument(_('Missing argument after the time.'))
            remaining = self.default

        self.arg = remaining
        return self

    async def convert(self, ctx, argument):
        try:
            calendar = HumanTime.calendar
            # regex = ShortTime.compiled
            now = ctx.message.created_at.replace(tzinfo=None)

            match = None  # regex.match(argument)
            if match is not None and match.group(0):
                data = {k: int(v) for k, v in match.groupdict(default=0).items()}
                remaining = argument[match.end():].strip()
                self.dt = now + relativedelta(**data)
                return await self.check_constraints(ctx, now, remaining)

            if argument.endswith('from now'):
                argument = argument[:-8].strip()

            if argument[0:2] == 'me':
                # starts with "me to", "me in", or "me at "
                if argument[0:6] in ('me to ', 'me in ', 'me at '):
                    argument = argument[6:]
            if argument.startswith("in "):
                argument = argument[3:]

            elements = calendar.nlp(argument, sourceTime=now)
            if elements is None or len(elements) == 0:
                raise commands.BadArgument(_('Time Error! try "in an hour" or "5 days".'))

            dt, status, begin, end, dt_string = elements[0]

            self.dt = dt

            if begin in (0, 1):
                if begin == 1:
                    # check if it's quoted:
                    if argument[0] != '"':
                        raise commands.BadArgument(_('Expected quote before time input...'))

                    if not (end < len(argument) and argument[end] == '"'):
                        raise commands.BadArgument(_('If the time is quoted, you must unquote it.'))

                    remaining = argument[end + 1:].lstrip(' ,.!')
                else:
                    remaining = argument[end:].lstrip(' ,.!')
            elif len(argument) == end:
                remaining = argument[:begin].strip()

            return await self.check_constraints(ctx, now, remaining)
        except Exception as e:
            return await ctx.channel.send(e)
            raise commands.BadArgument(_("Sorry, but I did not understand what you meant. You probably didn't specify the time or you specified it in another language (not English)"))


def human_timedelta(dt, *, source=None, accuracy=3, brief=False, suffix=True):
    now = source or datetime.datetime.now()
    # Microsecond free zone
    now = now.replace(microsecond=0)
    dt = dt.replace(microsecond=0)

    if hasattr(now, 'tzinfo'):
        now.replace(tzinfo=None)
    if hasattr(dt, 'tzinfo'):
        dt.replace(tzinfo=None)

    # This implementation uses relativedelta instead of the much more obvious
    # divmod approach with seconds because the seconds approach is not entirely
    # accurate once you go over 1 week in terms of accuracy since you have to
    # hardcode a month as 30 or 31 days.
    # A query like "11 months" can be interpreted as "!1 months and 6 days"
    if dt > now:
        delta = relativedelta(dt, now)
        suffix = ''
    else:
        delta = relativedelta(now, dt)
        suffix = ' ago' if suffix else ''

    attrs = [
        ('year', 'y'),
        ('month', 'mo'),
        ('day', 'd'),
        ('hour', 'h'),
        ('minute', 'm'),
        ('second', 's'),
    ]

    output = []
    for attr, brief_attr in attrs:
        elem = getattr(delta, attr + 's')
        if not elem:
            continue

        if attr == 'day':
            weeks = delta.weeks
            if weeks:
                elem -= weeks * 7
                if not brief:
                    output.append(format(plural(weeks), 'week'))
                else:
                    output.append(f'{weeks}w')

        if elem <= 0:
            continue

        if brief:
            output.append(f'{elem}{brief_attr}')
        else:
            output.append(format(plural(elem), attr))

    if accuracy is not None:
        output = output[:accuracy]

    if len(output) == 0:
        return 'now'
    else:
        if not brief:
            return human_join(output, final='and') + suffix
        else:
            return ' '.join(output) + suffix
