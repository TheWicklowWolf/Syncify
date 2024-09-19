import re
import os
import sys
import json
import time
import logging
import datetime
import threading
import concurrent.futures
from urllib.parse import urlparse, parse_qs
from flask import Flask, render_template
from flask_socketio import SocketIO
from ytmusicapi import YTMusic
import yt_dlp
from plexapi.server import PlexServer
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import requests
from thefuzz import fuzz


class DataHandler:
    YOUTUBE_LINK_PREFIX = "https://www.youtube.com/watch?v="

    def __init__(self):
        logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s", datefmt="%d/%m/%Y %H:%M:%S", handlers=[logging.StreamHandler(sys.stdout)])
        self.logger = logging.getLogger()

        app_name_text = os.path.basename(__file__).replace(".py", "")
        release_version = os.environ.get("RELEASE_VERSION", "unknown")
        self.logger.warning(f"{'*' * 50}\n")
        self.logger.warning(f"{app_name_text} Version: {release_version}\n")
        self.logger.warning(f"{'*' * 50}")

        self.config_folder = "config"
        self.download_folder = "downloads"
        self.media_server_addresses = "Plex: http://192.168.1.2:32400, Jellyfin: http://192.168.1.2:8096"
        self.media_server_tokens = "Plex: abc, Jellyfin: xyz"
        self.media_server_library_name = "Music"
        self.spotify_client_id = ""
        self.spotify_client_secret = ""
        self.thread_limit = int(os.environ.get("thread_limit", 1))
        self.media_server_scan_req_flag = False
        self.crop_album_art = os.getenv("crop_album_art", "false").lower()

        if not os.path.exists(self.config_folder):
            os.makedirs(self.config_folder)
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)

        self.sync_start_times = [0]
        self.settings_config_file = os.path.join(self.config_folder, "settings_config.json")

        self.sync_list = []
        self.sync_list_config_file = os.path.join(self.config_folder, "sync_list.json")

        if os.path.exists(self.settings_config_file):
            self.load_from_file()

        if os.path.exists(self.sync_list_config_file):
            self.load_sync_list_from_file()

        full_cookies_path = os.path.join(self.config_folder, "cookies.txt")
        self.cookies_path = full_cookies_path if os.path.exists(full_cookies_path) else None
        self.sync_in_progress_flag = False

        task_thread = threading.Thread(target=self.schedule_checker)
        task_thread.daemon = True
        task_thread.start()

    def load_from_file(self):
        try:
            with open(self.settings_config_file, "r") as json_file:
                ret = json.load(json_file)
            self.sync_start_times = ret["sync_start_times"]
            self.media_server_addresses = ret["media_server_addresses"]
            self.media_server_tokens = ret["media_server_tokens"]
            self.media_server_library_name = ret["media_server_library_name"]
            self.spotify_client_id = ret["spotify_client_id"]
            self.spotify_client_secret = ret["spotify_client_secret"]

        except Exception as e:
            self.logger.error(f"Error Loading Config: {str(e)}")

    def save_to_file(self):
        try:
            with open(self.settings_config_file, "w") as json_file:
                json.dump(
                    {
                        "sync_start_times": self.sync_start_times,
                        "media_server_addresses": self.media_server_addresses,
                        "media_server_tokens": self.media_server_tokens,
                        "media_server_library_name": self.media_server_library_name,
                        "spotify_client_id": self.spotify_client_id,
                        "spotify_client_secret": self.spotify_client_secret,
                    },
                    json_file,
                    indent=4,
                )

        except Exception as e:
            self.logger.error(f"Error Saving Config: {str(e)}")

    def load_sync_list_from_file(self):
        try:
            with open(self.sync_list_config_file, "r") as json_file:
                self.sync_list = json.load(json_file)

        except Exception as e:
            self.logger.error(f"Error Loading Playlists: {str(e)}")

    def save_sync_list_to_file(self):
        try:
            with open(self.sync_list_config_file, "w") as json_file:
                json.dump(self.sync_list, json_file, indent=4)

        except Exception as e:
            self.logger.error(f"Error Saving Playlists: {str(e)}")

    def schedule_checker(self):
        self.logger.warning("Starting periodic checks every 10 minutes to monitor sync start times.")
        self.logger.warning(f"Current scheduled hours to start sync (in 24-hour format): {self.sync_start_times}")

        while True:
            current_time = datetime.datetime.now().time()
            within_sync_window = any(datetime.time(t, 0, 0) <= current_time <= datetime.time(t, 59, 59) for t in self.sync_start_times)

            if within_sync_window and self.sync_in_progress_flag:
                self.logger.warning(f"Sync already in progress")
                time.sleep(600)

            elif within_sync_window and not self.sync_in_progress_flag:
                self.logger.warning(f"Time to Start Sync - as in a time window {self.sync_start_times}")
                self.master_queue()
                self.logger.warning("Big sleep for 1 Hour - Sync Done")
                time.sleep(3600)
                self.logger.warning(f"Checking every 10 minutes as not in sync time window {self.sync_start_times}")

            else:
                time.sleep(600)

    def spotify_extractor(self, link):
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=self.spotify_client_id, client_secret=self.spotify_client_secret))
        track_list = []

        if "album" in link:
            album_info = sp.album(link)
            album_name = album_info["name"]
            album = sp.album_tracks(link)
            for item in album["items"]:
                try:
                    track_title = item["name"]
                    artists = [artist["name"] for artist in item["artists"]]
                    artists_str = ", ".join(artists)
                    track_list.append({"Artist": artists_str, "Title": track_title, "Status": "Queued", "Folder": album_name})

                except Exception as e:
                    self.logger.error(f"Error Parsing Item in Album: {str(item)} - {str(e)}")

        else:
            playlist = sp.playlist(link)
            playlist_name = playlist["name"]
            number_of_tracks = playlist["tracks"]["total"]
            fields = "items(track(name,artists(name)),added_at)"

            offset = 0
            limit = 100
            all_items = []
            while offset < number_of_tracks:
                results = sp.playlist_items(link, fields=fields, limit=limit, offset=offset)
                all_items.extend(results["items"])
                offset += limit

            all_items_sorted = sorted(all_items, key=lambda x: x["added_at"], reverse=False)
            for item in all_items_sorted:
                try:
                    track = item["track"]
                    track_title = track["name"]
                    artists = [artist["name"] for artist in track["artists"]]
                    artists_str = ", ".join(artists)
                    track_list.append({"Artist": artists_str, "Title": track_title, "Status": "Queued", "Folder": playlist_name})

                except Exception as e:
                    self.logger.error(f"Error Parsing Item in Playlist: {str(item)} - {str(e)}")

        return track_list

    def youtube_extractor(self, link):
        self.ytmusic = YTMusic()
        track_list = []
        playlist_id = parse_qs(urlparse(link).query).get("list", [None])[0]
        if playlist_id:
            playlist = self.ytmusic.get_playlist(playlist_id)
            playlist_name = playlist["title"]

            for track in playlist["tracks"]:
                track_title = track["title"]
                artist_str = ", ".join([a["name"] for a in track["artists"]])
                track_list.append({"Artist": artist_str, "Title": track_title, "Status": "Queued", "Folder": playlist_name, "VideoID": track["videoId"]})
        else:
            self.logger.error("Unsupported youtube playlist url! It must have a list=<playlist_id> query params.")

        return track_list

    def find_youtube_link(self, artist, title):
        try:
            first_result = None

            self.ytmusic = YTMusic()
            search_results = self.ytmusic.search(query=f"{artist} - {title}", filter="songs", limit=5)

            cleaned_artist = self.string_cleaner(artist).lower()
            cleaned_title = self.string_cleaner(title).lower()
            for item in search_results:
                cleaned_youtube_title = self.string_cleaner(item["title"]).lower()
                if cleaned_title in cleaned_youtube_title:
                    first_result = self.YOUTUBE_LINK_PREFIX + item["videoId"]
                    break
            else:
                # Try again but check for a partial match
                for item in search_results:
                    cleaned_youtube_title = self.string_cleaner(item["title"]).lower()
                    cleaned_youtube_artists = ", ".join(self.string_cleaner(x["name"]).lower() for x in item["artists"])

                    title_ratio = 100 if all(word in cleaned_title for word in cleaned_youtube_title.split()) else fuzz.ratio(cleaned_title, cleaned_youtube_title)
                    artist_ratio = 100 if cleaned_artist in cleaned_youtube_artists else fuzz.ratio(cleaned_artist, cleaned_youtube_artists)

                    if title_ratio >= 90 and artist_ratio >= 90:
                        first_result = self.YOUTUBE_LINK_PREFIX + item["videoId"]
                        break
                else:
                    # Default to first result if Top result is not found
                    first_result = self.YOUTUBE_LINK_PREFIX + search_results[0]["videoId"]

                    # Search for Top result specifically
                    top_search_results = self.ytmusic.search(query=cleaned_title, limit=5)
                    cleaned_youtube_title = self.string_cleaner(top_search_results[0]["title"]).lower()
                    if "Top result" in top_search_results[0]["category"] and top_search_results[0]["resultType"] == "song" or top_search_results[0]["resultType"] == "video":
                        cleaned_youtube_artists = ", ".join(self.string_cleaner(x["name"]).lower() for x in top_search_results[0]["artists"])
                        title_ratio = 100 if cleaned_title in cleaned_youtube_title else fuzz.ratio(cleaned_title, cleaned_youtube_title)
                        artist_ratio = 100 if cleaned_artist in cleaned_youtube_artists else fuzz.ratio(cleaned_artist, cleaned_youtube_artists)
                        if (title_ratio >= 90 and artist_ratio >= 40) or (title_ratio >= 40 and artist_ratio >= 90):
                            first_result = self.YOUTUBE_LINK_PREFIX + top_search_results[0]["videoId"]

        except Exception as e:
            self.logger.error(f"Error Finding YouTube Link: {str(e)}")

        finally:
            return first_result

    def get_download_list(self, playlist):
        try:
            song_list_to_download = []
            playlist_name = playlist["Name"]
            playlist_link = playlist["Link"]
            if "youtube" in playlist_link:
                playlist_tracks = self.youtube_extractor(playlist_link)
            else:
                playlist_tracks = self.spotify_extractor(playlist_link)

            playlist_folder = playlist_name
            self.playlist_folder_path = os.path.join(self.download_folder, playlist_folder)

            if not os.path.exists(self.playlist_folder_path):
                os.makedirs(self.playlist_folder_path)

            raw_directory_list = os.listdir(self.playlist_folder_path)
            directory_list = self.string_cleaner(raw_directory_list)

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_limit) as executor:
                futures = []
                for song in playlist_tracks:
                    full_file_name = f'{song["Title"]} - {song["Artist"]}'
                    cleaned_full_file_name = self.string_cleaner(full_file_name)
                    if cleaned_full_file_name not in directory_list:
                        song_artist = song["Artist"]
                        song_title = song["Title"]
                        if song.get("VideoID"):
                            song_actual_link = self.YOUTUBE_LINK_PREFIX + song["VideoID"]
                            song_list_to_download.append({"title": cleaned_full_file_name, "link": song_actual_link})
                            self.logger.warning(f"Added Song to Download List: {cleaned_full_file_name} : {song_actual_link}")
                        else:
                            future = executor.submit(self.find_youtube_link, song_artist, song_title)
                            futures.append((future, cleaned_full_file_name))
                            self.logger.warning(f"Searching for Song: {cleaned_full_file_name}")
                    else:
                        self.logger.warning(f"File Already in folder: {cleaned_full_file_name}")

                for future, file_name in futures:
                    song_actual_link = future.result()
                    if song_actual_link:
                        song_list_to_download.append({"title": file_name, "link": song_actual_link})
                        self.logger.warning(f"Added Song to Download List: {file_name} : {song_actual_link}")
                    else:
                        self.logger.error(f"No Link Found for: {file_name}")

        except Exception as e:
            self.logger.error(f"Error Getting Download List: {str(e)}")

        finally:
            return song_list_to_download

    def download_queue(self, song_list, playlist):
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_limit) as executor:
                futures = []
                for song in song_list:
                    future = executor.submit(self.download_song, song, playlist)
                    futures.append(future)

                concurrent.futures.wait(futures)

        except Exception as e:
            self.logger.error(f"Error in Download Queue: {str(e)}")

    def download_song(self, song, playlist):
        if self.media_server_scan_req_flag == False:
            self.media_server_scan_req_flag = True
        link = song["link"]
        title = song["title"]
        sleep = playlist["Sleep"] if playlist["Sleep"] else 0
        full_file_path = os.path.join(self.playlist_folder_path, title)
        ydl_opts = {
            "logger": self.logger,
            "ffmpeg_location": "/usr/bin/ffmpeg",
            "format": "251/bestaudio",
            "outtmpl": full_file_path,
            "quiet": False,
            "progress_hooks": [self.progress_callback],
            "writethumbnail": True,
            "updatetime": False,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",
                },
                {
                    "key": "EmbedThumbnail",
                },
                {
                    "key": "FFmpegMetadata",
                },
            ],
        }

        if self.crop_album_art == "true":
            ydl_opts["postprocessor_args"] = {"thumbnailsconvertor+ffmpeg_o": ["-c:v", "mjpeg", "-vf", "crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'"]}

        if self.cookies_path:
            ydl_opts["cookiefile"] = self.cookies_path

        try:
            yt_downloader = yt_dlp.YoutubeDL(ydl_opts)
            self.logger.warning(f"yt_dlp - Starting Download of: {link}")

            yt_downloader.download([link])
            self.logger.warning(f"yt_dlp - Finished Download of: {link}")

            time.sleep(sleep)

        except Exception as e:
            self.logger.error(f"Error downloading song: {link}. Error message: {e}")

    def progress_callback(self, d):
        if d["status"] == "finished":
            self.logger.warning("Download complete")
            self.logger.warning("Processing File...")

        elif d["status"] == "downloading":
            self.logger.warning(f'Downloaded {d["_percent_str"]} of {d["_total_bytes_str"]} at {d["_speed_str"]}')

    def master_queue(self):
        try:
            self.sync_in_progress_flag = True
            self.media_server_scan_req_flag = False
            self.logger.warning("Sync Task started...")
            for playlist in self.sync_list:
                logging.warning(f'Looking for Playlist Songs on YouTube: {playlist["Name"]}')
                song_list = self.get_download_list(playlist)

                logging.warning(f'Starting Downloading List: {playlist["Name"]}')
                self.download_queue(song_list, playlist)

                logging.warning(f'Finished Downloading List: {playlist["Name"]}')

                playlist["Song_Count"] = len(os.listdir(self.playlist_folder_path))
                logging.warning(f'Files in Directory: {str(playlist["Song_Count"])}')

                playlist["Last_Synced"] = datetime.datetime.now().strftime("%d-%m-%y %H:%M:%S")

            self.save_sync_list_to_file()
            data = {"sync_list": self.sync_list}
            socketio.emit("Update", data)

            if self.media_server_scan_req_flag == True and self.media_server_tokens:
                self.sync_media_servers()
            else:
                self.logger.warning("Media Server Sync not required")

        except Exception as e:
            self.logger.error(f"Error in Master Queue: {str(e)}")
            self.logger.warning("Finished: Incomplete")

        else:
            self.logger.warning("Finished: Complete")

        finally:
            self.sync_in_progress_flag = False

    def add_playlist(self, playlist):
        self.sync_list.extend(playlist)

    def sync_media_servers(self):
        media_servers = self.convert_string_to_dict(self.media_server_addresses)
        media_tokens = self.convert_string_to_dict(self.media_server_tokens)
        if "Plex" in media_servers and "Plex" in media_tokens:
            try:
                token = media_tokens.get("Plex")
                address = media_servers.get("Plex")
                self.logger.warning("Attempting Plex Sync")
                media_server_server = PlexServer(address, token)
                library_section = media_server_server.library.section(self.media_server_library_name)
                library_section.update()
                self.logger.warning(f"Plex Library scan for '{self.media_server_library_name}' started.")
            except Exception as e:
                self.logger.warning(f"Plex Library scan failed: {str(e)}")

        if "Jellyfin" in media_tokens and "Jellyfin" in media_tokens:
            try:
                token = media_tokens.get("Jellyfin")
                address = media_servers.get("Jellyfin")
                self.logger.warning("Attempting Jellyfin Sync")
                url = f"{address}/Library/Refresh?api_key={token}"
                response = requests.post(url)
                if response.status_code == 204:
                    self.logger.warning("Jellyfin Library refresh request successful.")
                else:
                    self.logger.warning(f"Jellyfin Error: {response.status_code}, {response.text}")
            except Exception as e:
                self.logger.warning(f"Jellyfin Library scan failed: {str(e)}")

    def string_cleaner(self, input_string):
        if isinstance(input_string, str):
            raw_string = re.sub(r'[\/:*?"<>|]', " ", input_string)
            temp_string = re.sub(r"\s+", " ", raw_string)
            cleaned_string = temp_string.strip()
            return cleaned_string

        elif isinstance(input_string, list):
            cleaned_strings = []
            for string in input_string:
                file_name_without_extension, file_extension = os.path.splitext(string)
                raw_string = re.sub(r'[\/:*?"<>|]', " ", file_name_without_extension)
                temp_string = re.sub(r"\s+", " ", raw_string)
                cleaned_string = temp_string.strip()
                cleaned_strings.append(cleaned_string)
            return cleaned_strings

    def convert_string_to_dict(self, raw_string):
        result = {}
        if not raw_string:
            return result

        pairs = raw_string.split(",")
        for pair in pairs:
            key_value = pair.split(":", 1)
            if len(key_value) == 2:
                key, value = key_value
                result[key.strip()] = value.strip()

        return result

    def manual_start(self):
        if self.sync_in_progress_flag == True:
            self.logger.warning(f"Sync already in progress.")

        else:
            self.logger.warning("Manual Sync triggered.")
            task_thread = threading.Thread(target=self.master_queue, daemon=True)
            task_thread.start()


app = Flask(__name__)
app.secret_key = "secret_key"
socketio = SocketIO(app)

data_handler = DataHandler()


@app.route("/")
def home():
    return render_template("base.html")


@socketio.on("connect")
def connection():
    data = {"sync_list": data_handler.sync_list}
    socketio.emit("Update", data)


@socketio.on("loadSettings")
def loadSettings():
    data = {
        "sync_start_times": data_handler.sync_start_times,
        "media_server_addresses": data_handler.media_server_addresses,
        "media_server_tokens": data_handler.media_server_tokens,
        "media_server_library_name": data_handler.media_server_library_name,
        "spotify_client_id": data_handler.spotify_client_id,
        "spotify_client_secret": data_handler.spotify_client_secret,
    }
    socketio.emit("settingsLoaded", data)


@socketio.on("save_playlist_settings")
def save_playlist_settings(data):
    playlist_to_be_saved = data["playlist"]
    playlist_name = playlist_to_be_saved["Name"]
    for playlist in data_handler.sync_list:
        if playlist["Name"] == playlist_name:
            playlist.update(playlist_to_be_saved)
            break
    else:
        data_handler.sync_list.append(playlist_to_be_saved)
    data_handler.save_sync_list_to_file()


@socketio.on("updateSettings")
def updateSettings(data):
    data_handler.media_server_addresses = data["media_server_addresses"]
    data_handler.media_server_tokens = data["media_server_tokens"]
    data_handler.media_server_library_name = data["media_server_library_name"]
    data_handler.spotify_client_id = data["spotify_client_id"]
    data_handler.spotify_client_secret = data["spotify_client_secret"]

    try:
        if data["sync_start_times"] == "":
            raise Exception("No Time Entered, defaulting to 00:00")
        raw_sync_start_times = [int(re.sub(r"\D", "", start_time.strip())) for start_time in data["sync_start_times"].split(",")]
        temp_sync_start_times = [0 if x < 0 or x > 23 else x for x in raw_sync_start_times]
        cleaned_sync_start_times = sorted(list(set(temp_sync_start_times)))
        data_handler.sync_start_times = cleaned_sync_start_times

    except Exception as e:
        data_handler.logger.error(f"Error Parsing Schedule: {str(e)}")
        data_handler.sync_start_times = [0]

    finally:
        data_handler.logger.warning(f"Sync Times: {str(data_handler.sync_start_times)}")

    data_handler.save_to_file()


@socketio.on("add_playlist")
def add_playlist(data):
    data_handler.add_playlist(data)


@socketio.on("save_playlists")
def save_playlists(data):
    data_handler.sync_list = data["Saved_sync_list"]
    data_handler.save_sync_list_to_file()


@socketio.on("manual_start")
def manual_start():
    data_handler.manual_start()


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
