#!/usr/bin/env python3
"""
P4 Build Machine Lite: a build machine for a Perforce (P4) project, in one file.

When someone submits, it syncs its own P4 workspace, runs the build script in your
project (build.bat or build.sh), and puts the result on a web page: pass or fail,
the log, and the game to download. Settings live in build-machine.ini next to this
file; the first run creates it. See README.md.

    Windows:        py build_machine.py
    macOS / Linux:  python3 build_machine.py
"""
import configparser
import ctypes
import hmac
import html
import json
import os
import re
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ---------------------------------------------------------------------------
# Settings come from build-machine.ini (see load_settings). The first run writes
# this template for you to fill in.
# ---------------------------------------------------------------------------
SETTINGS_TEMPLATE = """\
# P4 Build Machine Lite settings. Lines starting with # are notes.
# Restart the build machine after changing them.

# The stream to build, like //MyGame/main
stream =

# The folder in that stream holding build.bat (Windows) or build.sh (macOS, Linux),
# like Game. Leave it empty if they're at the top of the stream.
project_folder =

# Optional settings. To use one, delete its # and change the value.

# Your P4 server and user, if the p4 command doesn't already use them.
# server = ssl:perforce.example.com:1666
# user = me

# Shown on the page and in zip names. Your stream's depot name if not set.
# name = My Game

# The page's port, and how teammates reach it if not http://<this computer>:<port>
# port = 8765
# public_url =

# Seconds between checks for new submits. 0 turns checking off.
# poll_seconds = 60

# The password for starting builds. Made for you in token.txt if not set.
# token =

# P4 Code Review's address, to test every review (see the README).
# code_review_url =

# A Discord channel webhook, to post each pass or fail.
# discord_webhook =

# Settings in capitals go to your build script as environment variables,
# like telling the Godot example where Godot is:
# GODOT = C:\\Godot\\Godot_v4.7.2-stable_win64_console.exe

# The build machine's own P4 workspace (named after this computer if not set),
# how many builds to keep, and how long a build may take.
# workspace = build-machine
# keep_builds = 20
# build_timeout_minutes = 30
"""
STREAM = ""
PROJECT_FOLDER = ""
SERVER = ""
USER = ""
NAME = ""
PORT = 8765
PUBLIC_URL = ""
POLL_SECONDS = 60
TOKEN = ""
CODE_REVIEW_URL = ""
WEBHOOK_URL = ""
WORKSPACE = "build-machine"
KEEP_BUILDS = 20
BUILD_TIMEOUT = 30 * 60            # seconds
MAX_WAITING = 10                   # build requests that can wait at once
BUILD_SCRIPT = "build.bat" if os.name == "nt" else "build.sh"
COOKIE = "build_machine_8765"      # named by port, so two build machines on one PC don't clash
SCRIPT_ENV = {}                    # settings in capitals, for the build script

# A PyInstaller .exe runs from a temporary folder, so its own files go next to the .exe.
HERE = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
SETTINGS_FILE = HERE / "build-machine.ini"
WORKSPACE_DIR = HERE / "workspace"
BUILDS_DIR = HERE / "builds"
TOKEN_FILE = HERE / "token.txt"

token = ""                         # TOKEN, or the one in token.txt (see load_token)
history = []                       # every build started, oldest first (saved in builds/history.json)
queue = []                         # build requests waiting their turn, oldest first
problem = ""                       # the last error, shown on the status page
# Guards the queue. The builder waits on it, and wakes up when a build is requested.
new_request = threading.Condition()


def window_closes_on_exit():
    """Whether this window closes when we exit: on Windows, a double-clicked .py or .exe has a
    console of its own, with only Python (and its launcher) attached. A terminal adds a shell."""
    if os.name != "nt" or not (sys.stdin and sys.stdin.isatty()):
        return False
    return ctypes.windll.kernel32.GetConsoleProcessList((ctypes.c_uint * 4)(), 4) <= 2


def stop(message):
    """Quit with a message, and wait first if the window would close and take it with it."""
    print(message)
    if window_closes_on_exit():
        input("Press Enter to close.")
    raise SystemExit(1)


def load_settings():
    """Read build-machine.ini into the settings above. The first time, write one to fill in."""
    global STREAM, PROJECT_FOLDER, SERVER, USER, NAME, PORT, PUBLIC_URL, POLL_SECONDS, TOKEN
    global CODE_REVIEW_URL, WEBHOOK_URL, WORKSPACE, KEEP_BUILDS, BUILD_TIMEOUT, COOKIE, SCRIPT_ENV
    file = SETTINGS_FILE.name
    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text(SETTINGS_TEMPLATE, encoding="utf-8")
        try:                           # open it: Notepad on Windows, TextEdit on a Mac
            if sys.platform == "darwin":
                subprocess.run(["open", "-t", str(SETTINGS_FILE)])
            else:
                os.startfile(SETTINGS_FILE)
        except (AttributeError, OSError):  # Linux, or nothing opens .ini files
            pass
        stop(f"Created {SETTINGS_FILE}\nSet your stream in it, then start the build machine again.")
    try:
        text = SETTINGS_FILE.read_text("utf-8-sig")
    except UnicodeDecodeError:
        stop(f"Save {file} as UTF-8, then start again.")
    # Strip each line: configparser reads an indented line as more of the setting above, and
    # deleting only the # leaves a space. Blank out [section] lines, then add the one it needs.
    lines = ["" if line.startswith("[") else line for line in map(str.strip, text.splitlines())]
    parser = configparser.ConfigParser(delimiters=("=",), interpolation=None)
    parser.optionxform = str           # keep capitals, for the build script's settings below
    try:
        parser.read_string("\n".join(["[settings]", *lines]))
    except configparser.DuplicateOptionError as error:
        stop(f"{error.option} is set twice in {file}. Keep one.")
    except configparser.ParsingError as error:
        line_number = error.errors[0][0] - 1     # minus the [settings] line added above
        stop(f"Line {line_number} of {file} isn't a setting: {lines[line_number - 1]}\n"
             "Settings look like this: stream = //MyGame/main")
    except configparser.Error as error:
        stop(f"Can't read {file}: {error}")

    def unquote(value):                # name = "My Game" means My Game
        return value[1:-1] if len(value) > 1 and value[0] == value[-1] in "\"'" else value
    everything = {key: unquote(value.strip()) for key, value in parser["settings"].items()}
    known = {"stream", "project_folder", "server", "user", "name", "port", "public_url",
             "poll_seconds", "token", "code_review_url", "discord_webhook", "workspace",
             "keep_builds", "build_timeout_minutes"}
    # Other settings in capitals, like GODOT = C:\Godot\godot.exe, go to the build script as
    # environment variables. The rest are ours, in any case.
    SCRIPT_ENV = {key: value for key, value in everything.items()
                  if key.isupper() and key.lower() not in known}
    values = {key.lower(): value for key, value in everything.items() if key not in SCRIPT_ENV}
    for key in values.keys() - known:
        print(f"Ignoring {key} in {file}: no such setting.")

    def number(key, default, low, high=None):
        text = values.get(key) or str(default)
        if not re.fullmatch(r"[0-9]+", text) or int(text) < low or (high and int(text) > high):
            limits = f"from {low} to {high}" if high else f"{low} or more"
            stop(f"{key} in {file} must be a whole number {limits}, not {text}.")
        return int(text)

    STREAM = values.get("stream", "").rstrip("./")    # also takes //MyGame/main/... from P4V
    if not STREAM:
        stop(f"Set your stream in {SETTINGS_FILE}, like: stream = //MyGame/main")
    folder = values.get("project_folder", "").replace("\\", "/")
    if folder.lower().startswith(STREAM.lower() + "/"):   # its full path, pasted in
        folder = folder[len(STREAM) + 1:]
    if folder.startswith("/") or ":" in folder or ".." in folder.split("/"):
        stop(f"project_folder in {file} is a folder in your stream, like Game, "
             "not a folder on this computer.")
    PROJECT_FOLDER = folder.strip("/")
    SERVER, USER = values.get("server", ""), values.get("user", "")
    NAME = values.get("name") or STREAM.strip("/").split("/")[0]   # //MyGame/main: MyGame
    PORT = number("port", 8765, 1, 65535)
    PUBLIC_URL = (values.get("public_url") or f"http://{socket.gethostname()}:{PORT}").rstrip("/")
    POLL_SECONDS = number("poll_seconds", 60, 0)
    TOKEN = values.get("token", "")
    CODE_REVIEW_URL = values.get("code_review_url", "")
    WEBHOOK_URL = values.get("discord_webhook", "")
    # Named after this computer, so build machines on Windows and a Mac can share a server.
    # Just the first part of the name: a Mac's changes with the network (Name.local, Name.lan).
    WORKSPACE = values.get("workspace") or re.sub(
        r"[^A-Za-z0-9-]+", "-", f"build-machine-{socket.gethostname().split('.')[0]}")
    KEEP_BUILDS = number("keep_builds", 20, 1)
    BUILD_TIMEOUT = number("build_timeout_minutes", 30, 1) * 60
    COOKIE = f"build_machine_{PORT}"


# ---------------------------------------------------------------------------
# P4
# ---------------------------------------------------------------------------
def connection():
    """The server and user from build-machine.ini, as p4 options. Unset, p4 uses its own."""
    return [*(["-p", SERVER] if SERVER else []), *(["-u", USER] if USER else [])]


def p4(*args, stdin=None):
    """Run a p4 command in the build machine's workspace. Raises if P4 reports an error."""
    # net.maxwait: give up if the network goes silent for a minute, instead of hanging forever.
    result = subprocess.run(["p4", *connection(), "-c", WORKSPACE, "-v", "net.maxwait=60", *args],
                            input=stdin, capture_output=True, encoding="utf-8", errors="replace",
                            cwd=HERE)
    if result.returncode != 0:
        raise RuntimeError(f"P4 said: {error_text(result.stderr or result.stdout)}")
    return result.stdout


def connect():
    """Check P4 answers and we're logged in. If P4 needs you to trust its server or type your
    password, it asks here in this window, once each."""
    tried = set()
    while True:
        try:
            p4("login", "-s")          # is there a ticket that still works?
            return
        except FileNotFoundError:
            stop("Can't find the p4 command. Install P4 CLI from perforce.com, "
                 "then start again from a new window.")
        except RuntimeError as error:
            message = str(error)
        fix = ("trust" if "p4 trust" in message else
               "login" if "P4PASSWD" in message or "session has expired" in message else None)
        if fix is None or fix in tried:
            hint = ("If you mistyped the password, start again." if fix == "login" else
                    f"Check server and user in {SETTINGS_FILE.name}.")
            stop(f"Can't start. {message}\n{hint}")
        tried.add(fix)
        print(message)
        subprocess.run(["p4", *connection(), fix], cwd=HERE)   # p4 asks its own questions


def error_text(output):
    """P4's error message in plain words. With -Mj, errors come as JSON too: {"data": "..."}."""
    words = []
    for line in output.strip().splitlines():
        try:
            words.append(json.loads(line)["data"].strip())
        except (ValueError, KeyError, TypeError):
            words.append(line.strip())
    return " ".join(words)


def p4_json(*args):
    """Run a p4 command and get its results as a list of dicts.

    -ztag -Mj makes p4 print one JSON object per result instead of text meant
    for people. Warnings such as "no such file(s)" arrive as objects with a
    "severity" field; those aren't results, so they're dropped.
    """
    records = [json.loads(line) for line in p4("-ztag", "-Mj", *args).splitlines() if line]
    return [record for record in records if "severity" not in record]


def check_workspace():
    """Create the build machine's workspace the first time. After that, make sure it's still ours."""
    spec = p4_json("client", "-o", WORKSPACE)[0]
    if "Update" not in spec:           # P4 has never saved it, so it doesn't exist yet
        # allwrite: build tools sometimes rewrite project files, so let them; "p4 clean"
        # puts every file back before the next build. clobber: let sync replace those files.
        # The other four options are P4's defaults.
        new_spec = p4("--field", f"Root={WORKSPACE_DIR}",
                      "--field", "Options=allwrite clobber nocompress unlocked nomodtime normdir",
                      "client", "-S", STREAM, "-o", WORKSPACE)
        p4("client", "-i", stdin=new_spec)
        print(f"Created workspace {WORKSPACE} for {STREAM} in {WORKSPACE_DIR}")
    elif spec.get("Stream") != STREAM or not same_folder(spec["Root"], WORKSPACE_DIR):
        raise RuntimeError(f"a workspace named {WORKSPACE} already exists for {spec.get('Stream')} "
                           f"in {spec['Root']}. Set another workspace in {SETTINGS_FILE.name}.")


def same_folder(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def newest_change():
    changes = p4_json("changes", "-m1", "-s", "submitted", f"//{WORKSPACE}/...")
    return changes[0]["change"] if changes else None


def describe(change):
    """Who made a change, and the first line of its description."""
    found = p4_json("describe", "-s", change)
    if not found:
        raise RuntimeError(f"change {change} doesn't exist")
    return found[0].get("user", "?"), found[0].get("desc", "").strip().split("\n")[0]


def get_the_code(change, shelved, from_scratch=False):
    """Make the workspace hold exactly what's in P4: a submitted change, or the newest code plus a shelf.

    from_scratch deletes the leftovers too, for a release build.
    """
    everything = f"//{WORKSPACE}/..."
    p4("revert", "-w", everything)     # undo anything a stopped build left open (-w deletes added files)
    # A submitted change is built exactly as submitted. A shelf is tested on top of the newest code.
    p4("sync", "-q", everything if shelved else f"{everything}@{change}")
    # clean: undo edits, delete stray files, restore missing ones. Files your .p4ignore
    # lists (like Godot's .godot/ import cache) are left alone, so builds stay fast.
    # -I means read no .p4ignore, so those caches and the last build's leftovers go too.
    p4("clean", *(["-I"] if from_scratch else []), everything)
    if shelved:
        # Open the shelf's files at the revisions it started from. --bypass-exclusive-lock
        # (undocumented) opens locked (+l) files too, even while the author or another build
        # machine has them open.
        p4("unshelve", "--bypass-exclusive-lock", "-s", change)
        opened = p4_json("opened", everything)
        in_shelf = p4_json("files", f"@={change}")
        if len(opened) < len(in_shelf):
            raise RuntimeError(f"only {len(opened)} of the {len(in_shelf)} files in shelf {change} "
                               f"could be unshelved into {STREAM}")
        # Merge in whatever teammates submitted to those files since, as P4 would at submit.
        # Skip this and a shelf silently undoes their newer work in the build.
        p4("sync", "-q", everything)
        p4("resolve", "-am", everything)
        conflicts = p4_json("resolve", "-n", everything)
        if conflicts:
            raise RuntimeError(f"shelf {change} conflicts with newer changes in {len(conflicts)} "
                               "file(s). Resolve and shelve again.")


# ---------------------------------------------------------------------------
# Build requests and the queue. One build runs at a time. Requests that arrive
# during a build wait, and they collapse: five submits during one build become
# a single build of the newest change, the same batching Jenkins and Horde do.
# ---------------------------------------------------------------------------
def request_build(reason, shelf=None, review_url=None, force=False, kind="test"):
    """Ask for a test or release build of the newest submitted change, or of one shelved change.

    Returns False if too many requests are already waiting.
    """
    with new_request:
        job = None
        for waiting in queue:
            if (waiting["shelf"], waiting["kind"]) == (shelf, kind):  # the same build is waiting: join it
                job = waiting
        if job is None:
            if len(queue) >= MAX_WAITING:
                return False
            job = {"shelf": shelf, "kind": kind, "reason": reason, "review_urls": [], "force": False}
            queue.append(job)
        elif reason not in job["reason"]:
            job["reason"] += f", {reason}"
        if review_url and review_url not in job["review_urls"]:
            job["review_urls"].append(review_url)
        job["force"] = job["force"] or force
        new_request.notify()
        return True


def build_forever():
    while True:
        with new_request:
            while not queue:
                new_request.wait()     # sleep until a build is requested
            job = queue.pop(0)
        try:
            run_build(job)
            set_problem("")
        except Exception as error:     # e.g. P4 is unreachable: say so, then carry on
            set_problem(error)
            for url in job["review_urls"]:
                post_json(url, {"status": "fail", "messages": [f"Build machine problem: {error}"]})


def poll_forever():
    while True:
        try:
            change = newest_change()
            if change and change != last_built_change():
                request_build("new change")
            set_problem("")
        except Exception as error:     # most often an expired P4 ticket: restart to log in
            set_problem(error)
        time.sleep(POLL_SECONDS)


def set_problem(error):
    global problem
    problem = str(error)
    if problem:
        print(f"Problem: {problem}")


# ---------------------------------------------------------------------------
# One build: get the code, run the script, keep the results.
# ---------------------------------------------------------------------------
def run_build(job):
    shelved = job["shelf"] is not None
    release = job["kind"] == "release"
    change = job["shelf"] if shelved else newest_change()
    if change is None:
        return                         # nothing has been submitted yet
    if (not shelved and not release and change == last_built_change()
            and not job["force"] and not job["review_urls"]):
        return                         # already built, and nobody is waiting on an answer

    user, desc = describe(change)
    number = history[-1]["number"] + 1 if history else 1
    folder = BUILDS_DIR / str(number)
    output = folder / "output"
    output.mkdir(parents=True, exist_ok=True)
    build = {"number": number, "change": change, "shelved": shelved, "kind": job["kind"],
             "user": user, "desc": desc,
             "reason": job["reason"], "result": "running", "started": time.time(),
             "seconds": None, "zip": None}
    history.append(build)
    save_history()
    notify(build, job["review_urls"])

    with open(folder / "log.txt", "wb") as log:
        def say(text):
            log.write(f"== {text}\n".encode())
            log.flush()

        passed = False
        try:
            say(f"Build {number}: {job['kind']} build of {'shelved' if shelved else 'submitted'} "
                f"change {change} by {user}")
            get_the_code(change, shelved, from_scratch=release)
            say(f"Running {script_name()}")
            code = run_script(output, change, number, job["kind"], log)
            say(f"{script_name()} exited with code {code}")
            passed = code == 0
            if passed and any(output.iterdir()):
                safe_name = re.sub(r"[^\w.-]+", "-", NAME).strip("-") or "game"  # a file name
                zip_name = f"{safe_name}-{'release-' if release else ''}{'shelf' if shelved else 'cl'}{change}"
                zip_folder(output, folder / f"{zip_name}.zip")
                build["zip"] = zip_name + ".zip"
                build["zip_bytes"] = (folder / build["zip"]).stat().st_size
        except Exception as error:
            say(f"ERROR: {error}")
        finally:
            shutil.rmtree(output, ignore_errors=True)   # the zip holds it all; don't keep it twice
            if shelved:                # revert now: unshelved files hold locks teammates may need
                try:
                    p4("revert", "-w", f"//{WORKSPACE}/...")
                except RuntimeError as error:
                    say(f"ERROR: {error}")

    build["result"] = "passed" if passed else "failed"
    build["seconds"] = round(time.time() - build["started"])
    save_history()
    delete_old_builds()
    notify(build, job["review_urls"])
    print(f"Build {number} {build['result']} in {build['seconds']}s: change {change} by {user}")


def script_name():
    """The build script's path in the stream: build.bat on Windows, build.sh elsewhere."""
    return f"{PROJECT_FOLDER}/{BUILD_SCRIPT}" if PROJECT_FOLDER else BUILD_SCRIPT


def missing_script():
    """Why the build script wasn't found, and how to fix it. Games often live in a folder of
    the stream, so look for the script anywhere in it. Only suggest a folder, never pick one:
    an Unreal stream with engine source has Build.bat files of its own."""
    try:                               # exact case only: Unreal's own scripts are Build.bat
        folders = [os.path.relpath(os.path.dirname(f["path"]), WORKSPACE_DIR).replace(os.sep, "/")
                   for f in p4_json("have", f"//{WORKSPACE}/.../{BUILD_SCRIPT}")
                   if os.path.basename(f["path"]) == BUILD_SCRIPT]
    except RuntimeError:
        folders = []
    missing = f"There's no {script_name()} in {STREAM}."
    if folders == ["."]:
        return f"{missing} There's one at the top: leave project_folder empty in {SETTINGS_FILE.name}."
    if len(folders) == 1:
        return (f"{missing} There's one in {folders[0]}: set project_folder = {folders[0]} "
                f"in {SETTINGS_FILE.name}.")
    if folders:
        places = ", ".join("the top" if f == "." else f for f in folders[:5])
        return (f"{missing} Found one in each of {places}: set project_folder in "
                f"{SETTINGS_FILE.name} to the one with your game.")
    return f"{missing} Submit your build script, and set project_folder if it's in a folder."


def zip_folder(folder, zip_path):
    """Zip a folder, keeping links as links and programs runnable: a macOS app has links
    inside it, and following them would break its signature ("the app is damaged")."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for root, dirs, files in os.walk(folder):
            for name in dirs + files:
                path = Path(root, name)
                inside = path.relative_to(folder).as_posix()
                if path.is_symlink():
                    link = zipfile.ZipInfo(inside)
                    link.create_system = 3     # Unix, so unzip reads the mode below
                    link.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(link, os.readlink(path))
                elif path.is_file():
                    archive.write(path, inside)


def run_script(output, change, number, kind, log):
    """Run the build script in its own folder. Stop it, and anything it started (like the
    game in a smoke test), if it runs longer than BUILD_TIMEOUT. Returns its exit code."""
    script = WORKSPACE_DIR / PROJECT_FOLDER / BUILD_SCRIPT
    if not script.is_file():
        raise RuntimeError(missing_script())
    command = [str(script)] if os.name == "nt" else ["bash", str(script)]
    env = {**os.environ, **SCRIPT_ENV, "BUILD_OUTPUT": str(output), "BUILD_CHANGE": change,
           "BUILD_NUMBER": str(number), "BUILD_KIND": kind}
    # On macOS/Linux, a new session groups the script with everything it starts, so the
    # timeout can stop them all at once. On Windows, taskkill /T does the same job.
    process = subprocess.Popen(command, cwd=script.parent, env=env, stdout=log,
                               stderr=subprocess.STDOUT, start_new_session=os.name != "nt")
    try:
        return process.wait(timeout=BUILD_TIMEOUT)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        log.write(f"== Stopped: took longer than {BUILD_TIMEOUT} seconds\n".encode())
        return -1


def newest_build(good=False, kind=None):
    """The newest build of a submitted change, or the newest one that passed with a zip.

    kind="release" looks only at release builds.
    """
    for build in reversed(history):
        if not build["shelved"] and (build["zip"] or not good) \
                and (kind is None or build.get("kind", "test") == kind):
            return build
    return None


def last_built_change():
    build = newest_build()
    if build is None or build["result"] == "stopped":
        return None                    # never built, or the build machine quit mid-build: build again
    return build["change"]


def zip_link(build):
    return f"/builds/{build['number']}/{urllib.parse.quote(build['zip'])}"


def delete_old_builds():
    # the newest good build of each kind stays downloadable, however old it is
    keep = [newest_build(good=True, kind="test"), newest_build(good=True, kind="release")]
    for build in history[:-KEEP_BUILDS]:
        if build not in keep:
            shutil.rmtree(BUILDS_DIR / str(build["number"]), ignore_errors=True)


def save_history():
    temp = BUILDS_DIR / "history.tmp"
    temp.write_text(json.dumps(history, indent=1))
    os.replace(temp, BUILDS_DIR / "history.json")  # swap in whole, so a crash can't leave half a file


def load_history():
    path = BUILDS_DIR / "history.json"
    if path.exists():
        history.extend(json.loads(path.read_text()))
    for build in history:
        if build["result"] == "running":
            build["result"] = "stopped"            # the build machine quit in the middle


# ---------------------------------------------------------------------------
# Telling people: P4 Code Review test results, and an optional Discord message.
# ---------------------------------------------------------------------------
def notify(build, review_urls):
    log_url = f"{PUBLIC_URL}/builds/{build['number']}/log.txt"
    status = {"running": "running", "passed": "pass"}.get(build["result"], "fail")  # Code Review's words
    for url in review_urls:
        post_json(url, {"status": status, "url": log_url,
                        "messages": [f"Build {build['number']} {build['result']}"]})
    if WEBHOOK_URL and build["result"] != "running":
        icon = ":white_check_mark:" if build["result"] == "passed" else ":x:"
        what = "Shelf" if build["shelved"] else "Change"
        release = "release " if build.get("kind") == "release" else ""
        post_json(WEBHOOK_URL, {
            "content": f"{icon} {NAME} {release}build {build['number']} {build['result']}: {what} "
                       f"{build['change']} by {build['user']}, \"{build['desc'][:200]}\" {PUBLIC_URL}",
            "allowed_mentions": {"parse": []}})  # a description can't @everyone the server


def post_json(url, data):
    # Discord asks for a User-Agent in this form. Code Review doesn't mind it.
    request = urllib.request.Request(url, json.dumps(data).encode(), method="POST", headers={
        "Content-Type": "application/json", "User-Agent": "DiscordBot (https://github.com/jase-perf/p4-build-machine-lite, 1.0)"})
    try:
        urllib.request.urlopen(request, timeout=10).close()
    except Exception as error:         # print only the host: these URLs contain secret tokens
        print(f"Could not notify {urllib.parse.urlsplit(url).netloc}: {error}")


def is_code_review_url(url):
    ours, theirs = urllib.parse.urlsplit(CODE_REVIEW_URL), urllib.parse.urlsplit(url)
    return bool(CODE_REVIEW_URL) and (theirs.scheme, theirs.netloc) == (ours.scheme, ours.netloc)


# ---------------------------------------------------------------------------
# The web side: build requests (POST /build), the status page, and the files.
# Anyone who can reach the page can look and download. Starting a build needs
# the token: in the request, or in the cookie the team link leaves behind.
# ---------------------------------------------------------------------------
def load_token():
    """TOKEN if you set one. Otherwise the one in token.txt, made the first time."""
    if not TOKEN and (not TOKEN_FILE.exists() or not TOKEN_FILE.read_text("utf-8-sig").strip()):
        # 0o600: on macOS and Linux, only your own account can read it.
        with os.fdopen(os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
            f.write(secrets.token_urlsafe(12) + "\n")
    value = TOKEN or TOKEN_FILE.read_text("utf-8-sig").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,}", value):  # it goes into URLs, a cookie and a trigger line
        stop("The token must be at least 8 letters, digits, - or _. Change token in "
             f"{SETTINGS_FILE.name}, or delete token.txt to get a new one.")
    return value


def token_matches(given):
    # compare_digest is a != that can't be timed. And no token must ever mean "no entry".
    return bool(token) and hmac.compare_digest(given.encode(), token.encode())


class Handler(BaseHTTPRequestHandler):
    timeout = 60                       # drop connections that go quiet, so they can't pile up

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        path = url.path
        if path == "/":
            query = dict(urllib.parse.parse_qsl(url.query))
            if "token" in query and self.has_token(query):
                return self.redirect("/", remember_token=True)  # the team link: remember it, tidy the URL
            self.send(200, status_page(can_build=self.has_token({})), "text/html; charset=utf-8")
        elif path in ("/latest", "/latest-release"):
            kind = "release" if path == "/latest-release" else None
            good = newest_build(good=True, kind=kind)
            if good:
                self.redirect(zip_link(good))
            else:
                self.send(404, "No passing release build yet\n" if kind else "No passing build yet\n")
        elif path.startswith("/builds/"):
            self.send_build_file(path[len("/builds/"):])
        else:
            self.send(404, "Not found\n")

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path != "/build":
            return self.send(404, "Not found\n")
        params = self.read_params()
        change, review_url = params.get("change", ""), params.get("update", "")
        if not self.has_token(params):
            return self.send(403, "Wrong or missing token. The build machine shows it when it starts.\n")
        if change and not re.fullmatch(r"[0-9]{1,10}", change):
            return self.send(400, "change must be a changelist number\n")
        if review_url and not is_code_review_url(review_url):
            return self.send(400, f"update must point at code_review_url in {SETTINGS_FILE.name}\n")

        reason = (params.get("reason") or ("Code Review" if review_url else "request"))[:40]
        kind = "release" if params.get("kind") == "release" else "test"
        if params.get("status") == "shelved":       # Code Review's {status} for a review's shelf
            if not change:
                return self.send(400, "status=shelved needs a change\n")
            queued = request_build(reason, shelf=change, review_url=review_url, kind=kind)
        else:                                        # anything else: build the newest change
            queued = request_build(reason, review_url=review_url, kind=kind,
                                   force=params.get("force") == "1")

        if not queued:
            self.send(503, "Too many builds waiting. Try again soon.\n")
        elif "text/html" in self.headers.get("Accept", ""):
            self.redirect("/", remember_token=True)  # a button: back to the page, token remembered
        else:
            self.send(202, f"Build queued: {PUBLIC_URL}\n")  # the submitter sees this in p4 submit

    def has_token(self, params):
        """Whether the request carries the token, as token=... or in the team link's cookie."""
        if params.get("token"):
            return token_matches(params["token"])
        # Browsers send the cookie with a form posted from any page on this computer, whatever
        # port it's on, so the cookie only counts for requests from this page itself.
        origin = self.headers.get("Origin")
        if origin and origin.lower() != "http://" + self.headers.get("Host", "").lower():
            return False
        cookies = (part.strip().partition("=") for part in self.headers.get("Cookie", "").split(";"))
        return any(name == COOKIE and token_matches(value) for name, _, value in cookies)

    def read_params(self):
        """Parameters from the URL (?a=1&b=2) and from a form-style body, merged."""
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
        length = max(0, min(int(self.headers.get("Content-Length") or 0), 100_000))
        params.update(urllib.parse.parse_qsl(self.rfile.read(length).decode("utf-8", "replace")))
        return params

    def send_build_file(self, rest):
        """Serve a build's log or zip. Only those two names are looked up, so no
        path trick in the URL can reach any other file on this computer."""
        number, _, name = urllib.parse.unquote(rest).partition("/")
        build = next((b for b in history if str(b["number"]) == number), None)
        file = BUILDS_DIR / number / name
        if build is None or name not in ("log.txt", build["zip"]) or not file.is_file():
            return self.send(404, "Not found\n")
        if name == "log.txt":              # Godot prints in color; browsers would show the codes
            return self.send(200, re.sub(r"\x1b\[[0-9;]*m", "", file.read_text("utf-8", "replace")))
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(file.stat().st_size))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(name)}")
        self.end_headers()
        with open(file, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def send(self, code, body, content_type="text/plain; charset=utf-8"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Frame-Options", "DENY")   # no other page can show this one and trick a click
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location, remember_token=False):
        self.send_response(303)
        self.send_header("Location", location)
        if remember_token:             # a cookie, so this browser can press the buttons from now on
            # HttpOnly: scripts can't read it. SameSite=Lax: forms on other websites don't send it.
            self.send_header("Set-Cookie", f"{COOKIE}={token}; Path=/; Max-Age={365 * 24 * 3600}; "
                                           "HttpOnly; SameSite=Lax")
        self.end_headers()

    def log_message(self, *args):
        pass                           # the page checks back every 5 seconds; keep the console quiet


STYLE = """
body { font: 16px system-ui, sans-serif; margin: 2rem auto; max-width: 70rem; padding: 0 1rem; }
.banner { font-size: 1.8rem; font-weight: 700; padding: 1rem 1.25rem; border-radius: 10px;
          color: #fff; background: #57606a; margin: 1rem 0; }
.banner span { display: block; font-size: 1rem; font-weight: 400; }
.passed { background: #1a7f37; } .failed { background: #cf222e; } .running { background: #9a6700; }
table { border-collapse: collapse; width: 100%; }
td, th { text-align: left; padding: .4rem .6rem; border-bottom: 1px solid #d0d7de; }
"""


def megabytes(build):
    """How big a build's zip is, e.g. "34.5 MB", so people know whether to download it now.
    Builds from before the build machine recorded sizes show nothing."""
    return f'{build["zip_bytes"] / 1e6:.1f} MB' if build.get("zip_bytes") else ""


def download_link(url, what, build):
    details = ", ".join(filter(None, [f'change {html.escape(build["change"])}', megabytes(build)]))
    return f'<p><a href="{url}">Download the newest {what}</a> ({details})</p>'


def status_page(can_build):
    e = html.escape                    # e() makes text safe to put inside HTML
    latest, good = newest_build(), newest_build(good=True)
    good_release = newest_build(good=True, kind="release")
    if latest is None:
        label = "No builds yet"
        banner = f'<div class="banner">{label}</div>'
    else:
        label = {"running": "Building", "passed": "Passing", "failed": "Broken"}.get(
            latest["result"], "Stopped")
        banner = (f'<div class="banner {latest["result"]}">{label}: change {e(latest["change"])} '
                  f'by {e(latest["user"])}<span>{e(latest["desc"])}</span></div>')
    if problem:
        banner += (f'<div class="banner failed">Problem: {e(problem)}<span>If P4 wants a password, '
                   'restart the build machine and type it there.</span></div>')
    if good:
        banner += download_link("/latest", "good build", good)
    if good_release and good_release is not good:
        banner += download_link("/latest-release", "release build", good_release)
    if good:
        banner += '<p><small>Unzip it, then run the game. Earlier builds are below.</small></p>'

    waiting = []
    for job in list(queue):
        what = f"shelf {job['shelf']}" if job["shelf"] else "newest change"
        if job["kind"] == "release":
            what = f"release build of {what}"
        waiting.append(f"{what} ({e(job['reason'])})")

    rows = ""
    for b in reversed(history[-KEEP_BUILDS:]):
        files = f'<a href="/builds/{b["number"]}/log.txt">log</a>'
        if b["zip"]:                   # every build that passed can be downloaded, not just the newest
            files = f'<a href="{e(zip_link(b))}">Download</a> {megabytes(b)} · {files}'
        took = "…" if b["seconds"] is None else f'{b["seconds"]}s'
        rows += (f'<tr><td>{b["number"]}</td><td>{b["result"]}</td>'
                 f'<td>{b.get("kind", "test")}</td>'
                 f'<td>{"shelf " if b["shelved"] else ""}{e(b["change"])}</td><td>{e(b["user"])}</td>'
                 f'<td>{e(b["desc"])}</td><td>{e(b["reason"])}</td>'
                 f'<td>{time.strftime("%a %H:%M", time.localtime(b["started"]))}</td>'
                 f'<td>{took}</td><td>{files}</td></tr>')

    # A browser that opened the team link has the token in a cookie. Anyone else types it.
    token_box = "" if can_build else '<input name="token" type="password" placeholder="token"> '
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{label} · {e(NAME)} builds</title><style>{STYLE}</style></head><body>
<h1>{e(NAME)} builds <small>{e(STREAM)}</small></h1>
<form method="post" action="/build"><input type="hidden" name="reason" value="button">
<input type="hidden" name="force" value="1">{token_box}<button>Build now</button>
<button name="kind" value="release">Release build</button></form>
<p><small>{"" if can_build else "To start builds, open the team link from whoever runs the build machine. "}Release builds start
from scratch and make the version players get. They're slower.</small></p>
<p id="offline" hidden><b>Can't reach the build machine. Still trying…</b></p>
<div id="live">{banner}
<p>{"Waiting: " + ", ".join(waiting) if waiting else ""}</p>
<table><tr><th>#</th><th>Result</th><th>Kind</th><th>Change</th><th>Who</th><th>What</th><th>Why</th>
<th>Started</th><th>Took</th><th>Files</th></tr>{rows}</table></div>
<script>  // fetch this page again and swap in just the part that changes: the buttons stay put
async function update() {{
  try {{
    const response = await fetch("/");
    if (!response.ok) throw response.status;
    const page = new DOMParser().parseFromString(await response.text(), "text/html");
    document.getElementById("live").replaceWith(page.getElementById("live"));
    document.title = page.title;
    document.getElementById("offline").hidden = true;
  }} catch {{
    document.getElementById("offline").hidden = false;   // it's stopped, or the network is down
  }}
}}
// Every 5 seconds while someone's looking, and straight away when they come back to the tab.
setInterval(() => {{ if (!document.hidden) update(); }}, 5000);
document.addEventListener("visibilitychange", () => {{ if (!document.hidden) update(); }});
</script>
</body></html>"""


def main():
    global token
    if getattr(sys, "frozen", False):  # a PyInstaller program points what it starts at its own
        if os.name == "nt":            # libraries: undo that for p4, the engines and the script
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        elif "LD_LIBRARY_PATH_ORIG" in os.environ:
            os.environ["LD_LIBRARY_PATH"] = os.environ.pop("LD_LIBRARY_PATH_ORIG")
        else:
            os.environ.pop("LD_LIBRARY_PATH", None)
    # A name or path the console can't show gets escaped instead of crashing. And print each
    # line straight away, even when the output goes to a file.
    sys.stdout.reconfigure(errors="backslashreplace", line_buffering=True)
    load_settings()
    connect()
    BUILDS_DIR.mkdir(exist_ok=True)
    load_history()
    token = load_token()
    try:
        check_workspace()
    except RuntimeError as error:
        stop(f"Can't start: {error}")
    try:
        server = ThreadingHTTPServer(("", PORT), Handler)
    except OSError as error:
        stop(f"Port {PORT} is taken, probably by another program ({error}). "
             f"Set another port in {SETTINGS_FILE.name}.")
    threading.Thread(target=build_forever, daemon=True).start()
    if POLL_SECONDS:
        threading.Thread(target=poll_forever, daemon=True).start()
    print(f"Building {STREAM} at {PUBLIC_URL}. Close this window or press Ctrl+C to stop.\n"
          f"Team link, to start builds too (share it only with your team): {PUBLIC_URL}/?token={token}\n"
          f"Token, for a P4 trigger or Code Review: {token}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    try:
        main()
    except Exception:                  # show what went wrong before a double-clicked window closes
        traceback.print_exc()
        stop("The build machine stopped because of the error above.")
