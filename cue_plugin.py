import re, os
from urllib.parse import unquote
from gi.repository import GObject, RB, Peas, Gtk

class CueListPlugin(GObject.Object, Peas.Activatable):
    object = GObject.property(type=GObject.Object)

    def __init__(self):
        super(CueListPlugin, self).__init__()

    def do_activate(self):
        shell = self.object
        self.shell_player = shell.props.shell_player
        self.playing_changed_handler_id = self.shell_player.connect('playing-song-changed', self.on_playing_song_changed)
        self.elapsed_changed_id = self.shell_player.connect('elapsed-changed', self.on_elapsed_changed)
        self.window = None

    def do_deactivate(self):
        if self.window:
            self.shell_player.disconnect(self.playing_changed_handler_id)
            self.shell_player.disconnect(self.elapsed_changed_id)
            self.window.destroy()

    # Handle track change event
    def on_playing_song_changed(self, player, playing, data=None):
        playing_track = self.shell_player.get_playing_entry()

        # Avoid creating a playlist window if Rhythmbox has just launched
        if not playing_track:
            # Destroy the playlist window, if there is one for the previous track, when clicking the Next/Previous track button
            if self.window:
                self.window.destroy()
            return

        # Try parsing the CUE file if it exists and storing it in a data array
        playing_track_uri = playing_track.get_playback_uri()
        self.track_data = self.check_and_parse_cue_file(playing_track_uri)

        # Display the playlist window if the parsing was successful
        if self.track_data:

            # Destroy the playlist window if there is one for the previous track
            if self.window:
                self.window.destroy()

            # Add the duration of the currently playing track to the end of the data array
            playing_track_duration=self.shell_player.get_playing_song_duration()
            self.track_data.append(("NULL", playing_track_duration))
            self.liststore = Gtk.ListStore(str, str, str)

            # Add the title of each track to the playlist along with the corresponding duration, converted to hh:mm:ss format
            for i in range(0, len(self.track_data) - 1):
                track_offset = self.track_data[i][1]
                next_track_offset = self.track_data[i+1][1]
                track_duration = next_track_offset - track_offset
                track_title = self.track_data[i][0]
                
                # Add a play mark to the first title only
                if i == 0:
                    self.liststore.append(["▶", track_title, self.seconds_to_hms(track_duration)])
                    self.row = 0
                else:
                    self.liststore.append(["", track_title, self.seconds_to_hms(track_duration)])
            
            # Create a playlist window
            treeview = Gtk.TreeView(model=self.liststore)
            treeview.connect("row-activated", self.on_tree_row_activated)

            renderer_current = Gtk.CellRendererText()            
            column_current = Gtk.TreeViewColumn("🔊", renderer_current, text=0)
            treeview.append_column(column_current)

            renderer_title = Gtk.CellRendererText()
            column_title = Gtk.TreeViewColumn("Title", renderer_title, text=1)
            treeview.append_column(column_title)

            renderer_time = Gtk.CellRendererText()
            renderer_time.set_property("xalign", 1.0)
            column_time = Gtk.TreeViewColumn("Time", renderer_time, text=2)
            treeview.append_column(column_time)

            self.window = Gtk.Window()
            self.window.set_title(playing_track.get_string(RB.RhythmDBPropType.TITLE).rsplit('.', 1)[0])
            self.window.add(treeview)

            width, height = self.window.get_size()
            self.window.set_size_request(width, height)
            self.window.set_resizable(False)

            self.window.show_all()
        elif self.window:
            self.window.destroy()

    # Mark the track being played in the playlist window 
    def on_elapsed_changed(self, player, elapsed):
            if self.window and self.track_data:
                if elapsed >= self.track_data[self.row][1] and elapsed <= self.track_data[self.row+1][1]:
                    return
                for i in range(0, len(self.track_data) - 1):
                    track_offset = self.track_data[i][1]
                    next_track_offset = self.track_data[i+1][1]
                    if elapsed >=track_offset and elapsed <=next_track_offset: 
                        self.liststore[self.row][0] = ""
                        self.liststore[i][0] = "▶"
                        break
                self.row = i

    # Play a track from the playlist by double clicking on it
    def on_tree_row_activated(self, treeview, path, column):
        model = treeview.get_model()
        selected_iter = model.get_iter(path)
        if selected_iter is not None:
            selected_track = model.get_value(selected_iter, 1)
            for i in range(0, len(self.track_data) - 1):
                track_title = self.track_data[i][0]
                track_offset = self.track_data[i][1]
                if track_title == selected_track:

                    # Change the position of the play mark
                    self.liststore[self.row][0] = ""
                    self.liststore[i][0] = "▶"
                    self.row = i

                    # Set the playback position
                    self.shell_player.set_playing_time(track_offset)

                    # Starts playback, if it is not already playing
                    self.shell_player.play()
                    break

    # If the CUE file is in the same directory and has the same name
    # as the audio file (track_uri), the function parses the CUE file
    # and returns a two-dimensional array:
    #	i,0 - title of a track
    #	i,1 - offset from the beginning of the track in seconds
    # otherwise, or in case the CUE file does not match the audio file,
    # an empty array is returned
    def check_and_parse_cue_file(self,track_uri):
        track_data = []
        track_file_path = unquote(track_uri).replace("file://", "")

        # Check for the presence of a CUE file
        track_file_path_without_ext = track_file_path.rsplit('.', 1)[0]
        cue_file_path = track_file_path_without_ext + ".cue"
        if not os.path.exists(cue_file_path):
            return

        with open(cue_file_path, 'r', encoding='utf-8') as cue_file:
            cue_content = cue_file.read()

        # Check if the CUE file match the audio file
        track_file_name_without_ext = re.search(r'([^/]+)$', track_file_path_without_ext)
        file_pattern = re.compile(r'FILE "(.+)" WAVE')
        file_matches = list(file_pattern.finditer(cue_content))
        if len(file_matches) != 1:
            return
        else:
            if file_matches[0].group(1).rsplit('.', 1)[0] != track_file_name_without_ext.group(1):
               return

        # Parse the CUE file and store all entries in a data array
        track_pattern = re.compile(r'TRACK (\d+) AUDIO\n\s+TITLE "([^"]+)"', re.MULTILINE)
        index_pattern = re.compile(r'INDEX 01 (\d+):(\d+):(\d+)', re.MULTILINE)
        track_matches = track_pattern.finditer(cue_content)
        index_matches = index_pattern.finditer(cue_content)
        for track_match, index_match in zip(track_matches, index_matches):
            track_number = int(track_match.group(1))
            track_title = track_match.group(2) + "\t\t"
            minutes = int(index_match.group(1))
            seconds = int(index_match.group(2))
            total_seconds = minutes * 60 + seconds
            track_data.append((track_title, total_seconds))
        return track_data

    # Convert seconds to hh:mm:ss format string
    def seconds_to_hms(self,seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours == 0:
            return f"{minutes}:{seconds:02d}"
        else:
            if minutes < 10:
                return f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{hours}:{minutes}:{seconds:02d}"
