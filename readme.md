![Build Status](https://github.com/TheWicklowWolf/Syncify/actions/workflows/main.yml/badge.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/thewicklowwolf/syncify.svg)

<p align="center">


![syncify_full_logo](https://github.com/TheWicklowWolf/Syncify/assets/111055425/f7c21dc6-a62f-4806-a7e7-b17441aa9fab)


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
      - 5000:5000![syncify_full_logo](https://github.com/TheWicklowWolf/Syncify/assets/111055425/20291a15-877d-4638-bf58-1a3e5d000f1d)

    environment:
      - thread_limit=4
    restart: unless-stopped
```

---

<p align="center">


![image](https://github.com/TheWicklowWolf/Syncify/assets/111055425/ba044b1f-7438-4bbf-adc3-b8e530515c82)


</p>


https://hub.docker.com/r/thewicklowwolf/syncify
