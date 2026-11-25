#!/usr/bin/env python3
"""Fetch GitHub's public contribution calendar and sponsors, then render every profile SVG."""
import argparse
import json
import os
import re
import sys
import time
import tomllib
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def load_config():
    return tomllib.loads((ROOT / "profile.toml").read_text(encoding="utf-8"))


class CalendarParser(HTMLParser):
    """Reads the cells and tooltips of https://github.com/users/<name>/contributions."""

    def __init__(self):
        super().__init__()
        self.cells = {}
        self.tips = {}
        self.tip_id = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "data-date" in attrs and "data-level" in attrs:
            self.cells[attrs["id"]] = {"date": attrs["data-date"], "level": int(attrs["data-level"])}
        if tag == "tool-tip":
            self.tip_id = attrs.get("for")
            if self.tip_id:
                self.tips[self.tip_id] = ""

    def handle_data(self, data):
        if self.tip_id:
            self.tips[self.tip_id] += data

    def handle_endtag(self, tag):
        if tag == "tool-tip":
            self.tip_id = None

    def days(self, as_of):
        result = []
        for key, cell in self.cells.items():
            if not f"{as_of.year}-01-01" <= cell["date"] <= as_of.isoformat():
                continue
            tip = self.tips.get(key, "").strip()
            match = re.match(r"([\d,]+) contributions?\b", tip)
            if match:
                count = int(match[1].replace(",", ""))
            elif tip.startswith("No contributions"):
                count = 0
            else:
                raise ValueError(f"Missing or unrecognized contribution tooltip: {cell['date']}")
            if bool(count) != bool(cell["level"]):
                raise ValueError(f"Contribution level/count mismatch: {cell['date']}")
            result.append(dict(cell, count=count))
        result.sort(key=lambda d: d["date"])
        expected = (as_of - date(as_of.year, 1, 1)).days + 1
        if len(result) != expected or len({d["date"] for d in result}) != expected:
            raise ValueError(f"Incomplete calendar: expected {expected} unique dates, got {len(result)}")
        return result


def summarize(days):
    run = longest = 0
    longest_end = None
    for day in days:
        run = run + 1 if day["count"] else 0
        if run > longest:
            longest, longest_end = run, day["date"]
    # A day still in progress does not break yesterday's streak.
    active = days if days[-1]["count"] else days[:-1]
    current = 0
    for day in reversed(active):
        if not day["count"]:
            break
        current += 1
    end = date.fromisoformat(active[-1]["date"]) if active and current else None
    return dict(total=sum(d["count"] for d in days), currentStreak=current,
                longestStreak=longest, activeDays=sum(bool(d["count"]) for d in days),
                currentStart=(end - timedelta(days=current - 1)).isoformat() if end else None,
                currentEnd=end.isoformat() if end else None, longestEnd=longest_end)


def fetch_calendar(username, as_of):
    url = f"https://github.com/users/{username}/contributions?from={as_of.year}-01-01&to={as_of.isoformat()}"
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "profile-readme/1.0", "Accept-Language": "en-US,en;q=0.9"})
            with urlopen(request, timeout=30) as response:
                parser = CalendarParser()
                parser.feed(response.read().decode("utf-8"))
            days = parser.days(as_of)
            return dict(source=url, asOf=as_of.isoformat(), days=days, summary=summarize(days))
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


SPONSORS_QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    sponsorshipsAsMaintainer(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        privacyLevel
        createdAt
        tier { monthlyPriceInDollars }
        sponsorEntity { ... on User { login } ... on Organization { login } }
      }
    }
  }
}
"""


def fetch_sponsors(username, token):
    """Active sponsorships of `username`. Reading them needs a token with the read:user scope."""
    nodes, cursor = [], None
    while True:
        body = json.dumps({"query": SPONSORS_QUERY, "variables": {"login": username, "cursor": cursor}}).encode("utf-8")
        request = Request("https://api.github.com/graphql", data=body, headers={
            "Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-readme/1.0"})
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("errors"):
            raise RuntimeError("; ".join(error.get("message", "unknown error") for error in payload["errors"]))
        page = payload["data"]["user"]["sponsorshipsAsMaintainer"]
        nodes += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return nodes
        cursor = page["pageInfo"]["endCursor"]


def group_sponsors(nodes, settings):
    """Keep public sponsors only, put each in the highest tier it reaches, oldest first.

    Sponsors below the lowest tier are only counted, never named. Only logins and tier
    names are kept, so the saved file never says who pays exactly how much.
    """
    tiers = sorted(settings.get("tiers", []), key=lambda tier: -tier["from"])
    listed, friends = [], 0
    for node in sorted(nodes, key=lambda node: node.get("createdAt") or ""):
        login = (node.get("sponsorEntity") or {}).get("login")
        if node.get("privacyLevel") != "PUBLIC" or not login:
            continue
        amount = (node.get("tier") or {}).get("monthlyPriceInDollars") or 0
        tier = next((tier["name"] for tier in tiers if amount >= tier["from"]), None)
        if tier:
            listed.append({"login": login, "tier": tier})
        else:
            friends += 1
    return {"sponsors": listed, "friends": friends}


def load_sponsors(config):
    """Fresh sponsors when SPONSORS_TOKEN is set, otherwise the last saved list (or none yet)."""
    path = ROOT / "data" / "sponsors.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"sponsors": [], "friends": 0}
    token = os.environ.get("SPONSORS_TOKEN")
    if not token:
        print("::warning::SPONSORS_TOKEN is not set, keeping the saved sponsors list.")
        return saved, False
    try:
        nodes = fetch_sponsors(config["github"]["username"], token)
    except Exception as error:
        print(f"::warning::Could not read sponsors ({error}), keeping the saved list.")
        return saved, False
    return group_sponsors(nodes, config.get("sponsors", {})), True


def main():
    config = load_config()
    today = datetime.now(ZoneInfo(config["github"].get("timezone", "UTC"))).date()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, default=today)
    parser.add_argument("--snapshot", type=Path, help="Render a saved calendar (data/contributions.json) without network access")
    args = parser.parse_args()
    if args.snapshot:
        data = json.loads(args.snapshot.read_text(encoding="utf-8"))
        data["asOf"] = data.get("asOf") or data["days"][-1]["date"]
        data["summary"] = summarize(data["days"])
    else:
        data = fetch_calendar(config["github"]["username"], args.as_of)

    sponsors, fresh = load_sponsors(config)

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import artwork  # needs fonttools and pyfiglet; imported late so the tests above can run without them
    artwork.write_assets(data, config, sponsors)

    dest = ROOT / "data"
    dest.mkdir(exist_ok=True)
    (dest / "contributions.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if fresh:
        (dest / "sponsors.json").write_text(json.dumps(sponsors, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f'Rendered profile assets: {data["asOf"]}, {data["summary"]["total"]} contributions, '
          f'{len(sponsors["sponsors"])} listed sponsors + {sponsors["friends"]} friends')


if __name__ == "__main__":
    main()
