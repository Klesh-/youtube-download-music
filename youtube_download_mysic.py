#!/usr/bin/env python3.10

import ffmpeg  
import os, errno
import scrapetube
import music_tag
import requests
import re
import io
import math

from pytube import YouTube
from argparse import ArgumentParser
from urllib import parse
from colorama import init as colorama_init
from colorama import Fore
from PIL import Image


colorama_init()

dry_run = False
limit = None
errors = {}
missing_only = False
tags_update = False
verbose = False
max_attempts = 5
timeout_sec = 120
download_folder = None
bad_symbols = '[^a-zA-Z0-9\s\-+_=()\[\]&^%$#@!]'
thumbnail_size = 512

def log_info(*values: object):
    print(f"{Fore.GREEN}[INFO]{Fore.RESET} ", end="")
    print(*values)

def log_warn(*values: object):
    print(f"{Fore.YELLOW}[WARN] ", end="")
    print(*values)
    print(Fore.RESET, end="")

def log_err(*values: object):
    print(f"{Fore.RED}[ERR] ", end="")
    print(*values)
    print(Fore.RESET, end="")

def record_error(video, e): 
    log_err(f"Cannot download video: {video}", e)
    errors[str(video)] = e
        
def dump_errors(): 
    if len(errors.keys()) > 0:
        log_warn(f"\nSome videos were not downloaded:")
        for vid, err in errors.items():
            log_warn(f'{vid}: {err}')


def is_limit_reached(count: int):
    if limit is not None and count >= limit:
        log_warn(f"Limit reached {limit}")
        return True
    return False

def silent_remove_file(filename: str):
    try:
        os.remove(filename)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise
        
def duration_str(seconds):
    t = ""
    h = math.floor(seconds / 3600)
    if h > 0:
        t += str(h).rjust(2,'0') + ':'
    
    m = str(math.floor((seconds % 3600) / 60)).rjust(2, '0')
    s = str(seconds % 60).rjust(2, '0')
    t += f'{m}:{s}'    
    return t;
        
def generate_square_thumbnail(url: str, size: int = thumbnail_size) :
    log_info(f"Generating song thumbnail: {url}", size)

    if dry_run:
        return
    
    img = Image.open(io.BytesIO(requests.get(url, stream=True).content))
    img.thumbnail((size, size))

    width, height = img.size
    if width > height:
        left = (width - height) / 2
        right = (width + height) / 2
        top = 0
        bottom = height
    else:
        left = 0
        right = width
        top = (height - width) / 2
        bottom = (height + width) / 2
    
    img = img.crop((left, top, right, bottom))

    bytes = io.BytesIO()
    img.save(bytes, format='PNG')
    return bytes.getvalue()

def ffmpreg_trim_audio(input_file: str, output_file: str, seconds: int):
    log_info(f"Trimming audio {input_file}")
    
    if dry_run:
        return
    
    audio_input = ffmpeg.input(input_file)
    audio_cut = audio_input.audio.filter('atrim', duration=seconds)
    audio_output = ffmpeg.output(audio_cut, output_file)
    
    quiet = verbose == False
    ffmpeg.run(audio_output, quiet=quiet)

def set_media_tags(yt: YouTube, file: str):
    log_info(f"Updating music tags: {file}")
    
    if dry_run:
        return
    
    try:
        tags = music_tag.load_file(file)
        tags['title'] = yt.title
        tags['artist'] = yt.author
        tags['artwork'] = generate_square_thumbnail(yt.thumbnail_url)
        tags.save()
    except Exception as e:
        log_warn(f"Cannot set music tags: {e}")

def download_audio_stream_with_attempts(yt: YouTube, download_file: str, output_file: str):
    log_info(f"Downloading video: {yt.title}")
    
    if dry_run:
        return
    
    try:
        attempt = 0
        while True:
            try:
                yt.streams.filter(only_audio=True) \
                    .filter(mime_type="audio/mp4").order_by("abr").desc().first() \
                    .download(filename=download_file, max_retries=max_attempts,timeout=timeout_sec)
                break
            except Exception as e:
                attempt += 1
                if attempt < max_attempts:
                    log_warn(f"Trying again: {e}")
                else:
                    raise
                
        ffmpreg_trim_audio(download_file, output_file, yt.length)
    finally:
        silent_remove_file(download_file)
            
def parse_video_link(url: str) -> YouTube:  
    if url.startswith('https'):
        return YouTube(url)
    else:
        return YouTube.from_id(url) 

def download_video_audio(video_url: str, folder='.'):
    yt = parse_video_link(video_url)
        
    vid_name = yt.title
    if yt.author.lower() not in yt.title.lower():
        vid_name = f'{yt.author} - {yt.title}'
    
    output_file = os.path.join(folder, f"{yt.video_id}.m4a")
    
    log_info("")
    log_info(f"Video: {vid_name} | {duration_str(yt.length)}")
    log_info(f" > {yt.watch_url}")
        
    final_file = os.path.join(folder, f"{re.sub(bad_symbols, '-', vid_name)}.m4a")
        
    if not os.path.exists(folder) and not dry_run:
        os.makedirs(folder, exist_ok=True)
        
    if os.path.exists(final_file):
        if tags_update and missing_only:
            set_media_tags(yt, final_file)
        if missing_only:
            log_info(f"Already downloaded")
            return
        
    download_file = os.path.join(folder, f"{yt.video_id}.download.mp4")
    download_audio_stream_with_attempts(yt, download_file, output_file)
    set_media_tags(yt, output_file)
    os.rename(output_file, final_file)

def download_all_videos_in_channel(channel_url: str):
    log_info(f"Downloading all videos of channel: {channel_url}")

    if channel_url.startswith("https"):
        url = parse.urlsplit(channel_url)
        channel_id = url.path.split('/')[-1]
    else:
        channel_id = channel_url
        
    log_info(f"ChannelId: {channel_id}")
   
    done = 0
    folder = download_folder or channel_id
    
    for video in scrapetube.get_channel(channel_id):
        video_id = str(video['videoId'])
        try:  
            download_video_audio(video_id, folder)
        except Exception as e:
            record_error(video_id, e)
            
        done += 1
        if is_limit_reached(done):
            return

def download_all_videos_in_playlist(playlist_url: str):
    log_info(f"Downloading all videos of playlist: {playlist_url}")

    if playlist_url.startswith("https"):
        params = dict(parse.parse_qsl(parse.urlsplit(playlist_url).query))
        list_id = params['list']
    else:
        list_id = playlist_url
    
    log_info(f"ListId: {list_id}")
   
    done = 0
    folder = download_folder or list_id
    
    for video in scrapetube.get_playlist(list_id):
        video_id = str(video['videoId'])
        try:
            download_video_audio(video_id, folder)
        except Exception as e:
            record_error(video_id, e)

        done =+ 1
        if is_limit_reached(done):
            return

def download_all_videos_in_list(list: list[str]):
    log_info(f"Downloading {len(list)} videos")

    done = 0
    folder = download_folder or "."

    for vid in list:
        try:
            download_video_audio(vid, folder)  
        except Exception as e:
            record_error(vid, e)
        
        done =+ 1
        if is_limit_reached(done):
            return


parser = ArgumentParser()
parser.add_argument("-d", "--dry-run", help="Dry run", action="store_true")
parser.add_argument("-m", "--limit", help="Max songs", type=int, default=None)
parser.add_argument("-t", "--timeout", help="Socket read timeout in seconds", type=int, default=timeout_sec)
parser.add_argument("-r", "--max-attempts", help="Max download retries", type=int, default=max_attempts)
parser.add_argument("--verbose", help="Verbose output", action="store_true")
parser.add_argument("--missing", help="Download missing only", action="store_true")
parser.add_argument("--tags", help="Update tags of exists files", action="store_true")
parser.add_argument("--dir", help="Download directory", default=None)

group = parser.add_mutually_exclusive_group()
group.add_argument("-v", "--videos", nargs="+", help="YouTube video URLs | Ids")
group.add_argument("-l", "--playlist", help="YouTube playlist URL | Id")
group.add_argument("-c", "--channel", help="YouTube channel URL | Id")

args = parser.parse_args()

dry_run = args.dry_run
limit = args.limit
verbose = args.verbose
missing_only = args.missing
tags_update = args.tags
max_attempts = args.max_attempts
timeout_sec = args.timeout
download_folder = args.dir

if args.channel:
    download_all_videos_in_channel(args.channel)
elif args.playlist:
    download_all_videos_in_playlist(args.playlist)
elif args.videos:
    download_all_videos_in_list(args.videos)
else:
    parser.error('No action requested')

dump_errors()
