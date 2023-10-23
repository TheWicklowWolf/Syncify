![Build Status](https://github.com/TheWicklowWolf/Syncify/actions/workflows/main.yml/badge.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/thewicklowwolf/syncify.svg)

<p align="center">

![full_logo](https://github.com/TheWicklowWolf/Syncify/assets/111055425/c07c2794-d537-407e-9f5b-83098244f6c7)



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
      - /data/media/syncify:/syncify/download
      - /etc/localtime:/etc/localtime:ro
    ports:
      - 5000:5000
    environment:
      - thread_limit=4
    restart: unless-stopped
```

---

<p align="center">





</p>


https://hub.docker.com/r/thewicklowwolf/syncify
