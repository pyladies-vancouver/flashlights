"""Demo preset: PyLadies Vancouver, from its public site
(https://vancouver.pyladies.com/): a meetup group, one edition per year,
each meetup's talks as sessions in the venue's room. In person, free, no
recordings, the PyLadies Slack as the chat, registrations from Luma as a
CSV. Organizers and speakers as the site lists them; emails are invented
(example.org); volunteers and registrants are made up.

Loaded by ``manage.py load_preset``; kept out of the Flashlights repository
because it is a real community's data. All passwords: password123.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.utils import timezone

from affiliations.models import Affiliation, AffiliationKind
from portal.models import Cadence, ChatPlatform, Conference, EventDate, Venue
from portal_account.handles import adopt_role_handles
from portal_account.models import PortalProfile
from speakers.checklists import complete_item
from speakers.constants import (
    OPEN_ITEM_STATUSES,
    Delivery,
    EventFormat,
    Recordings,
    RoomKind,
)
from speakers.lifecycle import confirm_session_if_ready
from speakers.models import (
    Presenter,
    PublishedSlot,
    Room,
    ScheduleSlot,
    Session,
    SessionPresenter,
    SpeakerSettings,
)
from speakers.program_types import presenter_role, session_type
from speakers.seeds import seed_checklists
from speakers.services import accept_invitation, send_invitation
from ticketing.models import TicketingSettings
from ticketing.sync import import_csv
from volunteer.constants import ApplicationStatus, Region
from volunteer.models import Team, VolunteerProfile
from volunteer.permission_presets import ORGANIZERS as ORGANIZERS_TEAM
from volunteer.permission_presets import PRESETS, permissions_for

PASSWORD = "password123"
VANCOUVER = ZoneInfo("America/Vancouver")
SITE = "https://vancouver.pyladies.com"

VENUES = {
    "Improving Vancouver": "116 West 6th Avenue, Suite 300, Vancouver",
    "VISST": "1490 West Broadway, Vancouver",
    "Northeastern University Vancouver": "410 West Georgia Street, Vancouver",
    "Z-Space Arts + Technology Society": "505 Hamilton St, Suite 301, Vancouver",
}

# year -> [(title, kind, day, start, minutes, venue, summary, [speakers])]
PROGRAM = {
    2025: [
        (
            "Emotion-aware AI in Python",
            "TALK",
            date(2025, 3, 7),
            "18:30",
            40,
            "Northeastern University Vancouver",
            "International Women's Day celebration: building emotion-aware AI "
            "with Python.",
            ["Hazra Imran"],
        ),
        (
            "From Curiosity to Cloud: A Hands-On Python Workshop",
            "WORKSHOP",
            date(2025, 6, 27),
            "18:00",
            120,
            "Z-Space Arts + Technology Society",
            "Deploy a Python app with an LLM integration to the cloud.",
            ["Linda Lee"],
        ),
    ],
    2026: [
        (
            "Durable execution for agents that wait on humans",
            "TALK",
            date(2026, 7, 6),
            "18:30",
            25,
            "Improving Vancouver",
            "July meetup on AI agents and LLMs. Pizza provided.",
            ["Melanie Warrick"],
        ),
        (
            "A practical introduction to generative AI and LLMs",
            "TALK",
            date(2026, 7, 6),
            "19:00",
            25,
            "Improving Vancouver",
            "July meetup on AI agents and LLMs.",
            ["Daniel Chen"],
        ),
        (
            "PyLadies x R-Ladies Vancouver Lightning Talks",
            "LIGHTNING",
            date(2026, 8, 19),
            "18:00",
            90,
            "VISST",
            "Joint lightning talks night with R-Ladies Vancouver: five to "
            "fifteen minutes each.",
            [
                "Daria Linhart Grudzien",
                "Maksym Shalenyi",
                "Sophia Chu",
                "Melissa Bather",
            ],
        ),
    ],
}

ORGANIZERS = [
    # username, first, last, superuser, affiliations
    (
        "mariatta",
        "Mariatta",
        "Wijaya",
        True,
        [(AffiliationKind.PROJECT, "CPython", "https://github.com/python/cpython")],
    ),
    ("eliza", "Eliza", "Sarobhasa", False, []),
]

VOLUNTEERS = [
    # username, first, last, status, team
    ("jen_k", "Jen", "Kwan", ApplicationStatus.APPROVED, "Meetup hosts"),
    ("amira_s", "Amira", "Saleh", ApplicationStatus.APPROVED, "Meetup hosts"),
    ("lucia_m", "Lucia", "Moreno", ApplicationStatus.PENDING, None),
]

REGISTRANTS = """Name,Email,Ticket
Ada Example,ada@example.org,General admission
Bea Example,bea@example.org,General admission
Cleo Example,cleo@example.org,General admission
Melanie Warrick,melanie.warrick@example.org,Speaker
Daniel Chen,daniel.chen@example.org,Speaker
"""

# year -> [(day, label, venue)]: the nights each edition meets.
NIGHTS = {
    2025: [
        (
            date(2025, 3, 7),
            "International Women's Day",
            "Northeastern University Vancouver",
        ),
        (date(2025, 6, 27), "Cloud workshop", "Z-Space Arts + Technology Society"),
    ],
    2026: [
        (date(2026, 7, 6), "July meetup: AI agents and LLMs", "Improving Vancouver"),
        (date(2026, 8, 19), "Lightning talks with R-Ladies", "VISST"),
    ],
    2027: [
        (date(2027, 2, 13), "Open source workshop", "Improving Vancouver"),
    ],
}


def run(stdout):
    organizers = _people(stdout)
    editions = {}
    for year in (2025, 2026, 2027):
        editions[year] = _edition(year, active=(year == 2026))
    for year, items in PROGRAM.items():
        _program(editions[year], items, organizers["mariatta"])
    _upcoming_workshop(editions[2027])
    for year, nights in NIGHTS.items():
        _event_dates(editions[year], nights)
    _volunteering(editions[2026], organizers)
    # The handles typed on the rows above become each person's own record
    # (portal_account.Handle), as the migration does for a live database.
    for user in User.objects.all():
        adopt_role_handles(user)
    ticketing, _ = TicketingSettings.objects.update_or_create(
        conference=editions[2026],
        defaults={
            "provider": "CSV",
            "api_token": "",
            "csv_columns": {"email": "Email", "name": "Name", "product": "Ticket"},
        },
    )
    result = import_csv(ticketing, REGISTRANTS)
    stdout.write(f"Imported {result.imported} Luma registrant(s).")
    stdout.write(
        f"Sign in as mariatta, eliza, jen_k or lucia_m; speakers by email "
        f"local part (melanie.warrick). Password: {PASSWORD}"
    )


def _user(username, first, last, staff=False, superuser=False):
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": first,
            "last_name": last,
            "email": f"{username}@example.org",
            "is_staff": staff,
            "is_superuser": superuser,
        },
    )
    user.set_password(PASSWORD)
    user.save()
    PortalProfile.objects.get_or_create(
        user=user, defaults={"coc_agreement": True, "tos_agreement": True}
    )
    return user


def _people(stdout):
    organizers = {}
    for username, first, last, superuser, rows in ORGANIZERS:
        user = _user(username, first, last, staff=True, superuser=superuser)
        for order, (kind, name, url) in enumerate(rows):
            Affiliation.objects.get_or_create(
                user=user, kind=kind, name=name, defaults={"url": url, "order": order}
            )
        organizers[username] = user
    return organizers


def _edition(year, active):
    edition, _ = Conference.objects.update_or_create(
        year=year,
        defaults={
            "name": f"PyLadies Vancouver {year}",
            "slug": str(year),
            "is_active": active,
            "cadence": Cadence.SERIES,
            "coc_url": "https://www.pyladies.com/CodeOfConduct/",
            "schedule_url": f"{SITE}/events/",
            "chat_platform": ChatPlatform.OTHER,
            "chat_name": "the PyLadies Slack (#city-vancouver)",
            "chat_url": "https://slackin.pyladies.com",
            "volunteer_application_open": active,
            "accepting_donations": False,
            "banner_text": (
                "Next up: Your First Open Source Contribution, a Python "
                "workshop on Saturday, February 13."
                if active
                else ""
            ),
        },
    )
    row, _ = SpeakerSettings.objects.get_or_create(conference=edition)
    row.speaker_module_enabled = True
    row.event_format = EventFormat.IN_PERSON
    row.recordings = Recordings.NONE
    row.conference_timezone = "America/Vancouver"
    row.organizers_email = "vancouver@example.org"
    row.proposals_open = active
    row.proposals_intro_md = (
        "Speak at a meetup: a five-minute lightning talk, a ten-minute talk, "
        "or a conference talk you want to practise. First-time speakers are "
        f"very welcome; see [Speak at our meetup]({SITE}/speak/)."
    )
    row.program_visibility = "PUBLISHED"
    row.save()
    seed_checklists(edition)
    # Only the venues this year's nights use, each with its one room.
    used = {venue for _, _, venue in NIGHTS.get(year, [])}
    for name, address in VENUES.items():
        if name not in used:
            continue
        place, _ = Venue.objects.update_or_create(
            name=name,
            defaults={
                "address": address,
                "url": "https://www.google.com/maps/search/?api=1&query="
                + address.replace(" ", "+"),
            },
        )
        Room.objects.update_or_create(
            conference=edition,
            name=name,
            defaults={"kind": RoomKind.ROOM, "url": place.url, "venue": place},
        )
    return edition


def _event_dates(edition, nights):
    """The year's meetup nights as the edition's event dates, each at its
    own venue, so the schedule editor offers those nights only and each
    night's lanes are the rooms there."""
    for day, label, venue in nights:
        EventDate.objects.update_or_create(
            conference=edition,
            date=day,
            defaults={"label": label, "venue": Venue.objects.get(name=venue)},
        )
    edition.span_from_dates()


def _presenter(edition, name, liaison):
    email = name.lower().replace(" ", ".") + "@example.org"
    presenter, _ = Presenter.objects.get_or_create(
        conference=edition,
        email=email,
        defaults={
            "display_name": name,
            "timezone": "America/Vancouver",
            "liaison": liaison,
            "is_public": True,
        },
    )
    return presenter


def _onboard(presenter, inviter):
    invitation = presenter.invitations.first()
    if invitation is None:
        invitation = presenter.invitations.create(
            message_md="We would love to have you speak at PyLadies Vancouver.",
            invited_by=inviter,
        )
        send_invitation(invitation, actor=inviter)
    if invitation.accepted_at is None:
        accept_invitation(invitation)
        presenter.refresh_from_db()
    if presenter.user_id and not presenter.user.has_usable_password():
        presenter.user.set_password(PASSWORD)
        presenter.user.save()
    PortalProfile.objects.get_or_create(
        user=presenter.user, defaults={"coc_agreement": True, "tos_agreement": True}
    )
    blocking = presenter.checklist_items.filter(
        is_required=True,
        status__in=OPEN_ITEM_STATUSES,
        auto_complete_rule="",
        is_waiting=False,
    )
    for item in blocking:
        complete_item(item, actor=presenter.user)


def _program(edition, items, liaison):
    for title, kind, day, start, minutes, venue, summary, speakers in items:
        session, _ = Session.objects.get_or_create(
            conference=edition,
            title=title,
            defaults={
                "kind": session_type(edition, kind),
                "delivery": Delivery.LIVE,
                "summary_md": summary,
                "language": "en",
                "duration_minutes": minutes,
            },
        )
        for order, name in enumerate(speakers):
            presenter = _presenter(edition, name, liaison)
            SessionPresenter.objects.get_or_create(
                session=session,
                presenter=presenter,
                defaults={
                    "role": presenter_role(edition, "PRESENTER"),
                    "order": order,
                },
            )
            _onboard(presenter, liaison)
        confirm_session_if_ready(session)
        hour, minute = (int(part) for part in start.split(":"))
        start_utc = datetime.combine(day, time(hour, minute), VANCOUVER).astimezone(UTC)
        room = Room.objects.get(conference=edition, name=venue)
        slot, _ = ScheduleSlot.objects.get_or_create(
            session=session,
            defaults={
                "room": room,
                "start_utc": start_utc,
                "end_utc": start_utc + timedelta(minutes=minutes),
            },
        )
        PublishedSlot.objects.get_or_create(
            session=session,
            defaults={
                "room": slot.room,
                "start_utc": slot.start_utc,
                "end_utc": slot.end_utc,
                "published_at": timezone.now(),
            },
        )
        session.refresh_from_db()
        if session.status == "CONFIRMED":
            session.schedule()
        if session.status == "SCHEDULED":
            session.publish()


def _upcoming_workshop(edition):
    Session.objects.get_or_create(
        conference=edition,
        title="Your First Open Source Contribution: A Python Workshop",
        defaults={
            "kind": session_type(edition, "WORKSHOP"),
            "delivery": Delivery.LIVE,
            "summary_md": "A hands-on workshop for beginners, from your first "
            "fork to your first pull request. Saturday, February 13, at "
            "Improving Vancouver.",
            "language": "en",
            "duration_minutes": 180,
        },
    )


def _volunteering(edition, organizers):
    leads = {}
    for username, user in organizers.items():
        leads[username], _ = VolunteerProfile.objects.get_or_create(
            user=user,
            conference=edition,
            defaults={
                "application_status": ApplicationStatus.APPROVED,
                "region": Region.NORTH_AMERICA,
                "availability_hours_per_week": 4,
                "github_username": username,
                "discord_username": username,
            },
        )
    teams = {}
    for name, description, lead in (
        ("Organizers", "Plan the year's meetups, find venues and speakers", "mariatta"),
        ("Meetup hosts", "Run the room on the night", "eliza"),
    ):
        team, _ = Team.objects.get_or_create(
            conference=edition,
            short_name=name,
            defaults={"description": description, "open_to_new_members": True},
        )
        team.team_leads.set([leads[lead]])
        leads[lead].teams.add(team)
        teams[name] = team
    # Access comes from the active edition's teams: both organizers run the
    # chapter's year through the Organizers team; only Mariatta is a
    # superuser.
    organizers_team = teams["Organizers"]
    organizers_team.permissions.set(permissions_for(PRESETS[ORGANIZERS_TEAM].members))
    organizers_team.lead_permissions.set(
        permissions_for(PRESETS[ORGANIZERS_TEAM].leads)
    )
    for profile in leads.values():
        profile.teams.add(organizers_team)
    for username, first, last, status, team in VOLUNTEERS:
        user = _user(username, first, last)
        profile, _ = VolunteerProfile.objects.get_or_create(
            user=user,
            conference=edition,
            defaults={
                "application_status": status,
                "availability_hours_per_week": 2,
                "github_username": username,
                "discord_username": username,
            },
        )
        if team:
            profile.teams.set([teams[team]])
