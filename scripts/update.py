#!/usr/bin/env python3
"""
Top of the Harbour - leaderboard updater.

Reads the season set-up files (settings.csv, rounds.csv, clubs.csv, overrides.csv),
collects every round's results from its sources, applies the overrides and writes
data/leaderboard.json, which index.html displays.

Sources a round can list (in the 'sources' column of rounds.csv, separated by spaces):
  * a Golf NZ tournament link   https://www.golf.co.nz/tournament-detail?competitionid=1229542
  * a results file in this repo results/round-6.csv
  * a link to an online CSV     e.g. a Google Sheet published as CSV
CSV results need the columns: player, club, holes, points

Standard library only, so it runs anywhere Python 3.9+ is installed.
"""
import csv, hashlib, io, json, os, re, sys, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "cache")
OUT = os.path.join(ROOT, "data", "leaderboard.json")
GOLFNZ = "https://www.golf.co.nz"
UA = "Mozilla/5.0 (TopOfTheHarbourLeaderboard; +https://github.com)"
NZ = timezone(timedelta(hours=12))  # display only

warnings, excluded = [], []


def warn(msg):
    warnings.append(msg)
    print("WARNING:", msg)


# ---------------------------------------------------------------- reading files
def read_csv(name, required=True):
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        if required:
            sys.exit(f"Missing {name}")
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = []
        for r in csv.DictReader(f):
            r = {k.strip().lower(): (v or "").strip() for k, v in r.items() if isinstance(k, str) and isinstance(v, (str, type(None)))}
            if any(r.values()) and not next(iter(r.values()), "").startswith("#"):
                rows.append(r)
        return rows


def to_int(v, default=None):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return default


def key(name):
    """Name used for matching: no accents, lower case, single spaces."""
    n = unicodedata.normalize("NFKD", name or "")
    n = "".join(c for c in n if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", n).strip().lower()


def tidy_name(name):
    name = re.sub(r"\s+", " ", (name or "").strip())
    if "," not in name and " " in name:  # "Blake Mills" -> "Mills, Blake"
        first, last = name.rsplit(" ", 1)
        name = f"{last}, {first}"
    return name


# ---------------------------------------------------------------- fetching
def http_get(url, as_json=True):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/csv, */*"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = r.read().decode("utf-8-sig")
    return json.loads(data) if as_json else data


def golfnz_id(src):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(src).query)
    for k, v in q.items():
        if k.lower() == "competitionid" and v and v[0].isdigit():
            return int(v[0])
    return None


def fetch_golfnz(cid):
    """Returns (info, rows). Rows are (player, club, holes, points)."""
    os.makedirs(CACHE, exist_ok=True)
    cache_file = os.path.join(CACHE, f"golfnz-{cid}.json")
    fixture = os.environ.get("GOLFNZ_FIXTURE")
    try:
        if fixture:
            data = fixture_lookup(fixture, cid)
        else:
            ov = http_get(f"{GOLFNZ}/api/Tournament/GetTournamentOverview?competitionid={cid}&memberUid=")
            lb_url = (f"{GOLFNZ}/api/Tournament/GetTournamentLeaderboard?competitionId={cid}&competitionTypeId={{t}}"
                      "&divisionId=&competitionRoundId=&showOnlyCountryName=false&pageNumber={p}&pageSize=500&includeFavouritePlayers=true")
            base = http_get(lb_url.format(t="", p=1))
            types = {(t.get("Name") or "").lower(): t.get("CompetitionTypeId") for t in (base.get("Types") or [])}
            tid = types.get("stableford")
            entries = []
            if tid is not None:
                page = 1
                while True:
                    j = http_get(lb_url.format(t=tid, p=page))
                    batch = j.get("Entries") or []
                    entries += batch
                    if len(batch) < 500:
                        break
                    page += 1
            data = {
                "id": cid, "name": ov.get("CompetitionName"), "holes": ov.get("NoOfHoles"),
                "date": (ov.get("CompetitionDate") or "")[:10], "has_stableford": tid is not None,
                "entries": [[e.get("DisplayName"), e.get("ClubCountry"), (e.get("EntryRound") or {}).get("RoundTotal")] for e in entries],
            }
        if data["entries"] or not os.path.exists(cache_file):
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=0)
    except Exception as ex:  # network problem: fall back to the last good copy
        if os.path.exists(cache_file):
            warn(f"Golf NZ competition {cid} could not be reached ({ex}); used the last saved copy.")
            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)
        else:
            warn(f"Golf NZ competition {cid} could not be reached ({ex}) and there is no saved copy.")
            return {"id": cid, "name": f"Golf NZ {cid}", "holes": None, "entries": []}, []
    holes = to_int(data.get("holes"), 18)
    if not data.get("has_stableford", True):
        warn(f"Golf NZ competition {cid} ({data.get('name')}) has no stableford results.")
    rows = []
    for name, club, pts in data["entries"]:
        p = to_int(pts)
        if p is None:
            continue  # entered but no score (DNS / no return)
        rows.append((name, club or "", holes, p))
    return data, rows


_fixture_cache = None


def fixture_lookup(path, cid):
    global _fixture_cache
    if _fixture_cache is None:
        with open(path, encoding="utf-8") as f:
            _fixture_cache = json.load(f)
    clubs = _fixture_cache["clubs"]
    for c in _fixture_cache["comps"]:
        if c[0] == cid:
            return {"id": cid, "name": c[1], "holes": c[2], "date": c[3], "has_stableford": "Stableford" in c[4],
                    "entries": [[n, clubs[ci], s] for n, ci, s in c[5]]}
    raise RuntimeError("not in fixture")


def read_results_csv(text, label):
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        if not r.get("player"):
            continue
        p = to_int(r.get("points") or r.get("stableford"))
        if p is None:
            warn(f"{label}: {r.get('player')} has no points, skipped.")
            continue
        rows.append((r["player"], r.get("club", ""), to_int(r.get("holes"), 18), p))
    return rows


# ---------------------------------------------------------------- main
def main():
    settings = {r["setting"].lower(): r["value"] for r in read_csv("settings.csv")}
    S = {
        "perClub": to_int(settings.get("scores_per_club"), 3),
        "bestEvents": to_int(settings.get("best_events"), 6),
        "nineHoleAdd": to_int(settings.get("nine_hole_add"), 17),
    }
    rounds_in = read_csv("rounds.csv")
    clubs_in = read_csv("clubs.csv")
    overrides = read_csv("overrides.csv", required=False)

    # clubs + aliases
    clubs, alias = [], {}
    for c in clubs_in:
        name = c["club"]
        clubs.append({"name": name, "bop": c.get("eligible", "yes").lower() not in ("no", "n", "false", "0")})
        alias[key(name)] = name
        for a in re.split(r"[;|]", c.get("also_known_as", "")):
            if a.strip():
                alias[key(a)] = name

    rounds, raw = [], []  # raw: dict(round, player, club, holes, points, source)
    for r in rounds_in:
        n = to_int(r.get("round"))
        if n is None:
            continue
        cancelled = r.get("status", "").lower().startswith("cancel")
        info = {"n": n, "event": r.get("event", f"Round {n}"), "venue": r.get("venue", ""), "date": r.get("date", ""),
                "cancelled": cancelled, "sources": []}
        if not cancelled:
            for src in r.get("sources", "").split():
                cid = golfnz_id(src)
                try:
                    if cid:
                        data, rows = fetch_golfnz(cid)
                        label = data.get("name") or f"Golf NZ {cid}"
                        link = f"{GOLFNZ}/tournament-detail?competitionid={cid}"
                        if not info["date"] and data.get("date"):
                            info["date"] = data["date"]
                    elif src.lower().startswith("http"):
                        rows = read_results_csv(http_get(src, as_json=False), src)
                        label, link = "Online results sheet", src
                    else:
                        with open(os.path.join(ROOT, src), encoding="utf-8-sig") as f:
                            rows = read_results_csv(f.read(), src)
                        label, link = src, None
                except Exception as ex:
                    warn(f"Round {n}: could not read source {src} ({ex}).")
                    continue
                info["sources"].append({"label": label, "link": link, "count": len(rows)})
                for p, club, holes, pts in rows:
                    raw.append({"round": n, "player": tidy_name(p), "club": club, "holes": holes, "points": pts, "source": label})
        rounds.append(info)
    rounds.sort(key=lambda x: x["n"])
    cancelled_rounds = {r["n"] for r in rounds if r["cancelled"]}

    # ---- overrides, applied in file order
    for i, o in enumerate(overrides, start=2):
        act = o.get("action", "").lower()
        rnd = to_int(o.get("round"))
        who = key(tidy_name(o.get("player", "")))
        hit = [x for x in raw if key(x["player"]) == who and (rnd is None or x["round"] == rnd)]
        where = f"overrides.csv line {i} ({act} {o.get('player','')})"
        if act == "rename":
            new = tidy_name(o.get("new_value", ""))
            for x in hit: x["player"] = new
        elif act == "club":
            for x in hit: x["club"] = o.get("club", "")
        elif act == "score":
            for x in hit:
                x["points"] = to_int(o.get("points"), x["points"])
                if o.get("holes"): x["holes"] = to_int(o.get("holes"), x["holes"])
        elif act == "remove":
            raw[:] = [x for x in raw if all(x is not h for h in hit)]
        elif act == "add":
            if rnd is None or to_int(o.get("points")) is None:
                warn(f"{where}: add needs a round and points."); continue
            raw.append({"round": rnd, "player": tidy_name(o["player"]), "club": o.get("club", ""),
                        "holes": to_int(o.get("holes"), 18), "points": to_int(o.get("points")), "source": "Manual override"})
            continue
        else:
            warn(f"{where}: unknown action '{act}'. Use add, score, remove, club or rename."); continue
        if not hit:
            warn(f"{where}: no matching result found.")

    # ---- validate and build results
    results, seen = [], {}
    for x in raw:
        if x["round"] in cancelled_rounds:
            continue
        club = alias.get(key(x["club"]))
        if not club:
            excluded.append({"round": x["round"], "player": x["player"], "club": x["club"] or "(none)", "points": x["points"], "source": x["source"]})
            continue
        if x["holes"] not in (9, 18):
            warn(f"Round {x['round']}: {x['player']} has holes={x['holes']}; treated as 18.")
            x["holes"] = 18
        k = (x["round"], key(x["player"]))
        if k in seen:
            warn(f"Round {x['round']}: {x['player']} appears twice ({seen[k]} and {x['source']}); the first was kept.")
            continue
        seen[k] = x["source"]
        results.append([x["round"], x["player"], club, x["holes"], x["points"]])
    # one spelling per player: the most common one (ties: the one with accents, as Golf NZ shows it)
    from collections import Counter
    spell = Counter((key(r[1]), r[1]) for r in results)
    best = {}
    for (k, name), n in spell.items():
        if k not in best or (n, name != key(name)) > (spell[(k, best[k])], best[k] != key(best[k])):
            best[k] = name
    for r in results:
        r[1] = best[key(r[1])]
    results.sort(key=lambda r: (r[0], r[2], r[1]))

    # ---- write, keeping 'updated' unless something changed
    payload = {
        "season": to_int(settings.get("season"), datetime.now(NZ).year),
        "title": settings.get("title", "Top of the Harbour"),
        "status": settings.get("status", "Live"),
        "settings": S, "rounds": rounds, "clubs": clubs, "results": results,
        "excluded": sorted(excluded, key=lambda e: (e["round"], e["player"])), "warnings": warnings,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    old = {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            try: old = json.load(f)
            except ValueError: old = {}
    if old.get("digest") == digest:
        print("No changes.")
        return
    payload["digest"] = digest
    payload["updated"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"Wrote {len(results)} results, {len(excluded)} excluded, {len(warnings)} warnings.")


if __name__ == "__main__":
    main()
