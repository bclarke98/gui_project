# Q-Tify Pre-reqs
- Python version >= 3.6.0
- Install Python dependencies with the command:
```
pip install -r requirements.txt
```
- Replace placeholder values in `config.py` with your Spotify API credentials
- Replace `localhost:5000` value with your registered Spotify API callback URI or register it as your callback URI
- Optionally set up `uwsgi` using `queue.ini` to create UNIX socket to use with reverse proxy of your choice
- If not using `uwsgi`, simply run `python main.py`
- Load associated URI in web browser to access your instance of the service
