import io
import os
import sys
import json
import uuid
import qrcode
import string
import secrets
import requests
import datetime
import urllib.parse

APP_SCOPES = 'user-read-private user-read-email user-read-playback-state user-modify-playback-state'
API_URL = 'https://api.spotify.com/v1/'
OAUTH_HEADER = {'Content-Type': 'application/x-www-form-urlencoded'}

this = sys.modules[__name__]
this._client_id = None
this._client_secret = None
this._client_data = {}
this._query_func = None
this._logger = None

########## Misc Util Funcs ##########

def dir_last_updated(path):
    return str(max(os.path.getmtime(os.path.join(root_path, f))
                for root_path, dirs, files in os.walk(path)
                for f in files))

def die(s, *args, **kwargs):
    # print `s` and exit
    print(s, *args, **kwargs)
    sys.exit(1)

def encode_dict(d):
    # turns key/value pairs into URL style key/value format
    # For example, if d={'a': 1, 'b': 2}, then encode_dict(d) -> 'a=1&b=2'
    return urllib.parse.urlencode(d)

def random_string(length=16):
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for i in range(length))

def sendable_img(pil_img):
    img_io = io.BytesIO()
    pil_img.save(img_io, 'png')
    img_io.seek(0)
    return img_io

def make_qr(url):
    return qrcode.make(url)

def bind_query_func(qf):
    this._query_func = qf

def bind_logger(l):
    this._logger = l

def logger(*args, **kwargs):
    return this._logger.error(*args, **kwargs)

def mkdir(path):
    try:
        os.mkdir(os.path.join(os.getcwd(), path))
    except FileExistsError:
        pass
    except:
        print(f'[ERROR]: CANNOT MKDIR PATH: "{path}"')

def read_file(path):
    try:
        with open(path) as f:
            return f.read()
    except:
        return None

def timedelta(*args, **kwargs):
    # possible kwargs: [days, seconds, microseconds, miliseconds, minutes, hours, weeks]
    return datetime.datetime.now() + datetime.timedelta(*args, **kwargs)

def seconds_since(td):
    return (datetime.datetime.now() - td).total_seconds()

def dict_val(d, k):
    try:
        return d[k]
    except KeyError:
        return None

########## Spotify API Util Funcs ##########

def api_call(access_token, endpoint, rtype='get', params={}, *args, **kwargs):
    query = '' if len(params) == 0 else '?' + encode_dict(params)
    return getattr(requests, rtype.lower())(API_URL + endpoint + query, headers={'Authorization': 'Bearer ' + access_token}, *args, **kwargs)

def song_query(query):
    r = api_call(c_token(), 'search', params={'q':query, 'type': 'track'})
    try:
        return [Song(i['name'], i['uri'], i['artists'][0]['name'], i['album']['name'], i['album']['images'][0]['url']).dict for i in r.json()['tracks']['items']]
    except (ValueError, KeyError):
        return []

def track_query(query):
    r = api_call(c_token(), 'tracks/' + query.split(':')[-1])
    try:
        i = r.json()
        return Song(i['name'], i['uri'], i['artists'][0]['name'], i['album']['name'], i['album']['images'][0]['url']).dict
    except (ValueError, KeyError):
        return {}

def refresh_token(refresh_token, client_id, client_secret):
    r = requests.post('https://accounts.spotify.com/api/token', auth=(client_id, client_secret), headers=OAUTH_HEADER, data={'grant_type': 'refresh_token', 'refresh_token': refresh_token})
    try:
        return r.json()['access_token']
    except (ValueError, KeyError):
        return None

def user_login_callback(auth_code, redirect_uri, client_id, client_secret):
    payload = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret
    }
    r_token = requests.post('https://accounts.spotify.com/api/token', data=payload, headers=OAUTH_HEADER)
    try:
        j = r_token.json()
        a_token = j['access_token']
        expires = j['expires_in']
        ref_token = j['refresh_token']
        t_type = j['token_type']
        return [a_token, expires, ref_token, t_type]
    except (ValueError, KeyError) as e:
        raise Exception(str(e))

def user_init_call(access_token, ref_token):
    r_me = api_call(access_token, 'me')
    try:
        uid = r_me.json()['id']
        existing = db_get_user(uid)
        if existing is None:
            query_db(
                'insert into users (spotifyid, refreshtoken, accesstoken) values (?,?,?)',
                [ uid, ref_token, access_token ],
                commit=True
            )
        else:
            query_db(
                'update users set refreshtoken = ?, accesstoken = ? where spotifyid = ?',
                [ ref_token, access_token, uid ],
                commit=True
            )
        return uid
    except (ValueError, KeyError):
        raise Exception('API call to "/me" failed to be parsed')

def client_auth_init(client_id, client_secret):
    return requests.post('https://accounts.spotify.com/api/token', auth=(client_id, client_secret), headers=OAUTH_HEADER, data={'grant_type': 'client_credentials'})

def authorize_client(client_id, client_secret):
    resp = client_auth_init(client_id, client_secret)
    try:
        j = resp.json()
        this._client_data['token'] = j['access_token']
        this._client_data['timestamp'] = datetime.datetime.now()
        return True
    except (ValueError, KeyError):
        return False

def c_token():
    if dict_val(this._client_data, 'timestamp') is None or \
            seconds_since(this._client_data['timestamp']) >= 3600:

        if not authorize_client(this._client_id, this._client_secret):
            die('BACKEND SPOTIFY CLIENT UNABLE TO RE-AUTHORIZE')
    return this._client_data['token']

def init_client(client_id, client_secret):
    if this._client_id is None:
        this._client_id = client_id
    if this._client_secret is None:
        this._client_secret = client_secret
    if not authorize_client(client_id, client_secret):
        die('BACKEND SPOTIFY CLIENT UNABLE TO AUTHORIZE')

########## Database Util Funcs ##########

def query_db(*args, **kwargs):
    return this._query_func(*args, **kwargs)

def db_gen_key():
    key = str(uuid.uuid4())
    query_db('insert into keys (uuid) values (?)', [key], commit=True)
    return key

def db_check_key(key):
    return query_db('select * from keys where uuid=?', [key], one=True)

def db_disable_key(key):
    query_db('update keys set valid = 0 where uuid=?', [key], commit=True)

def db_get_user(spotifyid):
    return query_db('select * from users where spotifyid = ?', [spotifyid], one=True)

def db_verify_user(spotifyid, refreshtoken):
    return DBUser(query_db('select * from users where spotifyid = ? and refreshtoken = ?',
            [spotifyid, refreshtoken],
            one=True))

########## Database Util Classes ##########

class DBUser(object):
    def __init__(self, dbrow):
        self.row = dbrow
        self.valid = dbrow is not None
        self.dict = {}
        if self.valid:
            for i in dbrow.keys():
                self.dict[i] = dbrow[i]

    def refresh(self, c_id, c_secret):
        token = refresh_token(self.refreshtoken, c_id, c_secret)
        if token is None:
            return False
        query_db(
            'update users set accesstoken = ? where spotifyid = ? and refreshtoken = ?',
            [token, self.spotifyid, self.refreshtoken],
            commit=True
        )
        self.dict['accesstoken'] = token
        return True

    def block_requests(self):
        query_db('update users set enabled = 0 where spotifyid = ? and refreshtoken = ?',
                [self.spotifyid, self.refreshtoken],
                commit=True
        )

    def allow_requests(self):
        query_db('update users set enabled = 1 where spotifyid = ? and refreshtoken = ?',
                [self.spotifyid, self.refreshtoken],
                commit=True
        )

    def view_requested_songs(self):
        query_db('update users set viewingblocked = 0 where spotifyid = ? and refreshtoken = ?',
                [self.spotifyid, self.refreshtoken],
                commit=True)

    def view_blocked_songs(self):
        query_db('update users set viewingblocked = 1 where spotifyid = ? and refreshtoken = ?',
                [self.spotifyid, self.refreshtoken],
                commit=True)

    def get_requests(self):
        return [Song.from_json(i) for i in query_db(
            'select * from requests where roomid=?',
            [self.id],
        )]

    def get_blocked(self):
        # TODO: search song from spotify api for 'i' since 'i' is the spotify track URI
        return [Song.from_json(track_query(i['songuri'])) for i in query_db(
            'select * from blocked where roomid=?',
            [self.id]
        )]

    def __str__(self):
        return '' if not self.valid else json.dumps(self.dict, indent=4, sort_keys=True)

    def __getattr__(self, attr):
        return dict_val(self.dict, attr)

class Song(object):
    def __init__(self, name, uri, artist, album, arturi):
        self.dict = {
            'songuri': uri,
            'songname': name,
            'artistname': artist,
            'albumname': album,
            'albumart': arturi,
        }

    def request_to_room(self, room):
        if query_db(
            'select * from users where id = ? and enabled = 0',
            [room]):
            return False, 'This room is locked and won\'t receive requests until the owner unlocks it!'
        if query_db(
            'select * from requests where songuri = ? and roomid = ?',
            [self.songuri, room]
            ):
            return False, 'This song is already in the request queue for this room!'
        if query_db(
            'select * from blocked where songuri = ? and roomid = ?',
            [self.songuri, room]):
            return False, 'This song has been blocked by the room\'s host!'
        query_db(
            'insert into requests (roomid, songuri, songname, artistname, albumname, albumart) values (?,?,?,?,?,?)',
            [room, self.songuri, self.songname, self.artistname, self.albumname, self.albumart],
            commit=True
        )
        return True, f'Successfully requested "{self.songname}" by {self.artistname} to Room #{room}'


    def __str__(self):
        return json.dumps(self.dict, indent=4, sort_keys=True)

    def __getattr__(self, attr):
        return dict_val(self.dict, attr)

    @staticmethod
    def from_str(s):
        return Song.from_json(json.loads(s))

    @staticmethod
    def from_json(j):
        try:
            return Song(j['songname'], j['songuri'], j['artistname'], j['albumname'], j['albumart'])
        except KeyError:
            die('Invalid song attempting to be created from json: ' + json.dumps(j, indent=4))
