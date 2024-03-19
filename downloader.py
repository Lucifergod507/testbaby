from telethon.tl.custom.message import Message
from base64 import b64encode
import datetime as dt

import subprocess
import asyncio

import requests
import aiohttp

import shlex
import time
import os
import re

from helper import (
    sign_classplus_link,
    extract_file_path,
    convert_size,

    resolve_classplus_drm,
    resolve_vajiram_drm,
    resolve_afeias_drm,
    decrypt,

    datetime_stamp,
    get_secret,
    has_any
)
from logger import get_logger
from errors import StopWorkError
from user import User

from config import EDIT_INTERVAL
from config import VIDEOS_DIR

logger = get_logger(__name__)

async def get_rpc(session, secret, method: str, limit: bool = False) -> list:
    if limit:
        sub_params = f'["token:{secret}",0,1000000]'
    else:
        sub_params = f'["token:{secret}"]'
    params = {
        'jsonrpc': '2.0',
        'method' : method,
        'id'     : 'tgbot',
        'params' : b64encode(sub_params.encode()).decode()
    }
    logger.debug(f'Requesting rpc with method : {method} ...')
    async with session.get('http://localhost:6800/jsonrpc', params=params) as res:
        # print((await res.json())['result'])
        if res.status == 200:
           return (await res.json())['result']
    

async def fetch_progress(session, secret: str):
    results = []
    methods_info = (
        ('aria2.tellWaiting', True),
        ('aria2.tellActive', False),
        ('aria2.tellStopped', True)
    )
    for method, limit in methods_info:
        res = await get_rpc(session, secret, method, limit)
        results.append(res if res else [])
    return results


async def progress_tracker(user: User, secret: str, started_at: float, reply: Message, template: str, progress_updater: callable):
    ariad_started = False
    async with aiohttp.ClientSession() as session:
        while True:
            if not ariad_started:
                try:
                    logger.debug('Pinging ari2d ...')
                    requests.get('http://localhost:6800/jsonrpc')
                    ariad_started = True
                except requests.exceptions.ConnectionError:
                    await asyncio.sleep(0.5)
                    continue

            if user.stop_work:
                logger.debug('Shutting ariad ...')
                await reply.edit(template.format('Stopping ...'))
                await get_rpc(session, secret, 'aria2.shutdown')
                raise StopWorkError()

            now = time.time()
            if (now - user.last_edited_at) < EDIT_INTERVAL:
                continue
            logger.debug(f'Passed {EDIT_INTERVAL}s since last edit')

            queued_frags, active_frags, completed_frags = await fetch_progress(session, secret)

            if (not (active_frags and queued_frags)) and completed_frags:
                logger.debug('Fragment download completed')

                await reply.edit(template.format('Merging ...'))
                await asyncio.sleep(1)

                await get_rpc(session, secret, 'aria2.shutdown')
                return True

            queued_frags = [queued_frag for queued_frag in queued_frags if queued_frag not in active_frags + completed_frags]
            active_frags  = [active_frag for active_frag in active_frags if active_frag not in completed_frags]

            unique_frags = completed_frags + active_frags + queued_frags

            current_bytes = 0
            for completed_frag in completed_frags:
                current_bytes += int(completed_frag['totalLength'])

            active_frag_count = 0
            for active_frag in active_frags:

                completed_bytes = int(active_frag['completedLength'])
                total_bytes = int(active_frag['totalLength'])

                if total_bytes:
                    active_frag_count += completed_bytes / total_bytes
                current_bytes += completed_bytes

            completed_frags = len(completed_frags) + active_frag_count
            total_frags = len(unique_frags)

            if not total_frags:
                logger.debug('Total file size is 0 units')
                continue

            percent = (completed_frags / total_frags) * 100

            if not percent:
                logger.debug('Percent is 0 %')
                continue

            total_bytes = current_bytes * (100 / percent)
            speed = current_bytes / (now - started_at)

            if not speed:
                logger.debug('Speed is 0 units')
                continue

            eta = (total_bytes - current_bytes) / speed

            await progress_updater(
                reply,
                template,
                convert_size(current_bytes),
                convert_size(total_bytes),
                round(percent, 2),
                convert_size(speed),
                dt.timedelta(seconds=int(eta))
            )
            user.last_edited_at = time.time()



async def download(user: User, link, caption, resolution, reply: Message, template: str, progress_updater: callable):
    logger.debug(f'Download link : {link}')
    is_drm = False

    if 'cpvod.testbook.com' in link:
        logger.debug('Resolving classplus DRM ...')
        link, keys = await resolve_classplus_drm(link)
        logger.info(f'Manifest link : {link}')
        logger.info(f'keys : {keys}')
        is_drm = True


    elif 'vajiramias.com/api/course-secure-auth-otp' in link:
        logger.debug('Resolving vajiram DRM ...')
        link, keys = await resolve_vajiram_drm(link)
        logger.info(f'Manifest link : {link}')
        logger.info(f'keys : {keys}')
        is_drm = True


    elif 'api2.afeias.com/api/integration/vdocipher/otp' in link:
        logger.debug('Resolving afeias DRM ...')
        link, keys = await resolve_afeias_drm(link)
        logger.info(f'Manifest link : {link}')
        logger.info(f'keys : {keys}')
        is_drm = True

    elif 'classplusapp.com' in link:
        link = await sign_classplus_link(link)
        if not link:
            return False
        

    rpc_secret = get_secret()
    logger.debug(f'RPC secret : {rpc_secret}')
    file_name = os.path.join(VIDEOS_DIR, str(user.id), f'{caption[:30]}_{datetime_stamp()}'.replace(' ', '_'))

    if has_any(link, ('.mp4', '.pdf', 'drive.google.com')):
        cmd = (
            'yt-dlp',
            link,
            '--no-warnings',
            '--no-progress',
            '--downloader aria2c',
            f'--downloader-args aria2c:\'--enable-rpc --rpc-secret={rpc_secret}\'',
            f'-o \'{file_name}.%(ext)s\''
        )

    elif has_any(link, ('.m3u8', '.mpd', 'youtu', 'hydrator.vercel.app')):
        cmd = (
            'yt-dlp',
            "-f 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b'",
            f'-S res~{resolution},+size,+br' if resolution else '',
            link,
            '--allow-u',
            '--no-warnings',
            '--no-progress',
            '--merge-output-format mkv',
            '--downloader aria2c',
            f'--downloader-args aria2c:\'--enable-rpc --rpc-secret={rpc_secret}\'',
            f'-o \'{file_name}.%(ext)s\''
        )
    else:
        logger.debug('Link has unknown extension')
        return False

    started_at = time.time()
    stdout = ''

    logger.debug(f'Executing command : {" ".join(cmd)}')
    process = subprocess.Popen(shlex.split(' '.join(cmd)), stdout=subprocess.PIPE)
    exit_status = await progress_tracker(user, rpc_secret, started_at, reply, template, progress_updater)

    if is_drm:

        while True:
            stdout_line = process.stdout.readline().decode()
            stdout += stdout_line
            if  re.match('\[download\] Destination:.*\.m4a', stdout_line):
                break

            logger.debug('Waiting for track download to start ...')
            await asyncio.sleep(0.1)

        started_at = time.time()
        logger.debug('DRM Detected envoking progress tracker again ...')
        
        await reply.edit('Downloading track ...')
        exit_status = await progress_tracker(user, rpc_secret, started_at, reply, template, progress_updater)

    if exit_status:
        logger.debug('Waiting for process to terminate ...')
        process.wait()

        file_paths = extract_file_path(stdout if stdout else process.stdout.read().decode())
        if not is_drm:
            logger.debug('Not DRM. Choosing last file path ...')
            return file_paths[0]
        
        logger.debug('DRM detected. Requesting decryption ...')
        return await decrypt(file_paths, file_name, keys)

    logger.debug('Terminating process ...')
    process.terminate()
