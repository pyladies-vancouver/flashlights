# PyLadies Vancouver on Flashlights

PyLadies Vancouver's own [Flashlights](https://github.com/mariatta/flashlights)
instance: a meetup group with one edition per year, each meetup's talks as sessions in the venue's room, free and in person, the PyLadies Slack as the chat, and registrations from Luma as a CSV. The public site is <https://vancouver.pyladies.com/>.

This repository holds only what is PyLadies Vancouver's. The core is consumed
as an image, never copied: `Dockerfile` starts `FROM
ghcr.io/mariatta/flashlights:0.2.0` and adds the `flashlights_vancouver` app, which the
core loads through `EXTRA_APPS`. Upgrading the core is a one-line change to
that tag, in a pull request that CI checks against PyLadies Vancouver's own
data. The core's [community apps guide](https://docs.flashlights.app/0.2.0/developer/community_apps/)
is the contract this repository relies on.

## What is here

| Path | What it is |
|---|---|
| `Dockerfile` | The core image plus this repository's app and static files |
| `flashlights_vancouver/` | The Django app: the logo and the share image today; its own pages, models, templates and commands when PyLadies Vancouver needs them |
| `presets/vancouver/` | The demo data (`seed.py`) and branding (`env`) for a local or review instance, loaded with the core's `manage.py load_preset` |
| `compose.yml`, `Makefile` | Run the instance locally from the image, on <http://127.0.0.1:8008/> |
| `app.json`, `heroku.yml` | The Heroku deployment: add-ons, processes, every variable with a description |
| `Procfile` | The same processes for hosts that read one, such as Cabotage |
| `.env.example` | The production variables, with PyLadies Vancouver's values filled in where they are not secrets |
| `docs/runbook.md` | Deploying, upgrading and rolling back |
| `tests/` | The app's tests, run inside the image against the pinned core |

## Run it locally

```sh
make build   # build the image from the pinned core
make seed    # migrate a fresh database and load the PyLadies Vancouver preset
make up      # serve on http://127.0.0.1:8008/
```

Every preset account signs in with the password `password123`; `make seed`
prints the logins. Emails land in maildev at <http://127.0.0.1:9008/>.
`make test` runs the app's tests inside the image, and `make down` stops
everything and drops the database.

## Deploy

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

The button creates the app on Heroku from `app.json` (the button needs the
repository on GitHub; until then the runbook's command line path does the
same). `docs/runbook.md` has the rest: the secrets, the domain, upgrades
and rollback.

## Where a change goes

- Anything another community could use belongs in the core: open an issue
  there, and it arrives as a setting or a feature in a later release.
- PyLadies Vancouver's data, name, colours, links and deployment belong here.
- A need the core cannot meet by configuration is a core
  extension point first (a setting, a signal, a template block), then this
  app uses it. Copying a core template into `flashlights_vancouver/templates/` is the last
  resort, and the [adapting guide](https://docs.flashlights.app/0.2.0/user/adapting/)
  says what a copy costs at upgrade time.

## Upgrading the core

1. Read the core's [changelog](https://github.com/mariatta/flashlights/blob/main/CHANGELOG.md)
   from the current tag to the new one.
2. Change the tag in `Dockerfile` (Dependabot opens this pull request when
   a new core version is published).
3. Let CI build the image, load the preset into a fresh database and run
   the tests against the new core.
4. Merge and deploy; the release step runs the migrations. The runbook has
   the rollback.

## Licence

This repository is under the MIT License, in `LICENSE`, so any community can
copy it as the starting point for its own Flashlights app. The core it runs
on is separate: Flashlights is free software under the GNU Affero General
Public License version 3, with a permission to run a modified copy for your
own events, as its [LICENSE](https://github.com/mariatta/flashlights/blob/main/LICENSE)
says. A running instance combines the two, so the core's licence governs
the instance, and this repository's licence governs only what is here.
