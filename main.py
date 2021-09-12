#!/usr/bin/env python3

import logging
import os
from datetime import timedelta

from aiogram import Bot, Dispatcher, executor
from aiogram.types import ContentType, ContentTypes, ChatPermissions, Message

from Timer import Timer
from Types import PostType

bot = Bot(token=os.environ['API_TOKEN'])
dp = Dispatcher(bot)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

ADMIN_NICKNAMES = os.environ['ADMINS'].split(' ')
RESTRICT = ChatPermissions(False, False, False, False, False, False, False, False)
TIMEOUT = int(os.environ.get('TIMEOUT', 10))
DEBUG = int(os.environ.get('DEBUG', 1))

# TODO: use an appropriate storage
ids = {}


@dp.message_handler(commands='history')
async def start(message: Message):
    if is_user_regular(message):
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
        a_type == PostType.INVALID,
        a_type == PostType.NOT_RUSSIAN_VACANCY,
        a_type == PostType.NO_TAGS,
        a_type == PostType.OVERLAPPED_TAGS,
    ))


def get_hashtags(message: Message):
    return [message.text[m.offset:m.offset + m.length] for m in message.entities if m['type'] == 'hashtag']


async def is_user_regular(message: Message):
    admin_ids = [member.user.id for member in await bot.get_chat_administrators(message.chat.id)]
    return message.from_user.id not in admin_ids or message.from_user.username not in ADMIN_NICKNAMES


@dp.edited_message_handler()
async def edited_message(message: Message):
    if not await is_user_regular(message):
        return
    if message.message_id in ids:
        if not second_chance_failed(get_hashtags(message)):
            if ids[message.message_id]:
                await ids[message.message_id].delete()
            del ids[message.message_id]


@dp.message_handler(content_types=ContentTypes.ANY)
async def any_message(message: Message):
    if not await is_user_regular(message):
        return

    if message.content_type != ContentType.TEXT:
        await message.delete()
        return

    hashtags = get_hashtags(message)

    async def mark_for_edit():
        if await is_user_regular(message):
            if message.message_id in ids:
                await bot.restrict_chat_member(
                    chat_id=message.chat.id,
                    user_id=message.from_user.id,
                    permissions=RESTRICT,
                    until_date=timedelta(days=7),
                )
                await message.delete()
                if ids[message.message_id]:
                    await ids[message.message_id].delete()
                del ids[message.message_id]
        else:
            await message.reply('Hello, admin')

    if not len(hashtags):
        if '#' in message.text:
            answer = await message.answer('Поставьте пробелы между тэгами, например: #вакансия #android #ios')
            ids[message.message_id] = answer
            Timer(TIMEOUT, mark_for_edit)
            return
        else:
            await message.delete()
            return

    a_type = check_type(hashtags)
    if a_type == PostType.OVERLAPPED_TAGS:
        answer = await message.reply('Укажите один тип тэгов: #вакансия для вакансий, #ищу и #резюме для соискателей')
        ids[message.message_id] = answer
        Timer(TIMEOUT, mark_for_edit)
        return
    if a_type == PostType.INVALID:
        answer = await message.reply('Укажите тэги по правилам: либо тэг #вакансия, либо тэги #резюме #ищу')
        ids[message.message_id] = answer
        Timer(TIMEOUT, mark_for_edit)
        return
    if a_type == PostType.NOT_RUSSIAN_VACANCY:
        answer = await message.reply('Укажите тэг #вакансия на русском')
        ids[message.message_id] = answer
        Timer(TIMEOUT, mark_for_edit)
    a_type = check_recommendations(hashtags)
    if a_type == PostType.NOT_ENGLISH_PLATFORM:
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
        return PostType.NOT_ENGLISH_PLATFORM
    if no_english_ios and ios_not_english:
        return PostType.NOT_ENGLISH_PLATFORM
    else:
        return PostType.TAGS_OK


def check_type(hashtags):
    has_vacancy_tag = '#вакансия' in hashtags
    has_cv_tag = '#ищу' in hashtags or '#резюме' in hashtags

    not_russian_vacancy = ('#vacancy' in hashtags or '#вакансiя' in hashtags) and not has_vacancy_tag

    if has_cv_tag and has_vacancy_tag:
        return PostType.OVERLAPPED_TAGS
    if not_russian_vacancy:
        return PostType.NOT_RUSSIAN_VACANCY
    if has_cv_tag:
        return PostType.CV_OK
    if has_vacancy_tag:
        return PostType.VACANCY_OK
    else:
        return PostType.INVALID


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG if DEBUG else logging.INFO,
        format="[%(levelname)s] %(asctime)s: %(name)s - %(message)s",
    )
    if DEBUG:
        executor.start_polling(dp, skip_updates=True)
    else:
        port = int(os.environ.get('PORT', 3000))
        executor.start_webhook(dp, '/', port=port)
