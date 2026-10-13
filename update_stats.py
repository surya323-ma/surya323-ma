import json
import os
import re
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

README = "README.md"
START = "<!-- STATS-START -->"
END = "<!-- STATS-END -->"


def sh(cmd):
    return subprocess.check_output(cmd, text=True).strip()


def github_api(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Accept": "application/vnd.github+json"},
    )
    token = os.getenv("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def badge(label, message, color, logo=None):
    """shields.io badge URL (dark theme, matches README)."""
    def esc(t):
        return quote(str(t).replace("-", "--").replace("_", "__"), safe="")

    url = (
        f"https://img.shields.io/badge/{esc(label)}-{esc(message)}-{color}"
        f"?style=for-the-badge&labelColor=0d1117"
    )
    if logo:
        url += f"&logo={logo}&logoColor=white"
    return f'<img src="{url}" alt="{label}" />'


owner = os.getenv("GITHUB_REPOSITORY_OWNER", "surya323-ma")

total_repos = github_api(f"/users/{owner}")["public_repos"]
repo_commits = sh(["git", "rev-list", "--count", "HEAD"])

last_commit = datetime.fromisoformat(sh(["git", "log", "-1", "--format=%cI"]))
ist = last_commit.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime(
    "%d %b %Y, %I:%M %p IST"
)

block = f"""{START}
<div align="center">

{badge("Projects", total_repos, "247bff", "github")}
{badge("Commits", repo_commits, "ff354f", "git")}

{badge("Last Commit", ist, "30363d", "clockify")}

</div>
{END}"""

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
