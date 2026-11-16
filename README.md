# Top of the Harbour – live leaderboard

A public web page showing the Top of the Harbour club teams and individual leaderboards.
It updates itself every three hours from each event's results, so after an event you
normally don't need to do anything.

The page has three tabs: **Club teams**, **Individuals** and **Event results**.
There is also a **Data check** page (link at the bottom of the leaderboard) that lists anything
the updater couldn't use.

---

## One-time setup (about 15 minutes)

1. **Create a free GitHub account** at github.com if you don't have one.
2. **Create a repository**: click **+** (top right) → **New repository**.
   Name it e.g. `top-of-the-harbour`, choose **Public**, and click **Create repository**.
3. **Upload the files**: on the new repository page click **uploading an existing file**.
   Unzip the download, open the `top-of-the-harbour` folder, select **everything inside it**
   and drag it into the browser. Click **Commit changes**.
   *The `.github` folder is hidden on some computers. If it doesn't upload, see "Troubleshooting".*
4. **Turn on the website**: go to **Settings → Pages**. Under *Build and deployment → Source*
   choose **GitHub Actions**.
5. **Run it once**: go to the **Actions** tab. If asked, click **I understand my workflows, go ahead
   and enable them**. Click **Update leaderboard** → **Run workflow** → **Run workflow**.
   After a minute or two it shows a green tick.
6. **Your link** is `https://YOUR-GITHUB-NAME.github.io/top-of-the-harbour/`
   (it's also shown under **Settings → Pages**). Share it, or put it on your website.

To show the leaderboard inside a page on your existing website, paste this where you want it
(swap in your link):

```html
<iframe src="https://YOUR-GITHUB-NAME.github.io/top-of-the-harbour/" style="width:100%;height:1400px;border:0" title="Top of the Harbour leaderboard"></iframe>
```

---

## The organiser page (easiest way to make changes)

Go to your leaderboard link and add `admin.html` to the end, e.g.
`https://YOUR-GITHUB-NAME.github.io/top-of-the-harbour/admin.html`. There's also an **Organiser** link
at the bottom of the leaderboard. From there you can add results links, fix scores, upload results, edit clubs and settings, and
press **Update the leaderboard now**.

The first time, you'll need a GitHub **access key** (the page shows you how): open
github.com/settings/personal-access-tokens/new, choose *Only select repositories* → this project,
set **Contents** and **Actions** to **Read and write**, and generate it. Paste it into the organiser page.
Keep it private: anyone with the key can change the leaderboard. When it expires, make a new one.

Everything the organiser page does can also be done by editing the files directly, as below.

### Look, sponsors and history

* **Look & sponsors** tab: upload your own logo for the header, change the small heading, and add sponsors
  (logo, name and website link). Sponsors show in a *Supported by* strip under the header.
* **History** tab: at the end of a season, set Status to Final, click **Save season to History**, then
  **Start next season**. Saved seasons appear on the leaderboard's **History** tab with a link to their full
  leaderboard. Winners from before this website are kept under *Past winners* (`honours.csv`).

## The files you edit

You can edit any of these straight on GitHub: open the file, click the **pencil** icon, make the
change, then click **Commit changes**. The leaderboard rebuilds within a couple of minutes.

| File | What it's for |
|---|---|
| `settings.csv` | Season year, title, Live/Final, and the scoring rules (best 3 per club, best 6 events, +17 for 9 holes) |
| `rounds.csv` | The 10 events: name, venue, date, Cancelled, and **where each event's results come from** |
| `clubs.csv` | The clubs that count, whether each can win the trophy, and other spellings of the club name |
| `overrides.csv` | Manual fixes that win over everything else |
| `results/` | Results for events that weren't scored on Golf NZ |

Don't edit anything in `data/`; the updater writes it.

### rounds.csv – linking each event's results

The `sources` column takes one or more links, separated by a space. Each can be:

* **A Golf NZ tournament link**, e.g. `https://www.golf.co.nz/tournament-detail?competitionid=1229542`.
  The stableford results are read automatically. Events usually have separate 18-hole and
  9-hole fields, so add both links. The updater knows which one is the 9-hole field and adds the 17 points itself.
* **A results file you upload** to the `results` folder, e.g. `results/2027-round-6.csv`.
* **A link to an online sheet** published as CSV. In Google Sheets: *File → Share → Publish to web →
  choose the sheet → Comma-separated values (.csv) → Publish*, and paste that link.

Results files and sheets need these four columns (copy `results/TEMPLATE.csv`):

```
player,club,holes,points
"Smith, Jane",Omanu Golf Club,18,36
"Brown, Tom",Te Puke Golf Club,9,19
```

Enter the **raw** stableford points. For a 9-hole card, put 9 in `holes` and the 17 points are added for you.

You can mix sources in one round, e.g. the Golf NZ 9-hole link plus a file for the 18-hole field.

To cancel an event, put `Cancelled` in its `status` column.

### clubs.csv

Players count for the club shown on their results. If a results system spells a club
differently (e.g. *Mt Maunganui GC*), add that spelling to `also_known_as` (separate several with `;`).
Set `eligible` to `No` for a club that takes part but can't win the trophy. It will be listed below the
standings without a position.

Players whose club isn't on the list (e.g. visitors from Waihi) are left out and shown on the
**Data check** page.

### overrides.csv – manual fixes

One fix per line. Overrides apply on top of the results, so they stay in place when new results
come in. Lines starting with `#` are notes.

| action | fill in | example |
|---|---|---|
| `add` | round, player, club, holes, points | a score that isn't on any results list |
| `score` | round, player, points (holes if it changed) | a card was corrected after the event |
| `remove` | player, round (blank = every round) | a player who shouldn't count |
| `club` | player, club, round (blank = every round) | a player who changed clubs, or is listed wrongly |
| `rename` | player (spelling to replace), new_value (spelling to keep) | "Smith, Jon" and "Smith, Jonathan" are the same player |

Names are matched as `Last, First`, ignoring capitals and accents.
The 2026 file has real examples of each.

---

## Starting a new season

1. In `settings.csv` set the new `season` and set `status` to `Live`.
2. In `rounds.csv` update the events, dates and venues, and replace the `sources` with the new
   season's links as each event's results page is set up. A round with no sources simply shows as upcoming.
3. Delete the old season's lines in `overrides.csv` (keep the notes at the top) and its files in `results/`.
4. Check `clubs.csv`.

At the end of the season set `status` to `Final`.

Tip: before a new season, save a copy of the old one. On the repository page click **Code →
Download ZIP**, or create a second repository for the old year.

---

## Good to know

* **How often it updates:** every 3 hours, plus straight away whenever you change a file. To update
  right now, go to **Actions → Update leaderboard → Run workflow**.
* **If Golf NZ can't be reached**, the last saved copy of each event is used and a note appears on the
  Data check page. The saved copies are in `data/cache/`.
* **GitHub pauses scheduled runs** in repositories with no activity for 60 days, e.g. over the off-season.
  If that happens, the Actions tab shows a banner. Click **Enable workflow**, or just edit any file.
* **Golf NZ's results feed** isn't an official public service. If Golf NZ changes how its website works,
  the automatic part may stop, but files, sheets and overrides keep working.

## Troubleshooting

* **The Actions tab has no "Update leaderboard" workflow:** the hidden `.github` folder didn't upload.
  Click **Add file → Create new file**, type the name `.github/workflows/update.yml`, paste in the
  contents of that file from the download, and commit.
* **A run has a red cross:** click it to see the error. The most common cause is a typo in a CSV,
  such as a missing comma.
* **The page says the data couldn't be loaded:** the workflow hasn't finished a run yet. Run it from the Actions tab.
