import os
import sys
import sqlite3
import logging

from config import Config
from flask import Flask, Blueprint, g
from flask_httpauth import HTTPBasicAuth
from logging.handlers import RotatingFileHandler

# "app" package variables defined here
app = Flask(__name__) # main Flask object
app.config.from_object(Config)
auth = HTTPBasicAuth()
profile = Blueprint('profile', __name__, template_folder='templates', static_folder='static')
app.register_blueprint(profile)

# Path definitions
ROOT_PATH = os.getcwd()
APP_PATH = os.path.join(ROOT_PATH, 'app')
STATIC_PATH = os.path.join(APP_PATH, 'static')
DB_PATH = os.path.join(ROOT_PATH, 'users.db')
SCHEMA_PATH = os.path.join(ROOT_PATH, 'schema.sql')

CLIENT_CREDS = {}

def save_pid():
    pid = os.getpid()
    with open('.pid', 'w') as f:
        f.write(f'{pid}\n')

def get_db():
    # binds 'db' object to Flask's global 'g' variable, preserving state across
    # multiple threads
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
# function fired before appcontext is closed (application halts)
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource(SCHEMA_PATH, mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

def query_db(query, args=(), one=False, commit=False):
    '''
    Usage examples:

    for user in query_db('select * from users'):
        print(f"{user['username']} has the id {user['user_id']}")

    user = query_db('select * from users where username = ?', [target_username], one=True)
    if user is None:
        print('No such user')
    else:
        print(f'{user} found')
    '''
    cur = get_db().execute(query, args)
    if commit:
        get_db().commit()
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

from app import routes, utils, manager

def init():
    l_handler = RotatingFileHandler('access.log', maxBytes=10000, backupCount=3)
    logger = logging.getLogger(__name__)
    logger.addHandler(l_handler)

    init_db()
    utils.bind_logger(logger)
    utils.bind_query_func(query_db)
    utils.init_client(app.config['S_CLIENT_ID'], app.config['S_CLIENT_SECRET'])
