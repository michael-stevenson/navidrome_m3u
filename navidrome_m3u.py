#!/usr/bin/env python

import sqlite3
import argparse
from asyncinotify import Inotify, Mask
import asyncio

class PlaylistProcessor:

    def __init__(self, database, playlists):
        self.connection = sqlite3.connect(database)
        self.playlists = playlists

    def __call__(self, args):

        for playlist in self.playlists:
            self._process_playlist(args, playlist)

    def _process_playlist(self, args, playlist):
        m3u = "{pl}.m3u".format(pl = playlist)
        with open(m3u, 'w') as f:
            f.write("#EXTM3U\n".format(name = playlist))
            f.write("#PLAYLIST:{name}\n".format(name = playlist))
            cursor = self.connection.execute(
                "SELECT mf.path FROM media_file mf \
                 JOIN playlist_tracks pt ON mf.id = pt.media_file_id \
                 JOIN playlist pl ON pt.playlist_id = pl.id")

            for row in cursor.fetchall():
                path = row[0]
                if args.old_root and args.new_root:
                    path = path.replace(args.old_root, args.new_root)

                f.write("{path}\n".format(path = path))

def _process(args, playlists):
    processor = PlaylistProcessor(args.database, playlists)
    processor(args)
        
async def async_main(args, playlists):
    with Inotify() as inotify:
        inotify.add_watch(args.database, Mask.MODIFY | Mask.CLOSE);
        async for event in inotify:
            _process(args, playlists)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=str, help = "The database to query")
    parser.add_argument("--continuous", action = 'store_true', help = "daemonize and monitor")
    parser.add_argument("--playlist", type=str, help = "Only translate the chosen playlist", default = None)
    parser.add_argument("--old_root", type = str, default = None)
    parser.add_argument("--new_root", type = str, default = None)
    args = parser.parse_args()

    playlists = list()
    if args.playlist is not None:
        playlists.append(args.playlist)
    else:
        connection = sqlite3.connect(args.database)
        for r in connection.execute("select name from playlist").fetchall():
            playlists.append(r[0])

    if not args.continuous:
        _process(args, playlists)

    else:
        import os
        pid = os.fork()
        if pid == 0:
            loop = asyncio.get_event_loop()
            try:
                loop.run_until_complete(async_main(args, playlists))
            except KeyboardInterrupt:
                pass
            finally:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()

if __name__ == "__main__":
    main()
