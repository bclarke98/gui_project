import os
import sys
import json

from app.utils import *

def approve_song(user, args):
    r_queue = api_call(user.accesstoken, 'me/player/queue', rtype='post',
            params={'uri': args['song']})
    if r_queue.status_code in [202, 204]:
        remove_song(user, args['song'])
        return True, f'Added {args["song"]} to user {user.spotifyid}\'s Spotify queue'
    else:
        print('---UNEXPECTED STATUS CODE RETURNED FOR QUEUE ADDITION REQUEST---')
        print(f'Code: {r_queue.status_code}\nContent: {r_queue.content}\nHeaders: {r_queue.headers}')
    return False, '---UNEXPECTED STATUS CODE RETURNED FOR QUEUE ADDITION REQUEST---'

def deny_song(user, args):
    remove_song(user, args['song'])
    return True, f'Removed {args["song"]} from user {user.spotifyid}\'s request queue'

def block_song(user, args):
    if query_db(
            'select * from blocked where roomid=? and songuri=?',
            [user.id, args['song']]):
        return False, f'Song {args["song"]} already exists on user {user.spotifyid}\'s blocklist'
    query_db('insert into blocked (roomid, songuri) values (?,?)',
            [user.id, args['song']],
            commit=True)
    remove_song(user, args['song'])
    return True, f'Song {args["song"]} added to user {user.spotifyid}\'s blocklist'

def unblock_song(user, args):
    query_db('delete from blocked where roomid=? and songuri=?',
        [user.id, args['song']],
        commit=True)
    return True, f'Song {args["song"]} removed from user {user.spotifyid}\'s blocklist'

def dump_user(user, args):
    return user.dict

def disable_req(user, args):
    user.block_requests()
    return True, f'Requests disabled for user {user.spotifyid}'

def view_requests(user, args):
    user.view_requested_songs()
    return True, f'Viewing requested songs for user {user.spotifyid}'

def view_block(user, args):
    user.view_blocked_songs()
    return True, f'Viewing blocked songs for user {user.spotifyid}'


def get_requests(user, args):
    return True, [str(i) for i in user.get_requests()]

def get_top_tracks(user, args):
    r_top = api_call(user.accesstoken, 'me/top/tracks')
    try:
        j = r_top.json()
        for song in j['items']:
            print(song)
        return True, []
    except (KeyError, ValueError):
        return False, []

def get_blocked_tracks(user, args):
    return True, [str(i) for i in user.get_blocked()]

def enable_req(user, args):
    user.allow_requests()
    return True, f'Requests enabled for user {user.spotifyid}'

def remove_song(user, uri):
    query_db('delete from requests where roomid=? and songuri=?',
        [user.id, uri],
        commit=True)
