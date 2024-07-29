
var config_modal = document.getElementById('config-modal');
var save_message = document.getElementById("save-message");
var save_changes_button = document.getElementById("save-changes-button");
var save_sync_list = document.getElementById("save-sync-list");
var save_sync_list_msg = document.getElementById("save-sync-list-msg");
var sync_start_times = document.getElementById("sync_start_times");
var media_server_addresses = document.getElementById("media_server_addresses");
var media_server_tokens = document.getElementById("media_server_tokens");
var media_server_library_name = document.getElementById("media_server_library_name");
var spotify_client_id = document.getElementById("spotify_client_id");
var spotify_client_secret = document.getElementById("spotify_client_secret");
var playlists = [];
var socket = io();

function renderPlaylists() {
    var syncList = document.getElementById("sync-list");
    syncList.innerHTML = "";
    playlists.forEach((playlist, index) => {
        var row = document.createElement("tr");
        row.innerHTML = `
                <td>${playlist.Name}</td>
                <td>${playlist.Last_Synced}</td>
                <td>${playlist.Song_Count}</td>
                <td>
                    <button class="btn btn-sm btn-primary custom-button-width" data-bs-toggle="modal" data-bs-target="#editModal${index}">Edit</button>
                </td>
            `;
        var deleteButton = createDeleteButton(index);
        row.querySelector("td:last-child").appendChild(deleteButton);
        syncList.appendChild(row);
    });
}

function removePlaylist(index) {
    playlists.splice(index, 1);
    renderPlaylists();
    createEditModalsAndListeners();
}

function createDeleteButton(index) {
    var deleteButton = document.createElement("button");
    deleteButton.className = "btn btn-sm btn-warning custom-button-width";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", function () {
        removePlaylist(index);
    });
    return deleteButton;
}

function updated_info(response) {
    playlists = response.sync_list;
    renderPlaylists();
    createEditModalsAndListeners();
}

function createEditModalsAndListeners() {
    playlists.forEach((playlist, index) => {
        var editModal = document.createElement("div");
        editModal.innerHTML = `
                <div class="modal fade" id="editModal${index}" tabindex="-1" role="dialog" aria-labelledby="editModalLabel" aria-hidden="true">                <div class="modal-dialog" role="document">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="editModalLabel${index}">Edit Playlist</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                        <div id="save-message-playlist-edit${index}" style="display: none;" class="alert alert-success mt-3">
                        Settings saved successfully.
                        </div>
                            <form>
                                <div class="form-group">
                                    <label for="playlistName${index}">Playlist Name:</label>
                                    <input type="text" class="form-control" id="playlistName${index}" value="${playlist.Name}">
                                </div>
                                <div class="form-group my-4">
                                    <label for="playlistLink${index}">Playlist Link:</label>
                                    <input type="text" class="form-control" id="playlistLink${index}" value="${playlist.Link}">
                                </div>
                                <div class="form-group">
                                    <label for="playlistSleep${index}">Sleep Interval between downloads (Seconds):</label>
                                    <input type="number" class="form-control" min=0 id="playlistSleep${index}" value="${playlist.Sleep}">
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <button type="button" class="btn btn-primary" onclick="savePlaylistSettings(${index})">Save Changes</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(editModal);
    });
}

function savePlaylistSettings(index) {
    playlists[index].Name = document.getElementById(`playlistName${index}`).value;
    playlists[index].Link = document.getElementById(`playlistLink${index}`).value;
    playlists[index].Sleep = parseInt(document.getElementById(`playlistSleep${index}`).value, 10);
    socket.emit("save_playlist_settings", { "playlist": playlists[index] });
    var save_message_playlist_edit = document.getElementById(`save-message-playlist-edit${index}`);
    save_message_playlist_edit.style.display = "block";
    setTimeout(function () {
        save_message_playlist_edit.style.display = "none";
    }, 1000);
    renderPlaylists();
}

socket.on("Update", updated_info);

document.getElementById("add-playlist").addEventListener("click", function () {
    playlists.push({ ID: self.crypto.randomUUID() ,Name: "New Playlist", Link: "", Sleep: 0, Last_Synced: "Never", Song_Count: 0 });
    renderPlaylists();
    createEditModalsAndListeners();
});

config_modal.addEventListener('show.bs.modal', function (event) {
    socket.emit("loadSettings");
    function handleSettingsLoaded(settings) {
        sync_start_times.value = settings.sync_start_times.join(', ');
        media_server_addresses.value = settings.media_server_addresses;
        media_server_tokens.value = settings.media_server_tokens;
        media_server_library_name.value = settings.media_server_library_name;
        spotify_client_id.value = settings.spotify_client_id;
        spotify_client_secret.value = settings.spotify_client_secret;
        socket.off("settingsLoaded", handleSettingsLoaded);
    }
    socket.on("settingsLoaded", handleSettingsLoaded);
});

save_changes_button.addEventListener("click", () => {
    socket.emit("updateSettings", {
        "sync_start_times": sync_start_times.value,
        "media_server_addresses": media_server_addresses.value,
        "media_server_tokens": media_server_tokens.value,
        "media_server_library_name": media_server_library_name.value,
        "spotify_client_id": spotify_client_id.value,
        "spotify_client_secret": spotify_client_secret.value,
    });
    save_message.style.display = "block";
    setTimeout(function () {
        save_message.style.display = "none";
    }, 1000);
});

save_sync_list.addEventListener("click", () => {
    socket.emit("save_playlists", { "Saved_sync_list": playlists });
    save_sync_list_msg.style.display = "inline";
    save_sync_list_msg.textContent = "Saved!";
    setTimeout(function () {
        save_sync_list_msg.textContent = "";
        save_message.style.display = "none";
    }, 3000);
});

const themeSwitch = document.getElementById('themeSwitch');
const savedTheme = localStorage.getItem('theme');
const savedSwitchPosition = localStorage.getItem('switchPosition');

if (savedSwitchPosition) {
    themeSwitch.checked = savedSwitchPosition === 'true';
}

if (savedTheme) {
    document.documentElement.setAttribute('data-bs-theme', savedTheme);
}

themeSwitch.addEventListener('click', () => {
    if (document.documentElement.getAttribute('data-bs-theme') === 'dark') {
        document.documentElement.setAttribute('data-bs-theme', 'light');
    } else {
        document.documentElement.setAttribute('data-bs-theme', 'dark');
    }
    localStorage.setItem('theme', document.documentElement.getAttribute('data-bs-theme'));
    localStorage.setItem('switchPosition', themeSwitch.checked);
});
