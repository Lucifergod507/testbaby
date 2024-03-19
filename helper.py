from telethon.tl.custom.message import Message
from datetime import datetime
import subprocess as sp
import datetime as dt
import aiohttp

import shlex
import time
import math

import re
import os

import secrets
import string

from errors import StopWorkError
from logger import get_logger
from user import User

from config import (
    EDIT_INTERVAL,
    THUMBS_DIR
)

logger = get_logger(__name__)

has_any = lambda box, items: any([item in box for item in items])
datetime_stamp = lambda :datetime.now().strftime('%Y%m%d%H%M%S')
get_secret = lambda :''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))


def convert_size(size_bytes):
   if size_bytes == 0:
       return '0B'
   size_name = ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return f'{s} {size_name[i]}'


async def sanitize(text: str) -> str:
    logger.debug(f'Sanitizing : {text}')
    chars = (
        ('  ', ' '), 
        (':' , '-'), 
        ('.' , '' ), 
        (',' , '' ),
        ('\'', '' ),
        ('"' , '' ),
        ('\\', '|'),
        ('/' , '|'),
        ('*' , '' ),
        ('#' , '' ),
        ('@' , '' ),
        ('||', '|'),
        ('{' , '('),
        ('}' , ')')
    )
    for old_char, new_char in chars:
        while text.find(old_char) != -1:
            text = text.replace(old_char, new_char)
    logger.debug(f'Sanitizer output : {text}')
    return text


async def validate_config(text: str, user: User):
    (download_range,
    resolution,
    course_name,
    credit_holder,
    thumb_id) = [field.strip() if field else field for field in (text.split('\n') + [None] * 4)[:5]]

    logger.info(f'Download range : {download_range}')
    logger.info(f'Resolution : {resolution}')
    logger.info(f'Course name : {course_name}')
    logger.info(f'Credit holder : {credit_holder}')
    logger.info(f'Thumb ID : {thumb_id}')

    start = stop = None
    valid_config = True

    pattern = '([0-9]{1,})(?:-([0-9]{1,}))?'
    match = re.match(pattern, download_range)

    if match:
        start, stop = [int(index) if index else 0 for index in match.groups()]
        if not (1 <= start <= stop and (start <= stop <= len(user.links)) if stop else True):
            valid_config = False
            logger.debug('Invalid download range')
    else:
        valid_config = False
        logger.debug('Invalid download range')

    if resolution:
        resolution = resolution.lower().strip('p')
        if not resolution.isdecimal():
            valid_config = False
            logger.debug('Invalid resolution')

    if thumb_id:
        if not all((
            thumb_id.isdecimal(),
            len(thumb_id) == 14,
            os.path.join(THUMBS_DIR, f'thumb_{thumb_id}.jpg'))):
            valid_config = False
            logger.debug('Invalid thumb ID')


    return valid_config, (
        (start, stop),
        resolution,
        course_name,
        credit_holder,
        thumb_id
    )


async def progress_bar(current, total, user: User, reply, template, progress_updater: callable, started_at: float):
    if user.stop_work:
        logger.debug('User has stopped work')
        await reply.edit(template.format('Stopping ...'))
        raise StopWorkError()

    now = time.time()
    if (now - user.last_edited_at) < EDIT_INTERVAL:
        return
    logger.debug(f'Passed {EDIT_INTERVAL}s since last edit')
    
    if not total:
        logger.debug('Total file size is 0 units')
        return
    
    percent = (current / total) * 100
    speed = current / (now - started_at)

    if not speed:
        logger.debug('Speed is 0 units')
        return

    eta = (total - current) / speed

    await progress_updater(
        reply,
        template,
        convert_size(current),
        convert_size(total),
        round(percent, 2),
        convert_size(speed),
        dt.timedelta(seconds=int(eta)),
    )
    user.last_edited_at = time.time()
    

async def progress_updater(reply: Message, template: str, *stats):
    stats = template.format(
        f'Progress : {stats[2]}%\n'
        f'Done : {stats[0]}\n'
        f'Total : {stats[1]}\n'
        f'Speed : {stats[3]}/s\n'
        f'ETA : {stats[4]} sec\n'
    )
    if reply.text == stats:
        logger.debug('Same stats, Not updating ...')
        return
    
    await reply.edit(stats)
    logger.debug('Stats updated')


async def get_thumb(file_path):
    thumb_path = os.path.join(THUMBS_DIR, f'thumb_{datetime_stamp()}.jpg')
    process = sp.run(
        ['ffmpeg', '-i', file_path, '-ss', '10', '-vframes', '1', thumb_path],
        stderr=sp.DEVNULL,
        stdout=sp.DEVNULL
    )
    try:
        process.check_returncode()
        return thumb_path
    except sp.CalledProcessError:
        logger.error('Failed to get thumb')
        return None
    

def get_duration(video):
    logger.debug('Getting video length ...')
    process = sp.run(
        shlex.split(
        f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 '{video}'"),
        stdout=sp.PIPE,
        stderr=sp.STDOUT
    )
    return int(float(process.stdout))


async def sign_classplus_link(link):

    headers = {
        'Host'           : 'api.classplusapp.com',
        'x-access-token' : 'eyJhbGciOiJIUzM4NCIsInR5cCI6IkpXVCJ9.eyJpZCI6MzgzNjkyMTIsIm9yZ0lkIjoyNjA1LCJ0eXBlIjoxLCJtb2JpbGUiOiI5MTcwODI3NzQyODkiLCJuYW1lIjoiQWNlIiwiZW1haWwiOm51bGwsImlzRmlyc3RMb2dpbiI6dHJ1ZSwiZGVmYXVsdExhbmd1YWdlIjpudWxsLCJjb3VudHJ5Q29kZSI6IklOIiwiaXNJbnRlcm5hdGlvbmFsIjowLCJpYXQiOjE2NDMyODE4NzcsImV4cCI6MTY0Mzg4NjY3N30.hM33P2ai6ivdzxPPfm01LAd4JWv-vnrSxGXqvCirCSpUfhhofpeqyeHPxtstXwe0',
        'user-agent'     : 'Mobile-Android',
        'app-version'    : '1.4.39.5',
        'api-version'    : '20',
        'device-id'      : '5d0d17ac8b3c9f51',
        'device-details' : '2848b866799971ca_2848b8667a33216c_SDK-30',
        'region'         : 'IN',
        'accept-encoding': 'gzip'
    }

    params = {'url': link}
    logger.debug(f'Signing classplus link : {link}')

    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.classplusapp.com/cams/uploader/video/jw-signed-url', headers=headers, params=params) as response:
            
            if response.status == 200:
                return (await response.json())['url']
            

def extract_file_path(output: str):
    logger.debug(output)
    logger.debug('Extracting file path from yt-dlp stdout ...')

    pattern = '((?<=\[download\]\s).*(?=\shas\salready\sbeen\sdownloaded)|(?<=\[Merger\]\sMerging\sformats\sinto\s").*(?=")|(?<=\[download\]\sDestination:\s).*)'
    match = re.findall(pattern, '\n'.join(output.split('\n')[::-1]))
    logger.debug(f'Output file path count : {len(match)}')
    return match


async def resolve_classplus_drm(link):

    logger.debug(f'Getting manifest link and keys ... : {link}')
    json_data = {'url': link}

    async with aiohttp.ClientSession() as session:
        async with session.post('https://getwvkeys.up.railway.app/api/cp', json=json_data) as response:
            
            response.raise_for_status()
            res_data = await response.json()
            logger.debug(res_data)
            return res_data['manifestUrl'], res_data['keys']
        

async def resolve_vajiram_drm(link):

    logger.debug(f'Getting manifest link and keys ... : {link}')
    json_data = {'url': link}

    async with aiohttp.ClientSession() as session:
        async with session.post('https://getwvkeys.up.railway.app/api/vr', json=json_data) as response:
            
            response.raise_for_status()
            res_data = await response.json()
            logger.debug(res_data)
            return res_data['manifestUrl'], res_data['keys']
        

async def resolve_afeias_drm(link):

    logger.debug(f'Getting manifest link and keys ... : {link}')
    json_data = {'url': link}

    async with aiohttp.ClientSession() as session:
        async with session.post('https://getwvkeys.up.railway.app/api/af', json=json_data) as response:
            
            response.raise_for_status()
            res_data = await response.json()
            logger.debug(res_data)
            return res_data['manifestUrl'], res_data['keys']
        

async def merge(dec_file_paths, file_name):
    logger.debug('Merging ...')
    file_path = f'{file_name}.mp4'
    cmd = (
        'ffmpeg',
        ' '.join([f'-i {dec_file_path}' for dec_file_path in dec_file_paths]),
        '-c copy',
        file_path
    )
    logger.debug(' '.join(cmd))
    sp.run(
        shlex.split(' '.join(cmd)),
        stderr=sp.DEVNULL,
        stdout=sp.DEVNULL
    )
    for dec_file_path in dec_file_paths:
        os.remove(dec_file_path)

    logger.debug(f'Merged to : {file_path}')
    return file_path


async def decrypt(enc_file_paths, file_name, keys):
    dec_file_paths = []
    for enc_file_path in enc_file_paths:

        logger.debug(f'Trying to decrypt ... : {enc_file_path}')
        enc_file_name, ext = os.path.splitext(enc_file_path)
        dec_file_path = f'{enc_file_name}_dec{ext}'

        cmd = (
            './bin/mp4decrypt',
            ' '.join([f'--key {k}:{v}' for k, v in keys.items()]),
            enc_file_path,
            dec_file_path
        )
        logger.debug(' '.join(cmd))
        sp.run(shlex.split(' '.join(cmd)))

        os.remove(enc_file_path)
        dec_file_paths.append(dec_file_path)
        logger.debug(f'Decryted to : {dec_file_path}')

    return await merge(dec_file_paths, file_name)