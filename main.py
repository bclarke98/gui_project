#!/usr/bin/env python3
from app import app, init
try:
    import uwsgidecorators

    @uwsgidecorators.postfork
    def preload():
        init()
except Exception as e:
    pass

if __name__ == '__main__':
    init()
    app.run(debug=True)
