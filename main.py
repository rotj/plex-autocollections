#!/usr/bin/env python
import re, sys, getpass
import plexapi.utils
from retry import retry
from plexapi.server import PlexServer, CONFIG
from plexapi.myplex import MyPlexAccount
from plexapi.exceptions import BadRequest
import yaml
import glob, os, argparse
from colorama import init
init() # Support text coloring on Windows

## Edit ##
PLEX_URL = os.getenv('PLEX_URL')
PLEX_TOKEN = os.getenv('PLEX_TOKEN')

DEBUG = os.getenv('DEBUG')
RESET_COLOR = '\033[0m'  # reset to default text color
RED         = '\033[31m' # set text color to red
GREEN       = '\033[32m' # set text color to green
BLUE        = '\033[34m' # set text color to blue

try:
    PLEX_URL = CONFIG.data['auth'].get('server_baseurl', PLEX_URL)
    PLEX_TOKEN = CONFIG.data['auth'].get('server_token', PLEX_TOKEN)
except:
    print("Failed loading in config file.")

class Plex():
    def __init__(self, library=""):
        if PLEX_URL and PLEX_TOKEN:
            self.server = PlexServer(PLEX_URL, PLEX_TOKEN)
        else:
            self.account = self.get_account()
            self.server = self.get_account_server(self.account)

        if library:
            try:
                self.section = self.server.library.section(library)
            except plexapi.exceptions.NotFound:
                self.section = self.get_server_section(self.server)
        else:
            self.section = self.get_server_section(self.server)

        self.media = self.get_flat_media(self.section)

    @retry(BadRequest)
    def get_account(self):
        username = input("Plex Username: ")
        password = getpass.getpass()

        return MyPlexAccount(username, password)

    def get_account_server(self, account):
        servers = [ _ for _ in account.resources() if _.product == 'Plex Media Server' ]
        if not servers:
            print('No available servers.')
            sys.exit()

        return plexapi.utils.choose('Select server index', servers, 'name').connect()

    def get_server_section(self, server):
        sections = [ _ for _ in server.library.sections() if _.type in {'movie'} ]
        if not sections:
            print('No available sections.')
            sys.exit()

        return plexapi.utils.choose('Select section index', sections, 'title')

    def get_flat_media(self, section):
        # Movie sections are already flat
        if section.type == 'movie':
            return self.section.all()
        else:
            episodes = []
            for show in self.section.all():
                episodes += show.episodes()
            return episodes

def process_movies(movies, medium, collection):
    matches = []
    for movie in movies:
        if isinstance(movie, list):
            process_movies(movie, medium, collection)
        else:
            year_regex = None
            for match in re.findall(r"\{\{((?:\s?\d+\s?\|?)+)\}\}", movie):
                year_regex = match.strip()
                movie = re.sub(r"\s+\{\{((\s?\d+\s?\|?)+)\}\}", "", movie)

            regex = re.compile(movie, re.IGNORECASE)
            if re.search(regex, medium.title):
                if year_regex and re.search(year_regex, str(medium.year)):
                    print("Adding" + RED, medium.title, RESET_COLOR + "to collection" + BLUE, collection, RESET_COLOR)
                    matches.append(medium)
                elif year_regex is None:
                    print("Adding" + RED, medium.title, RESET_COLOR + "to collection" + BLUE, collection, RESET_COLOR)
                    matches.append(medium)

    if matches:
        for movie in matches:
            movie.addCollection(collection)

def process_path(paths, medium, collection):
    matches = []
    for path in paths:
        if isinstance(path, list):
            process_path(path, medium, collection)
        else:
            regex = re.compile(re.escape(path), re.IGNORECASE) # Only matches against literal string from yml
            for part in medium.iterParts():
                if re.search(regex, part.file):
                    print("Adding" + RED, medium.title, RESET_COLOR + "to collection" + BLUE, collection, RESET_COLOR)
                    matches.append(medium)

    if matches:
        for movie in matches:
            movie.addCollection(collection)

def process_actor_title(movies, medium, actor, action, thumb, locked):
    matches = []
    for movie in movies:
        if isinstance(movie, list):
            process_movies(movie, medium, actor, action)
        else:
            year_regex = None
            for match in re.findall(r"\{\{((?:\s?\d+\s?\|?)+)\}\}", movie):
                year_regex = match.strip()
                movie = re.sub(r"\s+\{\{((\s?\d+\s?\|?)+)\}\}", "", movie)

            regex = re.compile(movie, re.IGNORECASE)
            if re.search(regex, medium.title):
                if year_regex and re.search(year_regex, str(medium.year)):
                    if (action == "Add"):
                        print("Adding actor" + GREEN, actor, RESET_COLOR + "to movie" + RED, medium.title, RESET_COLOR)
                    elif (action == "Remove"):
                        print("Removing actor" + GREEN, actor, RESET_COLOR + "from movie" + RED, medium.title, RESET_COLOR)
                    matches.append(medium)
                elif year_regex is None:
                    if (action == "Add"):
                        print("Adding actor" + GREEN, actor, RESET_COLOR + "to movie" + RED, medium.title, RESET_COLOR)
                    elif (action == "Remove"):
                        print("Removing actor" + GREEN, actor, RESET_COLOR + "from movie" + RED, medium.title, RESET_COLOR)
                    matches.append(medium)

    if matches:
        for movie in matches:
            if (action == "Add"):
                movie._edit_tags(tag="actor", items=[actor], locked=locked)
            elif (action == "Remove"):
                movie._edit_tags(tag="actor", items=[actor], locked=locked, remove=True)
        if (thumb and action == "Add"):
            edits = {
                'actor[0].tag.tag': ''+actor+'',
                'actor[0].tag.thumb': thumb
            }
            movie.edit(**edits)

def process_actor_path(paths, medium, actor, action, thumb, locked, exclude):
    matches = []
    for path in paths:
        if isinstance(path, list):
            process_path(path, medium, actor)
        else:
            skip = False
            for movie in exclude:
                year_regex = None
                for match in re.findall(r"\{\{((?:\s?\d+\s?\|?)+)\}\}", movie):
                    year_regex = match.strip()
                    movie = re.sub(r"\s+\{\{((\s?\d+\s?\|?)+)\}\}", "", movie)
                exclude_regex = re.compile(movie, re.IGNORECASE)
                if re.search(exclude_regex, medium.title):
                    if year_regex and re.search(year_regex, str(medium.year)):
                        skip = True
                        continue
                    elif year_regex is None:
                        skip = True
                        continue
            if(not skip):
                regex = re.compile(re.escape(path), re.IGNORECASE) # Only matches against literal string from yml
                for part in medium.iterParts():
                    if re.search(regex, part.file):
                        if (action == "Add"):
                            print("Adding actor" + GREEN, actor, RESET_COLOR + "to movie" + RED, medium.title, RESET_COLOR)
                        elif (action == "Remove"):
                            print("Removing actor" + GREEN, actor, RESET_COLOR + "from movie" + RED, medium.title, RESET_COLOR)
                        matches.append(medium)

    if matches:
        for movie in matches:
            if (action == "Add"):
                movie._edit_tags(tag="actor", items=[actor], locked=locked)
            elif (action == "Remove"):
                movie._edit_tags(tag="actor", items=[actor], locked=locked, remove=True)
        if (thumb and action == "Add"):
            edits = {
                'actor[0].tag.tag': ''+actor+'',
                'actor[0].tag.thumb': thumb
            }
            movie.edit(**edits)

def read_collection(filename, collections):
    if ((os.path.isfile(filename) > 0) and (os.path.getsize(filename) > 0)):
        with (open(filename, "r")) as stream:
            collections.update(yaml.load(stream, Loader=yaml.SafeLoader))
            print(GREEN + 'Reading ' + filename + '...' + RESET_COLOR)
            if DEBUG:
                for k, v in collections.items():
                    print(BLUE, k, "->", v, RESET_COLOR)
                print(RED, collections, RESET_COLOR)
    else:
        print()
        print(RED + filename + BLUE, 'is missing or empty. Skipping...' + RESET_COLOR)
        print()

def main():
    parser = argparse.ArgumentParser(description="Automatically create Plex collections")
    parser.add_argument("-l", "--library", help="choose LIBRARY from CLI")
    parser.add_argument("collection", nargs="*", help="Collection YAML files to process")
    args = parser.parse_args()

    if args.library:
        plex = Plex(args.library)
    else:
        plex = Plex()

    print()
    collections = {}        # create empty dictionary
    actors = {}        # create empty dictionary

    if args.collection:
        for i in range(len(args.collection)):
            read_collection(args.collection[i], collections)
    else:
        read_collection('collections.yml', collections)
        custom_collections = glob.glob('collections.d/*.yml')
        custom_actors = glob.glob('actors.d/*.yml')
        for custom_collection in custom_collections:
            read_collection(custom_collection, collections)
        for custom_actor in custom_actors:
            read_collection(custom_actor, actors)

    print()
    # keyword_matches = []  # unused list?

    for medium in plex.media:
        for collection, items, in collections.items():
            if (type(items) is list): # Assume list contains titles if collection has single level list
                process_movies(items, medium, collection)
            elif (type(items) is dict): # Choose processing method if collection has nested lists
                for method, movies in items.items():
                    if (method == "Title"):
                        process_movies(movies, medium, collection)
                    if (method == "Path"):
                        process_path(movies, medium, collection)

        for actor, items, in actors.items():
            if (type(items) is list): # Assume list contains titles if collection has single level list
                process_actor_title(items, medium, actor)
            elif (type(items) is dict): # Choose processing method if collection has nested lists
                if (items.get("Action")):
                    action = items.get("Action")
                else:
                    action = "Add"
                if (items.get("Thumb")):
                    thumb = items.get("Thumb")
                else:
                    thumb = None
                if (items.get("Locked") == False):
                    locked = False
                else:
                    locked = True
                if (type(items.get("Exclude")) is list):
                    exclude = items.get("Exclude")
                else:
                    exclude = []
                for method, movies in items.items():
                    if (method == "Title"):
                        process_actor_title(movies, medium, actor, action, thumb, locked)
                    if (method == "Path"):
                        process_actor_path(movies, medium, actor, action, thumb, locked, exclude)

if __name__ == "__main__":
    main()
