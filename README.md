# P4 Build Machine Lite

Turns a spare computer into your team's build machine. When someone submits to P4, it builds the game and puts it on a web page your team can download from.

For indie teams, solo devs and game jams that don't need Jenkins, TeamCity or Horde. It's one Python file.

## Setup

You need a computer that can build your game, with Python 3.9+ and the p4 command line (P4 CLI, from perforce.com).

1. **Add a build script to your project.** Copy an example folder's contents into your project's top folder (the one with `project.godot`, `Assets` or the `.uproject`), and submit them, `.p4ignore` included (merge it into yours if you have one): [Godot](examples/godot) · [Unity](examples/unity) · [Unreal](examples/unreal)
2. **Start the build machine** on the build computer. Put `build_machine.py` in a folder of its own and run `py build_machine.py` (Windows) or `python3 build_machine.py` (macOS, Linux). If Windows asks, allow it through the firewall, for private and public networks, so teammates can reach it.
3. **Fill in `build-machine.ini`**, which the first run creates. Set `stream`, and `project_folder` if your project is in a folder of the stream. If the p4 command isn't set up for your server, set `server` and `user` too. Then start it again: it reads the file only when it starts.
4. **Open the team link it shows**, and share it only with your team: anyone with it can start builds.

If P4 needs you to trust the server or log in, the build machine asks in its window. The first build starts within a minute.

## Using it

- **Builds start by themselves** within a minute of each submit.
- **Build now** builds the newest change straight away.
- **Release build** starts from scratch and makes the version players get. It's slower.
- **Download** gets any build that passed. The link at the top (`/latest`) always gets the newest.

Anyone who can reach the page can watch and download. Starting builds needs the team link, or the token it contains.

## Playing a build

Send this to your team:

1. Click **Download** on the build machine's page.
2. Unzip it (on Windows, right-click › **Extract All**). Don't run the game from inside the zip.
3. Run the game's `.exe`.
4. If Windows says it protected your PC, click **More info**, then **Run anyway**. The game just isn't signed.

## Build scripts

The build machine runs `build.bat` (Windows) or `build.sh` (macOS, Linux) in the script's own folder, with these set:

| | |
|---|---|
| `BUILD_OUTPUT` | An empty folder. What you put here becomes the download. |
| `BUILD_KIND` | `test` or `release` |
| `BUILD_CHANGE` | The changelist being built |
| `BUILD_NUMBER` | The build's number |

Exit with `0` to pass. The Godot and Unity examples also run the game for a few seconds and fail if it crashes or logs an error: both engines report success for games that break the moment they start.

Before each build, the workspace is reset to match P4, except what your `.p4ignore` lists. Ignore your engine's cache folders and test builds stay fast. Release builds delete those too, and everything else that isn't in P4, so don't keep or link anything in the build machine's `workspace` folder.

## Extras

Below, `BUILD-PC` is the build machine's address as your P4 server sees it, and `TOKEN` is the token it shows when it starts.

### Build the moment someone submits

As a P4 super user, add this line to `p4 triggers`:

```
	buildmachine change-commit //MyGame/main/... "curl -s -m 5 -d reason=p4-trigger -d token=TOKEN http://BUILD-PC:8765/build"
```

Submitters then see `Build queued` after `Change N submitted`. If the build machine is off, they see `'buildmachine' validation failed`, but their submit still goes in.

### Test every review in P4 Code Review

1. Set `code_review_url` in `build-machine.ini`, like `http://localhost:8080`.
2. Make sure a Code Review project has a branch covering your stream, like `//MyGame/main/...`. Without one, stream shelves don't become reviews.
3. Add a test to a workflow, with URL `http://BUILD-PC:8765/build` and this body, URL encoded: `change={change}&status={status}&update={update}&token=TOKEN`

Each review is built with the newest code merged in, and shows pass or fail with a link to the log. "There was no response" means Code Review couldn't reach `BUILD-PC`.

### P4 in containers

For [p4-server-docker](https://github.com/jase-perf/p4-server-docker) and similar:

- **Docker Desktop:** use `host.docker.internal` as `BUILD-PC`.
- **Podman on Windows:** containers can't reach the build machine, so skip the trigger and the Code Review test. Builds still start by themselves.

Don't run Docker Desktop and Podman at the same time.

### Discord

Set `discord_webhook` in `build-machine.ini` to post each pass or fail to a channel.

## Good to know

- **P4 logins expire,** after 12 hours by default. When the page shows a P4 password problem, restart the build machine and log in there. For a long jam, put its user in a P4 group with a longer `Timeout`.
- **Godot:** install the export templates on the build computer, and submit `export_presets.cfg` and your `.uid` files.
- **Unity:** sign into Unity Hub on the build computer (Personal works). Keep `BuildScript.cs` in `Assets/Editor`, and submit the `.meta` files.
- **Unreal:** C++ projects need Visual Studio on the build computer. Release builds package Shipping, so the game inside is `UnrealGame-Win64-Shipping.exe` rather than `UnrealGame.exe`.

## Limits

One computer, one stream, one build at a time. It keeps the last 20 builds (`keep_builds`), plus the newest good one of each kind. It isn't a service: after a reboot, start it again.

When you outgrow it, the usual next steps for P4 teams are TeamCity (its free edition includes 3 build agents), Jenkins with the P4 plugin, or Horde for Unreal. Your build scripts carry over.

## Security

- Anyone who can reach the page can see and download builds. On shared Wi-Fi, that includes other teams.
- Starting a build needs the token. Like the page, it travels over plain HTTP.
- Browsers send the team link's cookie to every web server on the build computer, whatever the port, so other servers there can read the token.
- If the token leaks, delete `token.txt` and restart, then update the trigger and the Code Review test.
- Anyone who can submit can change the build script, and the build machine runs it.

## Verified with

Windows 11, Python 3.13, Godot 4.7.2, Unity 6000.3, Unreal 5.7, P4 2025.x and 2026.1, and P4 Code Review 2026.3. Godot and Unity ran end to end through the build machine; Unity's release build and Unreal's were run by hand. Not yet tested: Discord, and the build machine itself on macOS or Linux.

## License

MIT. See [LICENSE](LICENSE).
