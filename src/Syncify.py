import logging
import os
import sys
import time
import datetime
import threading
import re
from flask import Flask, render_template
from flask_socketio import SocketIO
from ytmusicapi import YTMusic
import yt_dlp
import json
from plexapi.server import PlexServer
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import concurrent.futures


class Data_Handler:
    def __init__(self, thread_limit):
        self.config_folder = "config"
        self.download_folder = "download"
        self.plex_address = "http://192.168.1.2:32400"
        self.plex_token = "abc123"
        self.plex_library_name = "You Tube"
        self.spotify_client_id = "abc"
        self.spotify_client_secret = "123"
        self.thread_limit = thread_limit

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

        task_thread = threading.Thread(target=self.schedule_checker)
        task_thread.daemon = True
        task_thread.start()

    def load_from_file(self):
        try:
            with open(self.settings_config_file, "r") as json_file:
                ret = json.load(json_file)
            self.sync_start_times = ret["sync_start_times"]
            self.plex_address = ret["plex_address"]
            self.plex_token = ret["plex_token"]
            self.plex_library_name = ret["plex_library_name"]
            self.spotify_client_id = ret["spotify_client_id"]
            self.spotify_client_secret = ret["spotify_client_secret"]

        except Exception as e:
            logger.error("Error Loading Config: " + str(e))

    def save_to_file(self):
        try:
            with open(self.settings_config_file, "w") as json_file:
                json.dump(
                    {
                        "sync_start_times": self.sync_start_times,
                        "plex_address": self.plex_address,
                        "plex_token": self.plex_token,
                        "plex_library_name": self.plex_library_name,
                        "spotify_client_id": self.spotify_client_id,
                        "spotify_client_secret": self.spotify_client_secret,
                    },
                    json_file,
                    indent=4,
                )

        except Exception as e:
            logger.error("Error Saving Config: " + str(e))

    def load_sync_list_from_file(self):
        try:
            with open(self.sync_list_config_file, "r") as json_file:
                self.sync_list = json.load(json_file)

        except Exception as e:
            logger.error("Error Loading Playlists: " + str(e))

    def save_sync_list_to_file(self):
        try:
            with open(self.sync_list_config_file, "w") as json_file:
                json.dump(self.sync_list, json_file, indent=4)

        except Exception as e:
            logger.error("Error Saving Playlists: " + str(e))

    def schedule_checker(self):
        while True:
            current_time = datetime.datetime.now().time()
            within_sync_window = any(datetime.time(t, 0, 0) <= current_time <= datetime.time(t, 59, 59) for t in self.sync_start_times)

            if within_sync_window:
                logger.warning("Time to Start Sync")
                self.master_queue()
                logger.warning("Big sleep for 1 Hour - Sync Done")
                time.sleep(3600)
            else:
                logger.warning("Small sleep as not in sync time window " + str(self.sync_start_times) + " - checking again in 60 seconds")
                time.sleep(60)

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
                except:
                    pass

        else:
            playlist = sp.playlist(link)
            playlist_name = playlist["name"]
            number_of_tracks = playlist["tracks"]["total"]
            fields = "items.track(name,artists.name)"

            offset = 0
            limit = 100
            all_items = []
            while offset < number_of_tracks:
                results = sp.playlist_items(link, fields=fields, limit=limit, offset=offset)
                all_items.extend(results["items"])
                offset += limit

            for item in all_items:
                try:
                    track = item["track"]
                    track_title = track["name"]
                    artists = [artist["name"] for artist in track["artists"]]
                    artists_str = ", ".join(artists)
                    track_list.append({"Artist": artists_str, "Title": track_title, "Status": "Queued", "Folder": playlist_name})
                except:
                    pass

        return track_list

    def find_youtube_link(self, artist, title):
        self.ytmusic = YTMusic()
        search_results = self.ytmusic.search(query=artist + " " + title, filter="songs", limit=5)
        first_result = None
        cleaned_title = self.string_cleaner(title).lower()
        for item in search_results:
            cleaned_youtube_title = self.string_cleaner(item["title"]).lower()
            if cleaned_title in cleaned_youtube_title:
                first_result = "https://www.youtube.com/watch?v=" + item["videoId"]
                break
        else:
            # Try again but reverse the check otherwise select top result
            if len(search_results):
                for item in search_results:
                    cleaned_youtube_title = self.string_cleaner(item["title"]).lower()
                    if all(word in cleaned_title for word in cleaned_youtube_title.split()):
                        first_result = "https://www.youtube.com/watch?v=" + item["videoId"]
                        break
                else:
                    first_result = "https://www.youtube.com/watch?v=" + search_results[0]["videoId"]
        return first_result

    def get_download_list(self, playlist):
        playlist_name = playlist["Name"]
        playlist_link = playlist["Link"]
        playlist_tracks = self.spotify_extractor(playlist_link)

        playlist_folder = playlist["Name"]
        self.playlist_folder_path = os.path.join(self.download_folder, playlist_folder)

        if not os.path.exists(self.playlist_folder_path):
            os.makedirs(self.playlist_folder_path)

        raw_directory_list = os.listdir(self.playlist_folder_path)
        directory_list = self.string_cleaner(raw_directory_list)

        song_list_to_download = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_limit) as executor:
            futures = []
            for song in playlist_tracks:
                full_file_name = song["Title"] + " - " + song["Artist"]
                cleaned_full_file_name = self.string_cleaner(full_file_name)
                if cleaned_full_file_name not in directory_list:
                    song_artist = song["Artist"]
                    song_title = song["Title"]
                    future = executor.submit(self.find_youtube_link, song_artist, song_title)
                    futures.append((future, cleaned_full_file_name))
                    logger.warning("Searching for Song: " + cleaned_full_file_name)
                else:
                    logger.warning("File Already in folder: " + cleaned_full_file_name)

            for future, file_name in futures:
                song_actual_link = future.result()
                if song_actual_link:
                    song_list_to_download.append({"title": file_name, "link": song_actual_link})
                    logger.warning("Added Song to Download List: " + file_name + " : " + song_actual_link)
                else:
                    logger.error("No Link Found for: " + file_name)

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
            logger.error(str(e))

    def download_song(self, song, playlist):
        link = song["link"]
        title = song["title"]
        sleep = playlist["Sleep"] if playlist["Sleep"] else 0
        full_file_path = os.path.join(self.playlist_folder_path, title + ".mp3")
        ydl_opts = {
            "ffmpeg_location": "/usr/bin/ffmpeg",
            "format": "251/best",
            "outtmpl": full_file_path,
            "quiet": False,
            "progress_hooks": [self.progress_callback],
            "merge_output_format": "mp3",
            "sleep_interval": sleep,
            "add_metadata": True,
            "embed_thumnail": True,
        }

        try:
            yt_downloader = yt_dlp.YoutubeDL(ydl_opts)
            logger.warning("yt_dl Start : " + link)

            yt_downloader.download([link])
            logger.warning("yt_dl Complete : " + link)

        except Exception as e:
            logger.error(f"Error downloading song: {link}. Error message: {e}")

    def progress_callback(self, d):
        if d["status"] == "finished":
            logger.warning("Download complete")

        elif d["status"] == "downloading":
            logger.warning(f'Downloaded {d["_percent_str"]} of {d["_total_bytes_str"]} at {d["_speed_str"]}')

    def master_queue(self):
        try:
            logger.warning("Sync Task started...")
            for playlist in self.sync_list:
                logging.warning("Looking for Playlist Songs on YouTube: " + playlist["Name"])
                song_list = self.get_download_list(playlist)

                logging.warning("Starting Downloading List: " + playlist["Name"])
                self.download_queue(song_list, playlist)

                logging.warning("Finished Downloading List: " + playlist["Name"])

                playlist["Song_Count"] = len(os.listdir(self.playlist_folder_path))
                logging.warning("Files in Directory: " + str(playlist["Song_Count"]))

                playlist["Last_Synced"] = datetime.datetime.now().strftime("%d-%m-%y %H:%M:%S")

            self.save_sync_list_to_file()
            data = {"sync_list": self.sync_list}
            socketio.emit("Update", data)

            logger.warning("Attempting Plex Sync")
            plex_server = PlexServer(self.plex_address, self.plex_token)
            library_section = plex_server.library.section(self.plex_library_name)
            library_section.update()
            logger.warning(f"Library scan for '{self.plex_library_name}' started.")

        except Exception as e:
            logger.error(str(e))
            logger.warning("Sync Finished")

        else:
            logger.warning("Successfully Completed")

    def add_playlist(self, playlist):
        self.sync_list.extend(playlist)

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


app = Flask(__name__)
app.secret_key = "secret_key"
socketio = SocketIO(app)

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s", datefmt="%d/%m/%Y %H:%M:%S", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger()

try:
    thread_limit = int(os.environ["thread_limit"])

except:
    thread_limit = 1

logger.warning("thread_limit: " + str(thread_limit))
data_handler = Data_Handler(thread_limit)


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
        "plex_address": data_handler.plex_address,
        "plex_token": data_handler.plex_token,
        "plex_library_name": data_handler.plex_library_name,
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
    data_handler.plex_address = data["plex_address"]
    data_handler.plex_token = data["plex_token"]
    data_handler.plex_library_name = data["plex_library_name"]
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
        logger.error(str(e))
        data_handler.sync_start_times = [0]
    finally:
        logger.warning("Sync Times: " + str(data_handler.sync_start_times))
    data_handler.save_to_file()


@socketio.on("add_playlist")
def add_playlist(data):
    data_handler.add_playlist(data)


@socketio.on("save_playlists")
def save_playlists(data):
    data_handler.sync_list = data["Saved_sync_list"]
    data_handler.save_sync_list_to_file()


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
