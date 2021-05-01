import time
import json
import requests
import traceback

from flask import make_response, render_template, redirect, request, jsonify, url_for, send_file
from werkzeug.exceptions import HTTPException
import app.manager as manager

from app.utils import *
from app import app, auth, STATIC_PATH

def delete_cookie(r, cookie):
    r.set_cookie(cookie, '', expires=0)

def clear_spotify_cookies(r):
    delete_cookie(r, 'spotify_auth_state')
    delete_cookie(r, 'spotify_uid')
    delete_cookie(r, 'spotify_refresh_token')
    delete_cookie(r, '_spotify_refresh_token')
    return r

def jerror(j, redir='index'):
    return clear_spotify_cookies(make_response(render_template('error.tmpl', response=j, redir=redir)))

@app.after_request
def after_request(response):
    if response.status_code != 500:
        ts = time.strftime('[%Y-%b-%d %H:%M]')
        logger('%s %-15s %-4s %s %s %s',
                ts,
                request.remote_addr,
                request.method,
                request.scheme,
                response.status,
                request.full_path)
    return response

@app.errorhandler(Exception)
def exceptions(e):
    if isinstance(e, HTTPException):
        return e
    ts = time.strftime('[%Y-%b-%d %H:%M]')
    tb = traceback.format_exc()
    logger('%s %s %s %s %s 5xx INTERNAL SERVER ERROR\n%s',
            ts,
            request.remote_addr,
            request.method,
            request.scheme,
            request.full_path,
            tb)
    return 'Internal Server Error', 500

@auth.verify_password
def verify_pw(username, password):
    user = db_verify_user(username, password)
    if user.valid:
        return username

@app.route('/api/<func>')
@auth.login_required
def api(func):
    args = {}
    for i in request.args:
        args[i] = request.args.get(i)
    result, message = getattr(manager, func)(DBUser(db_get_user(auth.current_user())), args)
    return jsonify({'result': int(result), 'message': message})

@app.route('/')
def index():
    s_uid = request.cookies.get('spotify_uid')
    s_expired = request.cookies.get('spotify_refresh_token')
    s_need_refresh = True if s_expired is None else len(s_expired) == 0
    s_refresh_token = request.cookies.get('_spotify_refresh_token')
    s_refreshed = False
    user = None
    sus = False
    error = ''
    if s_uid and s_refresh_token:
        user = DBUser(db_get_user(s_uid))
        if user.valid:
            if user.refreshtoken != s_refresh_token:
                sus = True
                # TODO: actually do something if sus flag gets set
    rooms = sorted([i['id'] for i in query_db('select id from users')])

    searchq = request.args.get('query')
    roomnum = request.args.get('room')
    template = 'results.tmpl'
    songs = []
    if searchq:
        songs = song_query(searchq)
    if user and user.valid and not sus:
        if user.viewingblocked:
            songs = user.get_blocked()
            template = 'blocked.tmpl'
        else:
            songs = user.get_requests()
            template = 'room.tmpl'
    r = make_response(render_template(
        template,
        user=user, songs=songs, rooms=rooms, roomnum=roomnum, numsongs=len(songs),
        last_updated=dir_last_updated(STATIC_PATH)))
    return r

@app.route('/auth/<callback>')
def handle_auth(callback='index'):
    '''This function acts as a HTTPBasicAuth wrapper for requests,
    making calls to the /api endpoint using the cookie values of
    spotify_uid and spotify_refresh_token as the username/password.
    Necessary for future expansion to allow for apps to communicate
    securely with the /api endpoint while still allowing web-based
    clients to authenticate with the original cookie method.
    '''
    s_uid = request.cookies.get('spotify_uid')
    s_expired = request.cookies.get('spotify_refresh_token')
    s_need_refresh = True if s_expired is None else len(s_expired) == 0
    s_refresh_token = request.cookies.get('_spotify_refresh_token')
    refreshed = False
    error = ''
    user = db_verify_user(s_uid, s_refresh_token)
    if user.valid and s_need_refresh:
        if not user.refresh(app.config['S_CLIENT_ID'], app.config['S_CLIENT_SECRET']):
            error = 'UNABLE TO REFRESH USER ACCESS TOKEN'
        else:
            refreshed = True

    r = requests.get(request.url_root + 'api/' + request.args.get('func') + '?' + encode_dict(request.args), auth=(s_uid, s_refresh_token))
    if r.status_code == 200:
        # user properly authenticated
        pass
    resp = redirect(url_for(callback))
    if refreshed:
        resp.set_cookie('spotify_refresh_token', s_refresh_token, max_age=3600)
    return resp

@app.route('/search/<query>')
def search(query):
    return json.dumps(song_query(query))

@app.route('/track/<query>')
def track(query):
    return json.dumps(track_query(query))

@app.route('/logout')
def logout():
    return clear_spotify_cookies(make_response(redirect(url_for('index'))))

@app.route('/request/<int:room>', methods=['GET', 'POST'])
def handle_request(room):
    if request.method == 'POST':
        j = request.json
        try:
            s = Song.from_json(j)
            flag, msg = s.request_to_room(room)
            return jsonify({'result': int(flag), 'message': msg})
        except (ValueError, KeyError):
            return jsonify({'result': 0, 'message': 'Unable to parse song from POST request contents'})
    else:
        return jerror({'result': 0, 'message': 'GET request sent to POST only endpoint'})

@app.route('/stat')
def stat():
    return jsonify({
        'rooms': [i['id'] for i in query_db('select id from users where enabled=1')],
    })

@app.route('/login', defaults={'uclient': 'web'})
@app.route('/login/<uclient>')
def login(uclient):
    temp_state = uclient[:3] + ':' + random_string()
    payload = {
        'client_id': app.config['S_CLIENT_ID'],
        'response_type': 'code',
        'redirect_uri': app.config['S_REDIRECT_URI'],
        'state': temp_state,
        'scope': APP_SCOPES,
        'show_dialog': False
    }
    r = clear_spotify_cookies(make_response(redirect('https://accounts.spotify.com/authorize?' + encode_dict(payload))))
    r.set_cookie('spotify_auth_state', temp_state, max_age=3600)
    return r

@app.route('/callback', methods=['GET', 'POST'])
def callback():
    # First, make sure that the state value hasn't been tampered with between requests
    s_query = request.args.get('state')
    if request.method == 'GET':
        s_cookie = request.cookies.get('spotify_auth_state')
        if s_cookie and s_cookie != s_query:
            print('Mismatched states')
            return jerror({'result': 0, 'message': 'ERROR: State value changed between request and response. Aborting.'})
    # Now check to see if the user actually accepted our request for access
    code = request.args.get('code')
    error = request.args.get('error')
    if error:
        print(f'Authorization callback failed. Error: "{error}"')
        return jerror({'result': 0, 'message': f'Authorization callback failed. Error: "{error}"'})
    if not code:
        print('Authorization "succeeded" without returning access code.')
        return jerror({'result': 0, 'message': 'Authorization "succeeded" without returning access code.'})
    # Now we use the auth code we just got to request a refresh token and an
    # access token for that user
    try:
        app_redir = request.args.get('redir') if request.method == 'POST' else app.config['S_REDIRECT_URI']
        a_token, expires, ref_token, t_type = user_login_callback(code, app_redir, app.config['S_CLIENT_ID'], app.config['S_CLIENT_SECRET'])
    except Exception as e:
        print(f'Thrown Exception: {e}')
        print('Unable to parse JSON response during auth token exchange.')
        return jsonify({'result': 0, 'message': 'Unable to parse JSON response during auth token exchange.'})
    # if no exceptions were thrown, we can finally use the access token to grab
    # the user's account in order to provide a "username" with which we'll
    # use to identify them
    try:
        uid = user_init_call(a_token, ref_token)
        user = db_verify_user(uid, ref_token)
        if request.method == 'GET':
            response = make_response(redirect(url_for('index')))
            response.set_cookie('spotify_uid', uid, max_age=3600)
            response.set_cookie('spotify_refresh_token', ref_token, max_age=3600)
            response.set_cookie('_spotify_refresh_token', ref_token)
            return response
        else:
            return jsonify({'result': 1, 'message': 'Authorization successful', 'user': json.dumps(user.dict)})
    except Exception as e:
        print(f'Thrown Exception: {e}')
        print('Unable to parse response from API call.')
        return jsonify({'result': 0, 'message': 'Unable to parse response from API call.'})

@app.route('/qrcode/<int:roomid>')
def qrgen(roomid):
    return send_file(sendable_img(make_qr(f'https://q.d3x.me/?room={roomid}')), mimetype='image/png')

@app.route('/handshake/<uid>')
def handshake(uid):
    if db_check_key(uid) is not None:
        return jsonify({
            'result': 1,
            'client_id': app.config['S_CLIENT_ID'],
            'client_secret': app.config['S_CLIENT_SECRET'],
        })
    return jsonify({'result': 0, 'message': 'Invalid handshake UUID.'})
