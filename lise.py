import pyglet
import logging
from util import enableLogging
from gui import GameWindow
from database import load_game
from state import GameState
from sys import argv
from sqlite3 import connect, DatabaseError

DEBUG = False

i = 0
lang = "English"
dbfn = "default.sqlite"
for arg in argv:
    if arg == "-l":
        try:
            lang = argv[i+1]
        except:
            raise Exception("Couldn't parse language")
    elif arg == "-d":
        DEBUG = True
    elif arg[-2:] != "py":
        try:
            connect(arg).cursor().execute("SHOW TABLES")
            dbfn = arg
        except DatabaseError:
            print "Couldn't connect to the database named {0}.".format(arg)
    i += 1

print "Connecting to the database named {0}.".format(dbfn)

db = load_game(dbfn, lang)
s = GameState(db)
gw = GameWindow(s, "Physical")
if DEBUG:
    enableLogging()
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(s.logfmt)
    ch.setFormatter(formatter)
    statelogger = logging.getLogger('state.update')
    statelogger.setLevel(logging.DEBUG)
    statelogger.addHandler(ch)
pyglet.clock.schedule_interval(s.update, 1/60., 1/60.)
pyglet.app.run()
