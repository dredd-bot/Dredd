"""Dredd, discord bot
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


class flag_value:
    def __init__(self, func):
        self.flag = func(None)
        self.__doc__ = func.__doc__

    def __get__(self, instance, owner):
        return instance._has_flag(self.flag)


class UserFlags:
    def __init__(self, value: int = 0):
        self.value = value

    def __repr__(self):
        return '<%s value=%s>' % (self.__class__.__name__, self.value)

    def __iter__(self):
        for name, value in self.__class__.__dict__.items():
            if isinstance(value, flag_value) and self._has_flag(value.flag):
                yield name

    def _has_flag(self, o):
        return (self.value & o) == o

    @flag_value
    def discord_employee(self):
        return 1 << 0

    @flag_value
    def discord_partner(self):
        return 1 << 1

    @flag_value
    def hs_events(self):
        return 1 << 2

    @flag_value
    def bug_hunter_lvl1(self):
        return 1 << 3

    @flag_value
    def mfa_sms(self):
        return 1 << 4

    @flag_value
    def premium_promo_dismissed(self):
        return 1 << 5

    @flag_value
    def hs_bravery(self):
        return 1 << 6

    @flag_value
    def hs_brilliance(self):
        return 1 << 7

    @flag_value
    def hs_balance(self):
        return 1 << 8

    @flag_value
    def early_supporter(self):
        return 1 << 9

    @flag_value
    def team_user(self):
        return 1 << 10

    @flag_value
    def system(self):
        return 1 << 12

    @flag_value
    def unread_sys_msg(self):
        return 1 << 13

    @flag_value
    def bug_hunter_lvl2(self):
        return 1 << 14

    @flag_value
    def underage_deleted(self):
        return 1 << 15

    @flag_value
    def verified_bot(self):
        return 1 << 16

    @flag_value
    def verified_dev(self):
        return 1 << 17

    @flag_value
    def certified_mod(self):
        return 1 << 18


class BotFlags:
    def __init__(self, value: int = 0):
        self.value = value

    def __repr__(self):
        return '<%s value=%s>' % (self.__class__.__name__, self.value)

    def __iter__(self):
        for name, value in self.__class__.__dict__.items():
            if isinstance(value, flag_value) and self._has_flag(value.flag):
                yield name

    def _has_flag(self, o):
        return (self.value & o) == o

    @flag_value
    def bot_owner(self):
        return 1 << 0

    @flag_value
    def bot_admin(self):
        return 1 << 1

    @flag_value
    def bot_partner(self):
        return 1 << 2

    @flag_value
    def server_partner(self):
        return 1 << 3

    @flag_value
    def bug_hunter_lvl1(self):
        return 1 << 4

    @flag_value
    def bug_hunter_lvl2(self):
        return 1 << 5

    @flag_value
    def verified(self):
        return 1 << 6

    @flag_value
    def sponsor(self):
        return 1 << 7

    @flag_value
    def donator(self):
        return 1 << 8

    @flag_value
    def early(self):
        return 1 << 9

    @flag_value
    def early_supporter(self):
        return 1 << 10

    @flag_value
    def blocked(self):
        return 1 << 11

    @flag_value
    def duck(self):
        return 1 << 12

    @flag_value
    def translator(self):
        return 1 << 13
