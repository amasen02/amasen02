"""Local, read-only GitHub profile refresh agent (Python standard library only)."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from .presentation import render_readme as presentation_readme, template_digest, write_assets as presentation_assets

UTC = timezone.utc
MAX_PAGES = 3
PR_SEARCH_PAGE_SIZE = 100
PR_SEARCH_MAX_RESULTS = 1000
RENDERER_VERSION = "2026-09-05.6"
CURATED = {
    "polyai-dotnet": {"title": "PolyAI .NET", "category": "ai"},
    "credscan": {"title": "CredScan", "category": "ai"},
    "centaurloop-agent-governor": {
        "title": "CentaurLoop",
        "category": "ai",
        "reviewed_summary": "Python experiments for coding-agent guardrails: syntax checks, forbidden-phrase checks, and compact execution logs.",
        "implementation_url": "https://github.com/amasen02/centaurloop-agent-governor/blob/master/src/governor.py",
        "expected_url": "https://github.com/amasen02/centaurloop-agent-governor",
    },
    "freshcart-backend": {"title": "FreshCart Backend", "category": "fullstack"},
    "freshcart-web": {"title": "FreshCart Web", "category": "fullstack"},
    "dupesweep": {"title": "DupeSweep", "category": "tools"},
    "a11y-scope": {"title": "a11y-scope", "category": "tools"},
}


class RefreshError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path):
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def dump_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def safe_url(value: str, allowed_hosts: tuple[str, ...] = ()) -> bool:
    if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
        return False
    parsed = urlparse(value)
    host = parsed.hostname.lower() if parsed.hostname else ""
    return (parsed.scheme == "https" and parsed.username is None and parsed.password is None
            and parsed.port in (None, 443) and bool(host)
            and not parsed.params and not parsed.query and not parsed.fragment
            and (not allowed_hosts or host in allowed_hosts))


def safe_search_url(value: object) -> bool:
    if not isinstance(value, str) or any(ord(char) < 32 for char in value):
        return False
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "github.com"
        and parsed.username is None
        and parsed.password is None
        and parsed.port in (None, 443)
        and parsed.path == "/search"
        and bool(parsed.query)
        and not parsed.fragment
    )


def markdown_escape(value: str) -> str:
    return re.sub(r"([\\`*_{}\[\]<>])", r"\\\1", str(value)).replace("\r", " ").replace("\n", " ")


class Source:
    def __init__(self, offline: Path | None = None):
        self.offline = offline
        self.raw: dict[str, object] = {}
        self.urls: list[str] = []
        self.snapshot = load_json(offline) if offline else None
        if self.snapshot is not None:
            stamp = self.snapshot.get("evidence_at") if isinstance(self.snapshot, dict) else None
            try:
                parsed_stamp = datetime.fromisoformat(stamp.replace("Z", "+00:00")) if isinstance(stamp, str) and stamp.endswith("Z") else None
            except ValueError:
                parsed_stamp = None
            if parsed_stamp is None or parsed_stamp.tzinfo != UTC:
                raise RefreshError("offline snapshot must contain an ISO-UTC evidence_at timestamp")
            self.evidence_at = stamp
        else:
            self.evidence_at = now()

    def get(self, url: str):
        self.urls.append(url)
        if self.snapshot is not None:
            sources = self.snapshot.get("sources", self.snapshot)
            if url not in sources:
                raise RefreshError(f"offline snapshot has no source for {url}")
            data = sources[url]
        else:
            token = os.environ.get("GH_TOKEN")
            headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-studio-agent"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            try:
                with urlopen(Request(url, headers=headers), timeout=15) as response:
                    if response.status != 200:
                        raise RefreshError(f"GitHub returned HTTP {response.status} for {url}")
                    data = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                if exc.code not in (403, 429):
                    raise RefreshError(f"could not fetch {url}: {exc}") from exc
                data = self._gh_get(url)
            except RefreshError:
                raise
            except Exception as exc:
                raise RefreshError(f"could not fetch {url}: {exc}") from exc
        self.raw[url] = data
        return data

    @staticmethod
    def _gh_get(url: str):
        """Rate-limit fallback through the user's authenticated gh CLI; GET only."""
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "api.github.com":
            raise RefreshError("refusing non-GitHub CLI endpoint")
        gh = shutil.which("gh")
        if not gh:
            raise RefreshError("GitHub API rate limited and gh CLI is unavailable")
        endpoint = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        try:
            completed = subprocess.run([gh, "api", endpoint, "--method", "GET"], text=True, encoding="utf-8",
                                       errors="replace", capture_output=True, timeout=15, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RefreshError(f"GitHub API rate limited and gh fallback failed: {exc}") from exc
        if completed.returncode != 0:
            raise RefreshError("GitHub API rate limited and gh fallback failed")
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RefreshError("GitHub API rate limited and gh returned invalid JSON") from exc


def api_url(path: str) -> str:
    return "https://api.github.com" + path


def owned_public_repositories(source: Source, username: str) -> list[dict]:
    repositories: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        data = source.get(api_url(f"/users/{quote(username)}/repos?per_page=100&page={page}&type=owner&sort=updated"))
        if not isinstance(data, list):
            raise RefreshError("repository response is not a list")
        if any(not isinstance(item, dict) for item in data):
            raise RefreshError("repository response contains a malformed repository")
        repositories.extend(data)
        if len(data) < 100:
            break
    else:
        raise RefreshError(f"repository pagination reached the {MAX_PAGES}-page safety cap; totals are incomplete")
    valid = []
    for repo in repositories:
        owner = (repo.get("owner") or {}).get("login")
        if isinstance(owner, str) and owner.casefold() == username.casefold() and not repo.get("private") and not repo.get("fork") and not repo.get("archived"):
            valid.append(repo)
    return valid


def _utc_timestamp(value: object) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RefreshError("PR detail response has an invalid merged timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RefreshError("PR detail response has an invalid merged timestamp") from exc
    if parsed.tzinfo != UTC:
        raise RefreshError("PR detail response has a non-UTC merged timestamp")
    return value


def contribution_search_url(username: str) -> str:
    query = quote(f"author:{username} -user:{username} is:pr is:merged is:public", safe="")
    return f"https://github.com/search?q={query}&type=pullrequests"


def verified_prs(source: Source, username: str) -> tuple[list[dict], dict]:
    query = quote(f"author:{username} is:pr is:merged is:public", safe="")
    expected_total: int | None = None
    identities: set[str] = set()
    page = 1
    while True:
        search = source.get(api_url(
            f"/search/issues?q={query}&per_page={PR_SEARCH_PAGE_SIZE}&page={page}&sort=created&order=asc"
        ))
        if not isinstance(search, dict) or not isinstance(search.get("items"), list):
            raise RefreshError("PR search response is invalid")
        total = search.get("total_count")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise RefreshError("PR search response has an invalid total_count")
        if search.get("incomplete_results") is not False:
            raise RefreshError("PR search coverage is incomplete")
        if total > PR_SEARCH_MAX_RESULTS:
            raise RefreshError("PR search exceeds GitHub's 1,000-result coverage limit")
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise RefreshError("PR search total_count changed during pagination")
        for item in search["items"]:
            if not isinstance(item, dict) or not isinstance(item.get("pull_request"), dict):
                raise RefreshError("PR search response contains a malformed item")
            api = item["pull_request"].get("url")
            if not isinstance(api, str) or not safe_url(api, ("api.github.com",)):
                raise RefreshError("PR search response contains an unsafe PR URL")
            identities.add(api)
        if len(identities) > expected_total:
            raise RefreshError("PR search unique result count exceeds total_count")
        if len(identities) == expected_total:
            break
        if len(search["items"]) < PR_SEARCH_PAGE_SIZE:
            break
        page += 1
        if page > (PR_SEARCH_MAX_RESULTS // PR_SEARCH_PAGE_SIZE):
            raise RefreshError("PR search pagination exceeded GitHub's coverage limit")
    if expected_total is None or len(identities) != expected_total:
        raise RefreshError("PR search unique result count does not match total_count")

    external: list[dict] = []
    excluded_own = 0
    excluded_private = 0
    for api in sorted(identities):
        pr = source.get(api)
        if not isinstance(pr, dict) or pr.get("url") != api:
            raise RefreshError("PR detail response does not match the requested identity")
        user = pr.get("user")
        base_object = pr.get("base")
        if not isinstance(user, dict) or not isinstance(base_object, dict):
            raise RefreshError("PR detail response has malformed user or base data")
        base = base_object.get("repo")
        if not isinstance(base, dict):
            raise RefreshError("PR detail response has no base repository")
        owner_object = base.get("owner")
        if not isinstance(owner_object, dict):
            raise RefreshError("PR detail response has malformed base owner data")
        author = user.get("login")
        owner = owner_object.get("login")
        name = base.get("name")
        title = pr.get("title")
        if (
            not isinstance(author, str)
            or author.casefold() != username.casefold()
            or pr.get("merged") is not True
            or not isinstance(owner, str)
            or not isinstance(name, str)
            or not isinstance(title, str)
            or not isinstance(base.get("private"), bool)
        ):
            raise RefreshError("PR detail response does not verify the authored merged PR")
        merged_at = _utc_timestamp(pr.get("merged_at"))
        number = pr.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
            raise RefreshError("PR detail response has an invalid PR number")
        parsed_api = urlparse(api)
        expected_api_path = f"/repos/{owner}/{name}/pulls/{number}"
        if parsed_api.path != expected_api_path:
            raise RefreshError("PR detail response does not match the requested repository identity")
        url = pr.get("html_url")
        expected_html_url = f"https://github.com/{owner}/{name}/pull/{number}"
        if url != expected_html_url or not safe_url(url, ("github.com",)):
            raise RefreshError("PR detail response has an unsafe public URL")
        if base["private"]:
            excluded_private += 1
            continue
        if owner.casefold() == username.casefold():
            excluded_own += 1
            continue
        external.append({"title": title, "repository": f"{owner}/{name}", "url": url, "state": "merged", "merged_at": merged_at})
    external.sort(key=lambda item: (item["merged_at"], item["url"]), reverse=True)
    coverage = {
        "search_total": expected_total,
        "unique_checked_total": len(identities),
        "external_merged_count": len(external),
        "external_repository_count": len({item["repository"] for item in external}),
        "excluded_own_count": excluded_own,
        "excluded_private_count": excluded_private,
        "complete": True,
        "search_url": contribution_search_url(username),
    }
    return external, coverage


def project_from_repo(repo: dict) -> dict | None:
    name = repo.get("name")
    spec = CURATED.get(name)
    if not spec:
        return None
    url = repo.get("html_url")
    if not isinstance(url, str) or not safe_url(url, ("github.com",)):
        return None
    description = repo.get("description")
    if description is not None and not isinstance(description, str):
        raise RefreshError("repository description is malformed")
    description = (description or "").strip()
    reviewed_summary = spec.get("reviewed_summary")
    if reviewed_summary:
        if url != spec["expected_url"]:
            raise RefreshError("source-reviewed repository URL does not match its configured identity")
        summary = reviewed_summary
        evidence = [
            {"label": "Repository", "url": url},
            {"label": "Implementation", "url": spec["implementation_url"]},
        ]
    elif not description:
        return None  # source-supported claims fail closed when GitHub supplies no description
    else:
        summary = description
        evidence = [{"label": "Repository", "url": url}]
    language = repo.get("language")
    if language is not None and not isinstance(language, str):
        raise RefreshError("repository language is malformed")
    stack = [language] if language else []
    return {"id": name, "title": spec["title"], "category": spec["category"], "summary": summary,
            "stack": stack, "url": url, "stars": int(repo.get("stargazers_count") or 0),
            "updated_at": repo.get("updated_at") or None,
            "evidence": evidence, "highlights": [summary]}


def validate_profile(profile: dict) -> None:
    if profile.get("version") != 1:
        raise RefreshError("profile contract version is invalid")
    identity = profile.get("identity", {})
    for key in ("github", "linkedin"):
        if not safe_url(str(identity.get(key, ""))):
            raise RefreshError(f"unsafe identity URL: {key}")
    for project in profile.get("projects", []):
        if not safe_url(project.get("url", ""), ("github.com",)) or not project.get("summary"):
            raise RefreshError("unsafe or unsupported project")
        for evidence in project.get("evidence", []):
            if not safe_url(evidence.get("url", ""), ("github.com",)):
                raise RefreshError("unsafe project evidence URL")
    for contribution in profile.get("contributions", []):
        if contribution["state"] not in ("merged", "open", "closed") or not safe_url(contribution["url"], ("github.com",)):
            raise RefreshError("invalid contribution")
    coverage = profile.get("contribution_coverage")
    if not isinstance(coverage, dict) or coverage.get("complete") is not True:
        raise RefreshError("incomplete contribution coverage")
    for key in ("search_total", "unique_checked_total", "external_merged_count", "external_repository_count", "excluded_own_count", "excluded_private_count"):
        if not isinstance(coverage.get(key), int) or isinstance(coverage[key], bool) or coverage[key] < 0:
            raise RefreshError("invalid contribution coverage count")
    if coverage["external_merged_count"] != len(profile.get("contributions", [])):
        raise RefreshError("contribution coverage does not match records")
    repositories = {
        str(contribution.get("repository", "")).casefold()
        for contribution in profile.get("contributions", [])
    }
    if coverage["external_repository_count"] != len(repositories):
        raise RefreshError("contribution coverage repository count does not match records")
    if coverage["search_total"] != coverage["unique_checked_total"]:
        raise RefreshError("contribution coverage search total does not match checked records")
    if coverage["search_total"] != (
        coverage["external_merged_count"]
        + coverage["excluded_own_count"]
        + coverage["excluded_private_count"]
    ):
        raise RefreshError("contribution coverage totals do not balance")
    if not safe_search_url(coverage.get("search_url", "")):
        raise RefreshError("unsafe contribution search URL")


def profile_from_evidence(source: Source, config: dict) -> dict:
    identity = config["identity"]
    username = identity["username"]
    repos = owned_public_repositories(source, username)
    projects = [p for r in repos if (p := project_from_repo(r))]
    projects.sort(key=lambda p: list(CURATED).index(p["id"]))
    prs, coverage = verified_prs(source, username)
    profile = {"version": 1, "generated_at": now(), "identity": identity, "roles": config["roles"],
               "projects": projects, "contributions": prs,
               "contribution_coverage": coverage,
               "metrics": {"original_repositories": len(repos), "stars": sum(int(r.get("stargazers_count") or 0) for r in repos), "merged_prs_sample": len(prs)},
               "status": {"source": "snapshot" if source.snapshot is not None else "live", "evidence_at": source.evidence_at, "warnings": []}}
    if not projects:
        profile["status"]["warnings"].append("No curated repositories had a public source-supported description.")
    validate_profile(profile)
    return profile


def content_hash(profile: dict) -> str:
    stable = dict(profile)
    stable.pop("generated_at", None)
    stable["status"] = dict(stable["status"])
    stable["status"].pop("evidence_at", None)
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def artifact_hash(profile: dict) -> str:
    """Versioned draft hash; a template update must regenerate a reviewable draft."""
    source_digest = content_hash(profile)
    return hashlib.sha256(f"{source_digest}:{RENDERER_VERSION}:{template_digest()}".encode()).hexdigest()


def write_assets(directory: Path) -> None:
    presentation_assets(directory)


def render_readme(profile: dict) -> str:
    return presentation_readme(profile)


class Lock:
    def __init__(self, path: Path): self.path = path
    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                record = load_json(self.path); pid = int(record.get("pid", -1)); age = time.time() - self.path.stat().st_mtime
                alive = process_is_alive(pid)
                if alive or age < 300: raise RefreshError("another refresh appears to be running")
                self.path.unlink()
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except RefreshError: raise
            except Exception as exc: raise RefreshError(f"unsafe lock recovery: {exc}") from exc
        os.write(fd, json.dumps({"pid": os.getpid(), "created_at": now()}).encode()); os.close(fd); return self
    def __exit__(self, *_):
        self.path.unlink(missing_ok=True)


def process_is_alive(pid: int) -> bool:
    """Check lock ownership without signalling processes on Windows."""
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    process = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not process:
        # A caller unable to inspect another user's process must never steal its lock.
        return ctypes.get_last_error() == 5  # ERROR_ACCESS_DENIED
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code)):
            return True
        return exit_code.value == 259  # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(process)


def run_refresh(root: Path, offline: Path | None = None) -> dict:
    root = root.resolve(); config = load_json(root / "profile.config.json")
    output = root / "output"; run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run = output / run_id; receipt = {"run_id": run_id, "started_at": now(), "mode": "offline" if offline else "live", "stages": [], "status": "failed"}
    with Lock(root / ".profile-studio.lock"):
        try:
            source = Source(offline); profile = profile_from_evidence(source, config)
            source_digest = content_hash(profile); digest = artifact_hash(profile)
            run.mkdir(parents=True); evidence = run / "evidence"; evidence.mkdir()
            for index, (url, data) in enumerate(source.raw.items()): dump_json(evidence / f"{index:03d}.json", {"url": url, "retrieved_at": now(), "payload": data})
            dump_json(evidence / "manifest.json", {"source_urls": source.urls, "provenance": profile["status"]["source"]})
            receipt["stages"].append({"name": "fetch-and-validate", "status": "ok", "source_count": len(source.urls)})
            state_path = output / "state.json"; old = load_json(state_path) if state_path.exists() else {}; unchanged = old.get("content_hash") == digest
            files = []
            if not unchanged:
                draft = run / "profile"; draft.mkdir(); dump_json(draft / "profile.json", profile); write_assets(draft)
                (draft / "README.md").write_text(render_readme(profile), encoding="utf-8")
                files = [p for p in draft.rglob("*") if p.is_file()]
            manifest = {"content_hash": source_digest, "artifact_hash": digest, "renderer_version": RENDERER_VERSION, "files": {str(p.relative_to(run)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, "source_urls": source.urls, "kind": "evidence-only" if unchanged else "draft"}
            dump_json(run / "review-manifest.json", manifest)
            report = f"# Refresh review\n\n- Provenance: **{profile['status']['source']}**\n- Evidence timestamp: {profile['status']['evidence_at']}\n- Sources: {len(source.urls)}\n- Changed meaningful content: **{'no' if unchanged else 'yes'}**\n"
            if not unchanged:
                report += f"- Proposed bio: {profile['identity']['summary']}\n- Proposed pins: {', '.join(p['id'] for p in profile['projects']) or 'none'}\n\nNext step: inspect this draft and its evidence before any manual publication.\n"
            else:
                report += "\nNo draft was produced because the meaningful profile content is unchanged. This receipt preserves retrieval evidence only.\n"
            (run / "review-report.md").write_text(report, encoding="utf-8")
            if not unchanged:
                target = root / "site" / "public" / "profile.json"; target.parent.mkdir(parents=True, exist_ok=True); dump_json(target, profile)
                dump_json(state_path, {"content_hash": digest, "last_successful_run": run_id, "updated_at": now()})
            receipt.update({"status": "success", "finished_at": now(), "unchanged": unchanged, "content_hash": source_digest, "artifact_hash": digest, "renderer_version": RENDERER_VERSION})
            receipt["stages"].append({"name": "generate", "status": "ok", "published_local_artifact": not unchanged})
            dump_json(run / "receipt.json", receipt); dump_json(output / "last-receipt.json", receipt)
            return receipt
        except Exception as exc:
            run.mkdir(parents=True, exist_ok=True); receipt.update({"finished_at": now(), "error": str(exc)})
            receipt["stages"].append({"name": "refresh", "status": "failed", "error": str(exc)})
            dump_json(run / "receipt.json", receipt); dump_json(output / "last-receipt.json", receipt)
            raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m agent", description="Evidence-driven local profile refresh")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run"); run.add_argument("--offline", type=Path)
    watch = commands.add_parser("watch"); watch.add_argument("--interval", type=float, default=86400); watch.add_argument("--max-runs", type=int); watch.add_argument("--offline", type=Path)
    commands.add_parser("status")
    args = parser.parse_args(argv)
    if args.command == "status":
        path = args.root / "output" / "last-receipt.json"
        print(json.dumps(load_json(path) if path.exists() else {"status": "never-run"}, indent=2)); return 0
    if args.command == "watch":
        if not math.isfinite(args.interval) or args.interval <= 0:
            print("watch interval must be a finite positive number", file=sys.stderr); return 1
        if args.max_runs is not None and args.max_runs <= 0:
            print("watch max-runs must be a positive integer", file=sys.stderr); return 1
    runs = 0
    last_failed = False
    while True:
        try:
            result = run_refresh(args.root, getattr(args, "offline", None)); print(json.dumps(result, indent=2))
        except RefreshError as exc:
            print(f"refresh failed: {exc}", file=sys.stderr)
            last_failed = True
            if args.command == "run": return 1
        else:
            last_failed = False
        runs += 1
        if args.command == "run" or (args.max_runs is not None and runs >= args.max_runs):
            return 1 if last_failed else 0
        time.sleep(args.interval)
