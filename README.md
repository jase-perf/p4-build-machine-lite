# P4 Build Machine Lite

Turn a spare computer into your team's build machine. It watches your Perforce (P4) stream, and when someone submits, it makes a playable build of the game and puts it on a web page anyone on the team can download from.

It's one Python file you can read in one sitting, and there's nothing to install but Python and P4. It's for indie teams, solo projects and game jams: the point where "we should really have builds" is true, but a full build system like Jenkins, TeamCity or Horde is more than you want to run.

## What it does

Every build is the same steps, the ones you'd do by hand:

1. It notices there's something new to build.
2. It syncs its own P4 workspace to that change. Its own, so it never touches your work in progress.
3. It throws away anything left over from the last build.
4. It runs `build.bat` (or `build.sh`) from your project — the same file you can run yourself.
5. It zips whatever your script produced.
6. It shows the result on a page at `http://<that-computer>:8765`: passed or failed, who submitted what, the log, and a **Download the newest good build** link.

## What it doesn't do

- **One computer, one stream, one build at a time.** More requests wait their turn.
- **No accounts and no permissions.** Anyone who can reach the page can start a build and download what's there, so keep it on a network you trust.
- **No cloud, no Mac builds from a Windows PC.** It builds what the computer it runs on can build.
- **It doesn't test your game.** It checks that the build finishes, and the example scripts also start the game for a few seconds to catch the kind of break that still "builds fine".
- **It doesn't stop anyone submitting broken code.** It tells you quickly that someone did.
- **It doesn't install itself.** It's a program you start in a terminal and stop with Ctrl+C. Reboot the computer and someone has to start it again.
- **It keeps the last 20 builds** and deletes older ones, except the newest good build of each kind, which it always keeps.

## The two kinds of build

| | Test build | Release build |
|---|---|---|
| **Happens** | by itself, whenever something is submitted | when you ask for it: the **Release build** button |
| **Speed** | quick — it keeps the engine's cache between builds | slower — it deletes everything first and starts over |
| **What you get** | the game with its debug tools on, for playing today | the game the way players get it |
| **Download** | the **Download the newest good build** link | the **Download the newest release build** link, or `/latest-release` |

Both kinds run the same script from your project. It's told which one to make in `BUILD_KIND`, and the examples switch their engine's flags on it. Either kind counts as having built that change, so after a release build of change 42 the build machine won't build 42 again on its own.

`/latest` always points at the newest build that passed, whichever kind it is. `/latest-release` only ever points at a release build.

The clean-out before a release build is thorough: it deletes everything in the build machine's workspace that isn't in P4, including the engine caches your `.p4ignore` lists, and it follows any folder you've linked into that workspace. That's the point — nothing an earlier build left behind can end up in a build you hand to players — so don't keep or link anything you care about inside that folder.

## What you need

- **A computer that can already build your game** (the engine installed, and signed in if your engine asks for that) and that stays on while people are working.
- **Python 3.9 or newer** and the **p4 command line**, both on that computer.

## Setup (about 10 minutes)

1. **Put a build script in your project** and submit it. Copy the contents of one of the example folders — [Godot](examples/godot), [Unity](examples/unity), [Unreal](examples/unreal) — into the folder that holds your project file (`project.godot`, `Assets/`, or `*.uproject`), keeping the layout they're in. **Submit the `.p4ignore` too**, if your project doesn't have one yet: the build machine reads it from its own copy of your project, so one that only exists on your PC does nothing for it.
2. **Copy `build_machine.py`** to the computer that will do the builds, into a folder of its own.
3. **Edit the settings** at the top of `build_machine.py`. At minimum set `NAME` and `STREAM`.
4. **Check P4 works** in a terminal on that computer: `p4 info`, then `p4 login` if it asks for a password. If your server address starts with `ssl:`, run `p4 trust` first, once. The build machine uses your normal P4 connection and your P4 user. It creates a workspace of its own (one of the free tier's 20) and doesn't need its own user.
5. **Run it:** `py build_machine.py` on Windows (plain `python` there can be a Microsoft Store shortcut), or `python3 build_machine.py` on macOS and Linux. Allow it through the firewall if asked.
6. **Open** `http://<that-computer>:8765`. The first build starts within a minute.

That's the whole setup. Everything below is optional.

## What starts a build

| How | What happens | Needs |
|---|---|---|
| By itself | Built in: every 60 s it asks P4 whether anything new was submitted, and builds it | Nothing. Works anywhere, because the build machine only makes outgoing connections |
| Straight after a submit | A P4 trigger tells the build machine the moment someone submits | Super access to `p4 triggers`, and the P4 server must be able to reach this computer |
| Every code review | P4 Code Review asks for a build of each review, and shows pass or fail on it | Code Review and this computer must be able to reach each other |
| By hand | The **Build now** and **Release build** buttons on the page, or `curl -X POST http://HOST:8765/build` | Nothing |

Asking P4 every minute is enough on its own, and it's what makes this work on any network. The other two start builds sooner, and reviews get an answer without anyone asking.

In the steps below, `BUILD-PC` means this computer's name or address as your P4 server and Code Review see it. If they run in containers on the same computer, it's a special name instead; see [If P4 and Code Review run in containers](#if-p4-and-code-review-run-in-containers).

### Optional: build straight after every submit

A trigger is a command your P4 server runs when something happens. This one tells the build machine there's a new change, so a build starts in seconds instead of within a minute.

As a P4 super user, run `p4 triggers` and add one line (put your stream and host in, and add `&token=...` if you set `TOKEN`):

```
	buildmachine change-commit //project/main/... "curl -s -m 5 -X POST http://BUILD-PC:8765/build?reason=p4-trigger"
```

Whoever submits sees `Build queued: http://BUILD-PC:8765` right under `Change N submitted.` If the build machine is off, they'll see `'buildmachine' validation failed` instead. Their submit still went in, and the build machine catches up on its own when it's back.

### Optional: test every review in P4 Code Review

P4 Code Review can hand each review to the build machine and show the answer on the review, so nobody has to remember to try it.

1. **Set `CODE_REVIEW_URL`** in the settings to Code Review's address as this computer reaches it (with p4-server-docker on the same computer, that's `http://localhost:8080`). Results are only ever sent there.
2. **Make sure a Code Review project covers your stream:** a project with a branch whose path is your stream, e.g. `//project/main/...`. In our testing with Code Review 2026.3, a shelf in a stream only became a review once a project covered it.
3. **Add a test** in Code Review and attach it to a workflow (workflows have to be enabled there to use tests):
   - **URL:** `http://BUILD-PC:8765/build`
   - **Body** (URL encoded): `change={change}&status={status}&update={update}` (add `&token=...` if you set `TOKEN`)

Each review's shelved files are put on top of the newest code and merged with anything submitted to those same files since, the way P4 would do it at submit. If it can't merge cleanly, the test fails with "Resolve and shelve again". After the build, the shelved files are put back straight away, so they don't hold locks your teammates need. The review shows running, then pass or fail, with a link to the log.

If a review's test fails with "There was no response from http://…/build", Code Review couldn't reach the build machine at that address.

### If P4 and Code Review run in containers

That's how [p4-server-docker](https://github.com/jase-perf/p4-server-docker) runs them. The trigger and Code Review's test then call the build machine from inside a container, so `BUILD-PC` has to name your computer as the container sees it:

- **Docker Desktop:** use `host.docker.internal`, e.g. `http://host.docker.internal:8765/build`. Both the trigger and Code Review tests worked this way in our testing.
- **Podman:** in our testing on Windows, containers couldn't reach programs running on the Windows computer at all (Podman 5.5, rootless, with WSL's mirrored networking), so the trigger and Code Review tests can't reach the build machine. Leave it building by itself, which works, or use Docker Desktop if you want instant builds and Code Review results.

Don't run Docker Desktop and Podman at the same time on Windows. Podman takes over the connection Docker uses, and Docker Desktop crashed on start while Podman was running.

### Optional: Discord

Set `WEBHOOK_URL` to a Discord channel webhook, and every pass or fail is posted there with a link to the page.

## Your build script's side of the deal

The build machine runs your script in its own folder, with four environment variables:

| Variable | What it is |
|---|---|
| `BUILD_OUTPUT` | An empty folder. Put the playable game here, and it becomes the downloadable zip. |
| `BUILD_CHANGE` | The changelist being built |
| `BUILD_NUMBER` | This build's number |
| `BUILD_KIND` | `test` or `release` — see [the two kinds of build](#the-two-kinds-of-build) |

Exit with `0` and the build passes. Anything else and it fails.

The examples do two things: build the game, then run it for a few seconds and fail if it crashed or printed an error. The second step matters. Godot and Unity both report a successful build for a game that breaks as soon as it runs, so the only way to know a build works is to run it.

Godot needs one extra step for a release build, and it's worth understanding if you write your own script. A Godot release export prints no script errors at all, so the smoke test that catches them has to run a debug export. The example therefore exports debug, runs it, and only then exports the release copy — and starts that one too, which at least proves the copy people download runs.

Before every build, the build machine puts its workspace back to exactly what's in P4, but leaves alone whatever your `.p4ignore` lists. Ignore your engine's caches (`.godot/`, `Library/`, `Intermediate/`, `Saved/`, `DerivedDataCache/`) and builds stay fast. A release build deletes those too, so it starts from nothing.

## Things that will bite you

- **P4 tickets expire after 12 hours by default.** Run the build machine over a weekend jam, or just leave it on overnight, and the ticket runs out. When it does, the status page shows a red *Problem* banner. Run `p4 login` on the build machine, or put your user in a P4 group with a longer `Timeout`.
- **Godot:** install the export templates on the build machine, submit `export_presets.cfg`, and submit the `.uid` files Godot 4.4+ creates next to your scripts.
- **Unity:** batch mode needs a signed-in Editor on the build machine, so sign into Unity Hub there first. A Unity Personal license works. Signed out, the build stops with exit code 198 and "No valid Unity Editor license found". `BuildScript.cs` has to stay in `Assets/Editor/` — Unity won't run it anywhere else — and submit the `.meta` files Unity makes next to both scripts.
- **Unreal:** Blueprint-only projects package as they are. C++ projects also need Visual Studio on the build machine. A release build packages Shipping, so the game inside is `UnrealGame-Win64-Shipping.exe` where a test build has `UnrealGame.exe`; a launcher script that names one won't find the other.
- **A release build takes much longer than a test build.** It deletes the engine's cache, so the engine re-imports every asset: a few seconds more on a small Godot project, many minutes on a real Unity or Unreal one. That's why it isn't what happens on every submit.

## When you've outgrown it

This is one computer building one stream, one build at a time. Once you need several build machines, builds for several platforms at once, or permissions per project, move to a full CI system — the kind that runs as a service, with its own accounts, agents and history. For P4 teams, the usual next steps are:

- **TeamCity.** The free Professional edition includes 3 build agents and up to 100 build configurations, and it builds shelved changelists much the same way this does: unshelve, sync, `resolve -am`, build, revert.
- **Jenkins with the P4 plugin.** It's free and documented on Perforce's help site, and its review builds report back to P4 Code Review 2024.4 or later.
- **Horde,** Epic's build system, if you're on Unreal Engine 5.4 or later with P4 streams.

Your build script, your `.p4ignore` and your streams all carry over.

## Security

Anyone who can reach this computer's port can read the status page, the logs and the zips, so run it on a network you trust. Set `TOKEN` to stop strangers starting builds, especially on shared Wi‑Fi like a jam venue's or a coworking space's. Anyone who can submit or shelve can change the build script, and the build machine runs that script: the same trust any CI system places in the people who can commit.

## Verified with

Windows 11, Python 3.13, Godot 4.7.2, Unity 6000.3 (Personal), and Unreal Engine 5.7 (Blueprint project). Both kinds of build ran through the build machine end to end for Godot and Unity, including a runtime bug that turned the build red and the fix that turned it green. The Godot `build.sh` was run on Ubuntu under WSL.

P4 2025.x, and P4 2026.1 with P4 Code Review 2026.3 from [p4-server-docker](https://github.com/jase-perf/p4-server-docker) (SSL, security level 4). Under Docker Desktop, a trigger and a real Code Review test both reached the build machine. A review built green, a broken review failed, and both results showed on the review.

Not yet tested: a real Discord webhook, and `build_machine.py` itself on macOS or Linux.

## License

MIT. See [LICENSE](LICENSE).
