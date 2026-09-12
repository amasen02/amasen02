"""GitHub-native, source-led profile presentation renderer."""
from __future__ import annotations

import hashlib
import html
from pathlib import Path
from urllib.parse import quote, urlparse

from . import github_art

TEMPLATE_VERSION = "github-source-matter-2026-09-12-v5"
DOT = "\N{MIDDLE DOT}"
DASH = "\N{EM DASH}"

FEATURES = {
    "polyai-dotnet": {
        "title": "PolyAI .NET",
        "category": "Provider boundaries / C#",
        "note": "One client across five provider adapters. Unknown provider names fail explicitly.",
        "source": "https://github.com/amasen02/polyai-dotnet/blob/main/src/PolyAI/Extensions/PolyAIRouter.cs",
    },
    "credscan": {
        "title": "CredScan",
        "category": "MCP secret scanning / Python",
        "note": "Inspects MCP environment values, headers and arguments while skipping environment-variable placeholders.",
        "source": "https://github.com/amasen02/credscan/blob/main/src/credscan/agent_artifacts.py",
    },
    "mcp-breakbench": {
        "title": "mcp-breakbench",
        "category": "MCP regression lab / Python",
        "note": "Runs explicit allowlisted cases against real stdio servers and records inspectable receipts.",
        "source": "https://github.com/amasen02/mcp-breakbench/blob/master/src/mcp_breakbench/runner.py",
    },
    "freshcart-backend": {
        "title": "FreshCart",
        "category": "Gateway scope / Angular + .NET",
        "note": "The Angular interceptor attaches credentials only to /api/ and /hubs/ requests.",
        "source": "https://github.com/amasen02/freshcart-web/blob/master/src/app/core/http/credentials.interceptor.ts",
    },
}

PLATES = {
    "polyai-dotnet": {"title": "PolyAI .NET", "category": "Provider boundaries / C#"},
    "credscan": {"title": "CredScan", "category": "MCP secret scanning / Python"},
    "centaurloop-agent-governor": {"title": "CentaurLoop", "category": "Coding-agent checks / Python"},
    "freshcart-backend": {"title": "FreshCart", "category": "Gateway scope / Angular + .NET"},
    "freshcart-web": {"title": "FreshCart Web", "category": "Signals and auth / Angular"},
    "dupesweep": {"title": "DupeSweep", "category": "Reversible file operations / C#"},
    "a11y-scope": {"title": "a11y-scope", "category": "Accessibility inspection / Playwright"},
}

PROJECT_SOURCES = {
    "polyai-dotnet": {
        "readme": "https://github.com/amasen02/polyai-dotnet/blob/main/README.md",
        "tools": "https://github.com/amasen02/polyai-dotnet/blob/main/src/PolyAI/Tools/ToolRegistry.cs",
    },
    "credscan": {
        "artifacts": "https://github.com/amasen02/credscan/blob/main/src/credscan/agent_artifacts.py",
        "git": "https://github.com/amasen02/credscan/blob/main/src/credscan/git_integration.py",
    },
    "mcp-breakbench": {
        "readme": "https://github.com/amasen02/mcp-breakbench/blob/master/README.md",
        "runner": "https://github.com/amasen02/mcp-breakbench/blob/master/src/mcp_breakbench/runner.py",
        "snapshot": "https://github.com/amasen02/mcp-breakbench/blob/master/src/mcp_breakbench/snapshot.py",
    },
    "freshcart-backend": {
        "checkout": "https://github.com/amasen02/freshcart-backend/blob/master/src/Services/Ordering/FreshCart.Ordering.Application/Checkout/CheckoutSagaStateMachine.cs",
        "payments": "https://github.com/amasen02/freshcart-backend/blob/master/src/Services/Payment/FreshCart.Payment.Infrastructure/EventStore/MongoPaymentEventStore.cs",
        "ci": "https://github.com/amasen02/freshcart-backend/blob/master/.github/workflows/reusable-build-test.yml",
    },
    "freshcart-web": {
        "auth": "https://github.com/amasen02/freshcart-web/blob/master/src/app/core/http/credentials.interceptor.ts",
        "readme": "https://github.com/amasen02/freshcart-web/blob/master/README.md",
    },
    "a11y-scope": {
        "readme": "https://github.com/amasen02/a11y-scope/blob/main/README.md",
    },
}

CONTRIBUTION_HIGHLIGHTS = {
    "https://github.com/BerriAI/litellm/pull/39729": {
        "repository": "BerriAI/litellm",
        "summary": "Made budget resets invalidate the affected end-user spend counter and cache.",
    },
    "https://github.com/fleetdm/fleet/pull/52620": {
        "repository": "fleetdm/fleet",
        "summary": "Prevented Windows client-certificate validity from being truncated to one year.",
    },
    "https://github.com/Arize-ai/phoenix/pull/15964": {
        "repository": "Arize-ai/phoenix",
        "summary": "Removed a return from a finally block in playground_users.get_user to resolve a PEP 765 diagnostic.",
    },
}


def esc(value: object) -> str:
    """Escape untrusted evidence for Markdown text, without producing HTML."""
    text = str(value).replace("\r", " ").replace("\n", " ")
    for character in "\\`*_[]<>":
        text = text.replace(character, f"\\{character}")
    return text


def _safe_href(value: object) -> str:
    """Return a safely quoted HTTPS href, or reject malformed evidence."""
    raw = str(value)
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("presentation requires an absolute HTTPS URL")
    return html.escape(raw, quote=True)


def _mailto_href(email: object) -> str:
    address = str(email).strip()
    if not address or any(character in address for character in "\r\n?&#"):
        raise ValueError("presentation requires a plain email address")
    subject = quote(f"Engineering role {DASH} Ama Senevirathne", safe="")
    return html.escape(f"mailto:{address}?subject={subject}", quote=True)


def hero_svg(animated: bool) -> str:
    return github_art.hero_svg(animated)


def validate_svg(svg: str) -> None:
    github_art.validate_svg(svg)


def template_digest() -> str:
    source = "".join(
        (
            TEMPLATE_VERSION,
            Path(__file__).read_text(encoding="utf-8"),
            Path(github_art.__file__).read_text(encoding="utf-8"),
            github_art.source_matter_digest(),
        )
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def write_assets(directory: Path) -> None:
    """Write only rendered, self-contained GitHub assets into a draft."""
    target = directory / "assets"
    target.mkdir(parents=True, exist_ok=True)
    for filename, animated in (("hero.svg", True), ("hero-static.svg", False)):
        svg = hero_svg(animated)
        validate_svg(svg)
        (target / filename).write_text(svg, encoding="utf-8")
    for number, (project_id, plate) in enumerate(PLATES.items(), 1):
        for animated in (True, False):
            svg = github_art.plate_svg(project_id, plate["title"], plate["category"], number, animated)
            validate_svg(svg)
            suffix = "" if animated else "-static"
            (target / f"plate-{project_id}{suffix}.svg").write_text(svg, encoding="utf-8")


def _hero_block(identity: dict) -> list[str]:
    github = _safe_href(identity["github"])
    linkedin = _safe_href(identity["linkedin"])
    email = _mailto_href(identity["email"])
    contacts = [f"[Discuss an engineering role]({email})", f"[LinkedIn]({linkedin})"]
    for label, key in (("DEV.to", "devto"), ("X", "x")):
        if identity.get(key):
            contacts.append(f"[{label}]({_safe_href(identity[key])})")
    contacts.append(f"[GitHub]({github})")
    contact = f" {DOT} ".join(contacts)
    return [
        f"# {esc(identity['name'])}",
        "",
        f"**AI / agent engineer {DOT} Full-stack software engineer**",
        "",
        contact,
        "",
        '<p align="center">',
        "  <picture>",
        '    <source media="(prefers-reduced-motion: reduce)" srcset="assets/hero-static.svg">',
        f'    <img src="assets/hero.svg" alt="Source into form {DASH} authored architectural illustration" width="100%">',
        "  </picture>",
        "</p>",
        "",
        "I build and test the boundaries around AI systems: provider integrations, tool calling, security tooling, distributed backends, and the interfaces people use. My source includes [PolyAI .NET](https://github.com/amasen02/polyai-dotnet), [CredScan](https://github.com/amasen02/credscan), and [mcp-breakbench](https://github.com/amasen02/mcp-breakbench).",
        "",
    ]


def _project_proof(project: dict, project_id: str) -> list[str]:
    repository = _safe_href(project["url"])
    source = PROJECT_SOURCES[project_id]
    if project_id == "polyai-dotnet":
        text = (
            "C# multi-provider SDK with streaming, structured output, and runtime tool discovery. "
            "Tool schemas follow runtime types and reject unsupported parameter shapes. "
            f"[README]({_safe_href(source['readme'])}) {DOT} "
            f"[ToolRegistry]({_safe_href(source['tools'])}) {DOT} "
            f"[Provider routing]({_safe_href(FEATURES[project_id]['source'])})"
        )
    elif project_id == "credscan":
        text = (
            "Python scanning for source, staged changes, and agent configuration. It inspects MCP "
            "environment values, headers, and arguments, and reads Git index blobs so staged content "
            "is scanned as staged. "
            f"[Agent artifacts]({_safe_href(source['artifacts'])}) {DOT} "
            f"[Git integration]({_safe_href(source['git'])})"
        )
    elif project_id == "mcp-breakbench":
        text = (
            "Python MCP interoperability and regression lab that launches configured servers over "
            "stdio, snapshots advertised tool contracts, and runs explicit allowlisted cases with "
            "deterministic JSON receipts. "
            f"[README]({_safe_href(source['readme'])}) {DOT} "
            f"[Runner]({_safe_href(source['runner'])}) {DOT} "
            f"[Contract diff]({_safe_href(source['snapshot'])})"
        )
    else:
        text = (
            "A .NET / Aspire reference backend with an Angular storefront. Checkout state explicitly "
            "models stock and payment success or failure; activities and consumers isolate side effects; "
            "payment events and a projection marker share one MongoDB transaction. "
            f"[Checkout state machine]({_safe_href(source['checkout'])}) {DOT} "
            f"[Payment event store]({_safe_href(source['payments'])}) {DOT} "
            f"[Build and test workflow]({_safe_href(source['ci'])})"
        )
    return [f"### [{esc(project['title'])}]({repository})", text, ""]


def _featured_build(project: dict, project_id: str) -> list[str]:
    return [
        _project_plate(project, project_id),
        "",
        *_project_proof(project, project_id),
    ]


def _project_plate(project: dict, project_id: str) -> str:
    plate = PLATES[project_id]
    repository = _safe_href(project["url"])
    title = html.escape(str(project["title"]), quote=True)
    category = html.escape(plate["category"], quote=True)
    return (
        f'<a href="{repository}"><picture>'
        f'<source media="(prefers-reduced-motion: reduce)" srcset="assets/plate-{project_id}-static.svg">'
        f'<img src="assets/plate-{project_id}.svg" alt="{title} {DASH} {category}" width="100%">'
        "</picture></a>"
    )


def _evidence_href(project: dict, label: str) -> str:
    evidence = project.get("evidence")
    if not isinstance(evidence, list):
        raise ValueError(f"{project.get('id', 'project')} requires {label} evidence")
    for item in evidence:
        if isinstance(item, dict) and item.get("label") == label:
            return _safe_href(item.get("url", ""))
    raise ValueError(f"{project.get('id', 'project')} requires {label} evidence")


def _selected_builds(projects: dict) -> list[str]:
    lines: list[str] = []
    ai_projects = [
        project_id
        for project_id in ("polyai-dotnet", "credscan", "mcp-breakbench")
        if project_id in projects
    ]
    centaurloop = projects.get("centaurloop-agent-governor")
    if ai_projects or centaurloop:
        lines.extend(["## AI & agent systems", ""])
        for project_id in ai_projects:
            if project_id == "mcp-breakbench":
                lines.extend(_project_proof(projects[project_id], project_id))
            else:
                lines.extend(_featured_build(projects[project_id], project_id))
        if centaurloop:
            repository = _safe_href(centaurloop["url"])
            implementation = _evidence_href(centaurloop, "Implementation")
            lines.extend(
                [
                    _project_plate(centaurloop, "centaurloop-agent-governor"),
                    "",
                    f"### [{esc(centaurloop['title'])}]({repository})",
                    "Python experiments for coding-agent guardrails: syntax checks, forbidden-phrase checks, and compact execution logs. "
                    f"[Implementation]({implementation})",
                    "",
                ]
            )
    freshcart = projects.get("freshcart-backend")
    if freshcart:
        lines.extend(["## Full-stack systems", "", *_featured_build(freshcart, "freshcart-backend")])
    return lines


def _remaining_projects(projects: dict) -> list[str]:
    remaining = [
        project
        for project_id, project in projects.items()
        if project_id not in FEATURES and project_id != "centaurloop-agent-governor"
    ]
    if not remaining:
        return []
    lines = ["## More source", ""]
    for project in remaining:
        project_id = project["id"]
        repository = _safe_href(project["url"])
        title = esc(project["title"])
        if project_id == "freshcart-web":
            text = f"Angular storefront with signals and HttpOnly-cookie sessions. [Auth boundary]({_safe_href(PROJECT_SOURCES[project_id]['auth'])})"
        elif project_id == "dupesweep":
            text = "C# duplicate-file tooling with reversible quarantine and restore."
        elif project_id == "a11y-scope":
            text = f"Accessibility monitoring with Playwright and axe-core. [README]({_safe_href(PROJECT_SOURCES[project_id]['readme'])})"
        else:
            text = esc(project["summary"])
        if project_id in PLATES:
            lines.append(_project_plate(project, project_id))
        lines.extend(["", f"### [{title}]({repository})", text, ""])
    return [*lines, ""]


def _capability_map(projects: dict) -> list[str]:
    claims: list[str] = []
    if "polyai-dotnet" in projects:
        claims.append(
            f"- **AI integrations and tools** {DASH} C# provider boundaries, JSON Schema, streaming, "
            f"and structured output. [Evidence]({_safe_href(PROJECT_SOURCES['polyai-dotnet']['readme'])})"
        )
    if "credscan" in projects:
        claims.append(
            f"- **Agent security** {DASH} Python inspection of MCP configuration and staged Git content. "
            f"[Evidence]({_safe_href(PROJECT_SOURCES['credscan']['artifacts'])})"
        )
    if "mcp-breakbench" in projects:
        claims.append(
            f"- **MCP interoperability** {DASH} real stdio probes, contract snapshots, explicit "
            "allowlists, and typed receipts. "
            f"[Evidence]({_safe_href(PROJECT_SOURCES['mcp-breakbench']['runner'])})"
        )
    if "freshcart-backend" in projects:
        source = PROJECT_SOURCES["freshcart-backend"]
        claims.extend(
            [
                f"- **Distributed systems** {DASH} MassTransit state machines and transactional event storage. "
                f"[Evidence]({_safe_href(source['checkout'])})",
                f"- **Data and recovery** {DASH} MongoDB event storage and projection markers in one transaction. "
                f"[Evidence]({_safe_href(source['payments'])})",
            ]
        )
    if "freshcart-web" in projects:
        source = PROJECT_SOURCES["freshcart-web"]
        claims.append(
            f"- **Frontend** {DASH} Angular, TypeScript, signals, and a deliberately scoped auth boundary. "
            f"[README]({_safe_href(source['readme'])}) {DOT} [Auth boundary]({_safe_href(source['auth'])})"
        )
    delivery = "freshcart-backend" in projects
    accessibility = "a11y-scope" in projects
    if delivery and accessibility:
        claims.append(
            f"- **Delivery and accessibility** {DASH} reusable restore, build, and test workflow; "
            "Playwright and axe-core monitoring described in the project README. "
            f"[Workflow]({_safe_href(PROJECT_SOURCES['freshcart-backend']['ci'])}) {DOT} "
            f"[README]({_safe_href(PROJECT_SOURCES['a11y-scope']['readme'])})"
        )
    elif delivery:
        claims.append(
            f"- **Delivery** {DASH} reusable restore, build, and test workflow. "
            f"[Evidence]({_safe_href(PROJECT_SOURCES['freshcart-backend']['ci'])})"
        )
    elif accessibility:
        claims.append(
            f"- **Accessibility** {DASH} Playwright and axe-core monitoring described in the project README. "
            f"[Evidence]({_safe_href(PROJECT_SOURCES['a11y-scope']['readme'])})"
        )
    return ["## Engineering range", "", *claims, ""] if claims else []


def _verified_contributions(contributions: list[dict]) -> list[dict]:
    return [
        item
        for item in contributions
        if item.get("state") == "merged" and isinstance(item.get("url"), str)
    ]


def _contribution_block(
    contributions: list[dict], coverage: dict | None
) -> list[str]:
    verified = _verified_contributions(contributions)
    if not verified:
        return []
    grouped: dict[str, list[dict]] = {}
    for item in verified:
        grouped.setdefault(str(item["repository"]), []).append(item)
    lines = ["## Open-source contributions", ""]
    record_count = len(verified)
    repository_count = len({repository.casefold() for repository in grouped})
    complete = False
    if isinstance(coverage, dict) and coverage.get("complete") is True:
        count = coverage.get("external_merged_count")
        repositories = coverage.get("external_repository_count")
        search_url = coverage.get("search_url")
        if (
            count == record_count
            and repositories == repository_count
            and isinstance(search_url, str)
        ):
            lines.extend(
                [
                    f"**{record_count} verified merged pull requests across {repository_count} repositories**. [Live GitHub search]({_safe_href(search_url)})",
                    "",
                ]
            )
            complete = True
    if len(lines) == 2:
        lines.extend([f"**{len(verified)} verified merged pull requests**", ""])
    repositories = [
        f"[{esc(repository)}]({_safe_href(f'https://github.com/{repository}')})"
        for repository in sorted(grouped, key=str.casefold)
    ]
    lines.extend([f"**Repositories:** {f' {DOT} '.join(repositories)}", "", "## Selected upstream merges", ""])
    ranked = {url: rank for rank, url in enumerate(CONTRIBUTION_HIGHLIGHTS)}
    prioritized = sorted(
        verified,
        key=lambda item: ranked.get(item["url"], len(ranked)),
    )
    selected: list[str] = []
    for item in prioritized:
        highlight = CONTRIBUTION_HIGHLIGHTS.get(item["url"])
        if highlight and highlight["repository"] == item.get("repository"):
            summary = highlight["summary"]
        else:
            summary = esc(item["title"])
        selected.append(f"- **[{esc(item['repository'])}]({_safe_href(item['url'])})** {DASH} {summary}")
        if len(selected) == 3:
            break
    summary = (
        f"Full merged-PR catalog ({record_count})"
        if complete
        else f"Verified PR records ({record_count})"
    )
    lines.extend([*selected, "", f"<details><summary>{summary}</summary>", ""])
    for repository in sorted(grouped, key=str.casefold):
        lines.extend([f"#### [{esc(repository)}]({_safe_href(f'https://github.com/{repository}')})", ""])
        for item in grouped[repository]:
            lines.append(
                f"- [{esc(item['title'])}]({_safe_href(item['url'])})"
            )
        lines.append("")
    return [*lines, "", "</details>", ""]


def render_contributions(contributions: list[dict], coverage: dict | None) -> str:
    return "\n".join(_contribution_block(contributions, coverage))


def render_readme(profile: dict) -> str:
    """Render evidence fields as Markdown text and HTML attributes at their creation sites."""
    projects = {project["id"]: project for project in profile.get("projects", [])}
    lines = _hero_block(profile["identity"])
    lines.extend(_selected_builds(projects))
    lines.extend(_remaining_projects(projects))
    lines.extend(_capability_map(projects))
    lines.extend(["<!-- BEGIN AUTO-CONTRIBUTIONS -->", ""])
    contribution_text = render_contributions(profile.get("contributions", []), profile.get("contribution_coverage"))
    if contribution_text:
        lines.extend(contribution_text.splitlines())
    lines.extend(["", "<!-- END AUTO-CONTRIBUTIONS -->", ""])
    lines.extend(
        [
            "---",
            "",
            "_Sources: public GitHub repository and pull-request records._",
            "",
        ]
    )
    return "\n".join(lines)
