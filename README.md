# YouTube Music downloading tool

A small script to download music from youtube.
Support downloading single songs, playlists and channels with thumbnails

## Use cases

### Download single song:

```sh
$ python3 youtube_download_music.py -v "https://www.youtube.com/watch?v=xxx"
```

### Download all songs from playlist:

```sh
$ python3 youtube_download_music.py -l "https://www.youtube.com/watch?v=list=xxx"
```

### Download all songs from channel:

```sh
$ python3 youtube_download_music.py -l "https://www.youtube.com/channel/xxx"
```

#### Options `--help`

-   `--limit` - Limit number of sings to download
-   `--dry-run` - For testing purposes
-   `--timeout` - Socket read timeout in seconds
-   `--max-attempts` - Max download retries
-   `--verbose` - Verbose output
-   `--missing` - Download missing only
-   `--tags` - Update tags of exists files
-   `--order` - Songs order in channel: `newest`, `oldest`, `popular`
-   `--dir` - Download directory

## Installation

-   [ffmpeg-python](https://github.com/kkroening/ffmpeg-python?tab=readme-ov-file#installation)
-   `pip3 install -r requirements.txt`

## Thanks

-   [scrapetube](https://github.com/dermasmid/scrapetube)
-   [pytube](https://github.com/pytube/pytube)

### Known bugs

Fix: `pytube` cannot download: `get_throttling_function_name: could not find match for multiple`

-   append `r'\([a-z]\s*=\s*([a-zA-Z0-9$]+)(\[\d+\])\([a-z]\)',` to `function_patterns` in `cipher.py` at `264` line
