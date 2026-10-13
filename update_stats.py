"""
README ka STATS-START / STATS-END block GitHub ke asli data se update karta hai.

Data source: GitHub GraphQL API (saare public repos, saari languages, saare saal ke commits).
Token: STATS_TOKEN (optional PAT) ya default GITHUB_TOKEN.
"""
import json
import os
import re
import subprocess
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

README = "README.md"
START = "<!-- STATS-START -->"
END = "<!-- STATS-END -->"

OWNER = os.getenv("GITHUB_REPOSITORY_OWNER") or "surya323-ma"
THIS_REPO = os.getenv("GITHUB_REPOSITORY", "").split("/")[-1]
TOKEN = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")

TOP_LANGS = 8          # kitni languages dikhani hain
INCLUDE_FORKS = False  # True karo to forked repos bhi count honge
IST = timezone(timedelta(hours=5, minutes=30))

# language -> (color, simple-icons logo)
LANG_STYLE = {
    "Python": ("3776AB", "python"),
    "Jupyter Notebook": ("DA5B0B", "jupyter"),
    "JavaScript": ("D4B800", "javascript"),
    "TypeScript": ("3178C6", "typescript"),
    "Java": ("B07219", "openjdk"),
    "C": ("555555", "c"),
    "C++": ("F34B7D", "cplusplus"),
    "HTML": ("E34C26", "html5"),
    "CSS": ("563D7C", "css3"),
    "Dart": ("00B4AB", "dart"),
    "Shell": ("4EAA25", "gnubash"),
    "Kotlin": ("A97BFF", "kotlin"),
    "Go": ("00ADD8", "go"),
    "Rust": ("DEA584", "rust"),
    "PHP": ("777BB4", "php"),
    "Cython": ("C9A227", None),
}


# ---------- GitHub API ----------
def gql(query, variables=None):
    if not TOKEN:
        raise SystemExit("Token nahi mila (GH_TOKEN / GITHUB_TOKEN)")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if data.get("errors"):
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]


def fetch_profile():
    q = """query($login:String!){user(login:$login){createdAt followers{totalCount}}}"""
    u = gql(q, {"login": OWNER})["user"]
    created = datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))
    return created, u["followers"]["totalCount"]


def fetch_repos():
    q = """
    query($login:String!,$after:String,$fork:Boolean){
      user(login:$login){
        repositories(first:100, after:$after, ownerAffiliations:OWNER, isFork:$fork,
                     privacy:PUBLIC, orderBy:{field:PUSHED_AT, direction:DESC}){
          pageInfo{hasNextPage endCursor}
          nodes{
            name stargazerCount pushedAt
            languages(first:10, orderBy:{field:SIZE, direction:DESC}){
              edges{size node{name}}
            }
          }
        }
      }
    }"""
    repos, after = [], None
    # isFork:false => sirf apne banaye repos; None => sab
    fork = None if INCLUDE_FORKS else False
    while True:
        conn = gql(q, {"login": OWNER, "after": after, "fork": fork})["user"]["repositories"]
        repos += conn["nodes"]
        if not conn["pageInfo"]["hasNextPage"]:
            return repos
        after = conn["pageInfo"]["endCursor"]


def fetch_total_commits(created):
    """Account banne ke saal se ab tak ke saare saal ke commits jodta hai."""
    now = datetime.now(timezone.utc)
    parts = [
        f'y{y}: contributionsCollection(from:"{y}-01-01T00:00:00Z", to:"{y}-12-31T23:59:59Z")'
        "{totalCommitContributions}"
        for y in range(created.year, now.year + 1)
    ]
    q = "query($login:String!){user(login:$login){" + " ".join(parts) + "}}"
    user = gql(q, {"login": OWNER})["user"]
    return sum(v["totalCommitContributions"] for v in user.values())


# ---------- helpers ----------
def sh(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def parse_iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def esc(t):
    return quote(str(t).replace("-", "--").replace("_", "__"), safe="")


def badge(label, message, color, logo=None):
    url = (
        f"https://img.shields.io/badge/{esc(label)}-{esc(message)}-{color}"
        "?style=for-the-badge&labelColor=0d1117"
    )
    if logo:
        url += f"&logo={logo}&logoColor=white"
    return f'<img src="{url}" alt="{label}" />'


def latest_push(repos):
    """Sabse latest push (repo naam, time). Bot ke 'update stats' commit ginte nahi."""
    best = None
    for r in repos:
        if r["name"] == THIS_REPO or not r.get("pushedAt"):
            continue
        t = parse_iso(r["pushedAt"])
        if best is None or t > best[1]:
            best = (r["name"], t)
    if THIS_REPO:
        own = sh(["git", "log", "-1", "--format=%cI",
                  "--invert-grep", "--grep=chore: update stats"])
        if own:
            t = parse_iso(own)
            if best is None or t > best[1]:
                best = (THIS_REPO, t)
    return best


# ---------- build ----------
def build_block():
    created, followers = fetch_profile()
    repos = fetch_repos()
    commits = fetch_total_commits(created)

    stars = sum(r["stargazerCount"] for r in repos)

    langs = Counter()
    for r in repos:
        for e in r["languages"]["edges"]:
            langs[e["node"]["name"]] += e["size"]
    total_bytes = sum(langs.values()) or 1

    row1 = "\n".join([
        badge("Projects", len(repos), "247bff", "github"),
        badge("Commits", f"{commits:,}", "ff354f", "git"),
        badge("Stars", stars, "e3b341", "github"),
        badge("Followers", followers, "8957e5", "github"),
    ])

    lang_badges = []
    for name, size in langs.most_common(TOP_LANGS):
        color, logo = LANG_STYLE.get(name, ("30363d", None))
        pct = size * 100 / total_bytes
        lang_badges.append(badge(name, f"{pct:.1f}%", color, logo))
    row2 = "\n".join(lang_badges)

    lp = latest_push(repos)
    row3 = ""
    if lp:
        when = lp[1].astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
        row3 = badge("Last Push", f"{lp[0]} | {when}", "30363d", "clockify")

    parts = [row1, row2] + ([row3] if row3 else [])
    body = "\n\n".join(parts)
    return f'{START}\n<div align="center">\n\n{body}\n\n</div>\n{END}'


def main():
    block = build_block()
    with open(README, encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(content):
        raise SystemExit("STATS-START / STATS-END markers README mein nahi mile")

    new_content = pattern.sub(lambda _: block, content)
    if new_content != content:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("README updated")
    else:
        print("No change")


if __name__ == "__main__":
    main()
