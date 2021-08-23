#!/usr/bin/env python3

import os
import logging
from datetime import timedelta

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ContentType, ContentTypes

from Timer import Timer
from parser import Type

bot = Bot(token=os.environ['API_TOKEN'])
dp = Dispatcher(bot)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

ADMIN_NICKNAMES = os.environ['ADMINS'].split(' ')
RESTRICT = types.ChatPermissions(False, False, False, False, False, False, False, False)
TIMEOUT = os.environ.get('TIMEOUT', 15 * 60)

ids = []


@dp.message_handler(commands='history')
async def start(message: types.Message):
    if message.from_user.username not in ADMIN_NICKNAMES:
        await message.reply('Эта команда только для админов')
        return
    if not message.text:
        await message.reply('Введите ник')
        return
    if '@' not in message.text:
        await message.reply('Введите ник')
        return
    await message.reply(f'{message.text} ух чё натворил')


def second_chance_failed(hashtags):
    a_type = check_type(hashtags)
    return any((
        a_type == Type.INVALID,
        a_type == Type.NOT_RUSSIAN_VACANCY,
        a_type == Type.NO_TAGS,
        a_type == Type.OVERLAPPED_TAGS,
    ))


def get_hashtags(message: types.Message):
    return [message.text[m.offset:m.offset + m.length] for m in message.entities if m['type'] == 'hashtag']


@dp.edited_message_handler()
async def edited_message(message: types.Message):
    if message.message_id in ids:
        if not second_chance_failed(get_hashtags(message)):
            ids.remove(message.message_id)


@dp.message_handler(content_types=ContentTypes.ANY)
async def any_message(message: types.Message):
    admin_ids = [member.user.id for member in await bot.get_chat_administrators(message.chat.id)]
    regular_user = message.from_user.id not in admin_ids or message.from_user.username not in ADMIN_NICKNAMES

    if regular_user and message.content_type != ContentType.TEXT:
        await message.delete()
        return

    hashtags = get_hashtags(message)

    async def mark_for_edit():
        if regular_user:
            if message.message_id in ids:
                await bot.restrict_chat_member(
                    chat_id=message.chat.id,
                    user_id=message.from_user.id,
                    permissions=RESTRICT,
                    until_date=timedelta(days=7),
                )
                await message.delete()
                ids.remove(message.message_id)
        else:
            await message.reply('Hello, admin')

    if not len(hashtags):
        if regular_user:
            if '#' in message.text:
                await message.answer('Поставьте пробелы между тэгами, например: #вакансия #android #ios')
                ids.append(message.message_id)
                Timer(TIMEOUT, mark_for_edit)
            else:
                await message.delete()
        return

    a_type = check_type(hashtags)
    if a_type == Type.OVERLAPPED_TAGS:
        await message.reply('Укажите один тип тэгов: #вакансия для вакансий, #ищу и #резюме для соискателей')
        ids.append(message.message_id)
        Timer(TIMEOUT, mark_for_edit)
        return
    if a_type == Type.INVALID:
        await message.reply('Укажите тэги по правилам')
        ids.append(message.message_id)
        Timer(TIMEOUT, mark_for_edit)
        return
    if a_type == Type.NOT_RUSSIAN_VACANCY:
        await message.reply('Укажите тэг #вакансия на русском')
        ids.append(message.message_id)
        Timer(TIMEOUT, mark_for_edit)
    a_type = check_recommendations(hashtags)
    if a_type == Type.NOT_ENGLISH_PLATFORM:
        await message.reply('Для лучшего поиска добавьте тэг платформы на английском: #android, #ios')


def check_recommendations(hashtags):
    android_not_english = any((
        '#андройд' in hashtags,
        '#андроид' in hashtags,
        '#андроед' in hashtags,
        '#андроїд' in hashtags,
        '#андроiд' in hashtags,
    ))
    ios_not_english = any((
        '#иос' in hashtags,
        '#айос' in hashtags,
        '#айось' in hashtags,
    ))
    no_english_android = '#android' not in hashtags
    no_english_ios = '#ios' not in hashtags
    if no_english_android and android_not_english:
        return Type.NOT_ENGLISH_PLATFORM
    if no_english_ios and ios_not_english:
        return Type.NOT_ENGLISH_PLATFORM
    else:
        return Type.TAGS_OK


def check_type(hashtags):
    has_vacancy_tag = '#вакансия' in hashtags
    has_cv_tag = '#ищу' in hashtags or '#резюме' in hashtags

    not_russian_vacancy = ('#vacancy' in hashtags or '#вакансiя' in hashtags) and not has_vacancy_tag

    if has_cv_tag and has_vacancy_tag:
        return Type.OVERLAPPED_TAGS
    if not_russian_vacancy:
        return Type.NOT_RUSSIAN_VACANCY
    if has_cv_tag:
        return Type.CV_OK
    if has_vacancy_tag:
        return Type.VACANCY_OK
    else:
        return Type.INVALID


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
