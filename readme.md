![Build Status](https://github.com/TheWicklowWolf/Syncify/actions/workflows/main.yml/badge.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/thewicklowwolf/syncify.svg)


<img src="https://raw.githubusercontent.com/TheWicklowWolf/Syncify/main/src/static/syncify_full_logo.png" alt="logo">


Syncify is a tool for synchronising and fetching content from Spotify or YouTube playlists via yt-dlp.


## Run using docker-compose

```yaml
services:
  syncify:
    image: thewicklowwolf/syncify:latest
    container_name: syncify
    volumes:
      - /path/to/config:/syncify/config
      - /data/media/syncify:/syncify/downloads
      - /etc/localtime:/etc/localtime:ro
    ports:
      - 5000:5000
    environment:
      - thread_limit=1
      - crop_album_art=false
    restart: unless-stopped
```


## Configuration via environment variables

Certain values can be set via environment variables:

* __thread_limit__: Max number of threads to use. Defaults to `1`.
* __crop_album_art__: Set this to `true` to force the creation of square album art instead of using the 16:9 aspect ratio from YouTube. Defaults to `false`.


## Sync Schedule

Use a comma-separated list of hours to search for new tracks (e.g. `2, 20` will initiate a search at 2 AM and 8 PM).
> Note: There is a deadband of up to 10 minutes from the scheduled start time.


## Cookies (optional)
To utilize a cookies file with yt-dlp, follow these steps:

* Generate Cookies File: Open your web browser and use a suitable extension (e.g. cookies.txt for Firefox) to extract cookies for a user on YT.

* Save Cookies File: Save the obtained cookies into a file named `cookies.txt` and put it into the config folder.


---

![image](https://github.com/TheWicklowWolf/Syncify/assets/111055425/025365a6-095f-4110-9c28-4be2921d6f47)

---

![SyncifyDark](https://github.com/TheWicklowWolf/Syncify/assets/111055425/0ef9bb70-77c4-4da5-95b5-889839b63b84)

---


https://hub.docker.com/r/thewicklowwolf/syncify
