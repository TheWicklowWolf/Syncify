![Build Status](https://github.com/TheWicklowWolf/Syncify/actions/workflows/main.yml/badge.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/thewicklowwolf/syncify.svg)


<img src="https://raw.githubusercontent.com/TheWicklowWolf/Syncify/main/src/static/syncify_full_logo.png" alt="logo">


Syncify is a tool for synchronising and fetching content from a Spotify playlist via yt-dlp.


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
    restart: unless-stopped
```


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
