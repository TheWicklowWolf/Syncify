![Build Status](https://github.com/TheWicklowWolf/Syncify/actions/workflows/main.yml/badge.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/thewicklowwolf/syncify.svg)

<p align="center">


![syncify_full_logo](https://github.com/TheWicklowWolf/Syncify/assets/111055425/e9b5e271-a7ef-4e9b-9a47-2436a6f06b44)


</p>

Web GUI for synchronising and fetching content from a Spotify playlist.


## Run using docker-compose

```yaml
version: "2.1"
services:
  syncify:
    image: thewicklowwolf/syncify:latest
    container_name: syncify
    volumes:
      - /config/syncify:/syncify/config
      - /data/media/syncify:/syncify/downloads
      - /etc/localtime:/etc/localtime:ro
    ports:
      - 5000:5000
    environment:
      - thread_limit=4
    restart: unless-stopped
```

---


![image](https://github.com/TheWicklowWolf/Syncify/assets/111055425/025365a6-095f-4110-9c28-4be2921d6f47)


---


![SyncifyDark](https://github.com/TheWicklowWolf/Syncify/assets/111055425/0ef9bb70-77c4-4da5-95b5-889839b63b84)


---


https://hub.docker.com/r/thewicklowwolf/syncify
