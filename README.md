# P4 Build Machine Lite

Turn any computer on your team into a build machine for a Perforce (P4) project. It's one Python file with no dependencies that you can read in one sitting, for indie teams, solo projects, game jams, and anything else that wants a playable build after every submit but isn't ready for a full CI system like Jenkins, TeamCity or Horde.

It keeps its own P4 workspace, so it never touches your work in progress. When a build is requested, it gets the code, runs the build script that lives in your project, and shows the result on a status page with a **Download the newest good build** link.

## What starts a build

| How | What happens | Needs |
|---|---|---|
| Polling | Built in: every 60 s it asks P4 whether anything new was submitted | Nothing. Works anywhere, because it only makes outgoing connections |
| P4 trigger | A `change-commit` trigger runs `curl` after each submit | Super access to `p4 triggers`, and the P4 server must be able to reach this computer |
| P4 Code Review | A test definition calls `/build` for each review's shelf and gets pass/fail back | Code Review and this computer must be able to reach each other |
| By hand | The **Build now** button, or `curl -X POST http://HOST:8080/build` | Nothing |

Polling alone is enough. A trigger makes builds start instantly instead of within a minute.

## Setup (about 10 minutes)

1. **Put a build script in your project** and submit it. Copy one from `examples/`: [Godot](examples/godot), [Unity](examples/unity), or [Unreal](examples/unreal). It goes next to your project file (`project.godot`, `Assets/`, or `*.uproject`). Take that folder's `.p4ignore` too, if your project doesn't have one yet.
2. **Copy `build_machine.py`** to the computer that will do the builds, into a folder of its own.
3. **Edit the settings** at the top of `build_machine.py`. At minimum set `NAME` and `STREAM`.
4. **Check P4 works** in a terminal on that computer: `p4 info`, then `p4 login` if it asks for a password. The build machine uses your normal P4 connection and your P4 user. It creates a workspace of its own (one of the free tier's 20) and doesn't need its own user.
5. **Run it:** `py build_machine.py` on Windows (plain `python` there can be a Microsoft Store shortcut), or `python3 build_machine.py` on macOS and Linux. Allow it through the firewall if asked.
6. **Open** `http://<that-computer>:8080`. The first build starts within a minute.

### Optional: build on every submit with a P4 trigger

As a P4 super user, run `p4 triggers` and add one line (put your stream and host in, and add `&token=...` if you set `TOKEN`):

```
	buildmachine change-commit //project/main/... "curl -s -m 5 -X POST http://BUILD-PC:8080/build?reason=p4-trigger"
```

Whoever submits sees `Build queued: http://BUILD-PC:8080` right under `Change N submitted.` If the build machine is off, they'll see `'buildmachine' validation failed` instead. Their submit still went in, and polling catches up when the build machine is back.

The trigger runs on the P4 server's machine. If your P4 server runs in a container, it runs inside the container, so the container needs `curl`, and `BUILD-PC` has to be this computer's address as the container sees it (with Docker Desktop, that's `host.docker.internal`).

### Optional: test every review in P4 Code Review

Set `CODE_REVIEW_URL` in the settings to your Code Review address. Results are only ever sent there. Then add a test in Code Review (workflow has to be enabled there to use tests):

- **URL:** `http://BUILD-PC:8080/build`
- **Body** (URL encoded): `change={change}&status={status}&update={update}` (add `&token=...` if you set `TOKEN`)

Each review's shelf is unshelved on top of the newest code and merged with anything submitted to the same files since, the way P4 would do it at submit. If it can't merge cleanly, the test fails with "Resolve and shelve again". After the build, the shelf is reverted straight away, so unshelved files don't hold locks your teammates need. The review shows running, then pass or fail, with a link to the log.

### Optional: Discord

Set `WEBHOOK_URL` to a Discord channel webhook, and every pass or fail is posted there with a link to the page.

## Your build script's side of the deal

The build machine runs your script in its own folder, with three environment variables:

| Variable | What it is |
|---|---|
| `BUILD_OUTPUT` | An empty folder. Put the playable game here, and it becomes the downloadable zip. |
| `BUILD_CHANGE` | The changelist being built |
| `BUILD_NUMBER` | This build's number |

Exit with `0` and the build passes. Anything else and it fails. The examples do two things: export the game, then run it for a few seconds and fail if it crashed or printed an error. The second step matters. Godot and Unity both report a successful build for a game that breaks as soon as it runs, so the only way to know a build works is to run it.

Before every build, the build machine resets its workspace to exactly what's in P4 (`p4 clean`), but leaves alone anything your `.p4ignore` lists. Ignore your engine's caches (`.godot/`, `Library/`, `Intermediate/`, `Saved/`, `DerivedDataCache/`) and builds stay fast.

## Things that will bite you

- **P4 tickets expire after 12 hours by default.** Run the build machine over a weekend jam, or just leave it on overnight, and the ticket runs out. When it does, the status page shows a red *Problem* banner. Run `p4 login` on the build machine, or put your user in a P4 group with a longer `Timeout`.
- **Godot:** install the export templates on the build machine, submit `export_presets.cfg`, and submit the `.uid` files Godot 4.4+ creates next to your scripts.
- **Unity:** batch mode needs a signed-in Editor on the build machine, so sign into Unity Hub there first. A Unity Personal license works. Signed out, the build stops with exit code 198 and "No valid Unity Editor license found". Also put `SmokeTest.cs` from the example anywhere under `Assets/`.
- **Unreal:** Blueprint-only projects package as they are. C++ projects also need Visual Studio on the build machine.

## When you've outgrown it

This is one computer building one stream, one build at a time. Once you need several build machines, builds for many platforms in parallel, or permissions per project, move to a full CI system. For P4 teams, the usual next steps are:

- **TeamCity.** The free Professional edition includes 3 build agents and up to 100 build configurations, and it builds shelved changelists much the same way this does: unshelve, sync, `resolve -am`, build, revert.
- **Jenkins with the P4 plugin.** It's free and documented on Perforce's help site, and its review builds report back to P4 Code Review 2024.4 or later.
- **Horde,** Epic's build system, if you're on Unreal Engine 5.4 or later with P4 streams.

Your build script, your `.p4ignore` and your streams all carry over.

## Security

Anyone who can reach this computer's port can read the status page, the logs and the zips, so run it on a network you trust. Set `TOKEN` to stop strangers starting builds, especially on shared Wi‑Fi like a jam venue's or a coworking space's. Anyone who can submit or shelve can change the build script, and the build machine runs that script: the same trust any CI system places in the people who can commit.

## Verified with

Windows 11, Python 3.13, P4 2025.x, Godot 4.7.2, Unity 6000.3 (Personal), and Unreal Engine 5.7 (Blueprint project). The Godot and Unity examples ran through the build machine end to end, including a runtime bug that turned the build red and the fix that turned it green. The Godot `build.sh` was run on Ubuntu under WSL.

Not yet tested: a real Discord webhook, and a real P4 Code Review instance. The Code Review path was tested against a stand-in that records the callbacks, using the parameters and result format from Code Review's documentation. `build_machine.py` itself has only been run on Windows.

## License

MIT. See [LICENSE](LICENSE).
