from __future__ import annotations

import unittest

from agent.presentation import render_contributions, render_readme


class ContributionHighlightTests(unittest.TestCase):
    def test_selected_merges_prefer_curated_substantive_fixes(self) -> None:
        contributions = [
            {
                "repository": "docs/example",
                "title": "docs: fix a typo",
                "url": "https://github.com/docs/example/pull/1",
                "state": "merged",
            },
            {
                "repository": "Arize-ai/phoenix",
                "title": "fix(server): remove PEP 765 return in finally",
                "url": "https://github.com/Arize-ai/phoenix/pull/15964",
                "state": "merged",
            },
            {
                "repository": "fleetdm/fleet",
                "title": "fix(mdm): prevent windows client certificate lifetime truncation",
                "url": "https://github.com/fleetdm/fleet/pull/52620",
                "state": "merged",
            },
            {
                "repository": "BerriAI/litellm",
                "title": "fix(proxy): invalidate end-user spend counter and cache",
                "url": "https://github.com/BerriAI/litellm/pull/39729",
                "state": "merged",
            },
        ]

        selected = render_contributions(contributions, None).split("<details>", 1)[0]

        expected_urls = [
            "https://github.com/BerriAI/litellm/pull/39729",
            "https://github.com/fleetdm/fleet/pull/52620",
            "https://github.com/Arize-ai/phoenix/pull/15964",
        ]
        positions = [selected.index(url) for url in expected_urls]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("https://github.com/docs/example/pull/1", selected)

    def test_profile_renders_source_backed_breakbench_entry_without_new_art(self) -> None:
        profile = {
            "identity": {
                "name": "Ama Senevirathne",
                "email": "ama@example.com",
                "github": "https://github.com/amasen02",
                "linkedin": "https://www.linkedin.com/in/ama-sen/",
            },
            "projects": [
                {
                    "id": "mcp-breakbench",
                    "title": "mcp-breakbench",
                    "url": "https://github.com/amasen02/mcp-breakbench",
                    "summary": "A reproducible MCP contract and fault lab",
                }
            ],
            "contributions": [],
        }

        rendered = render_readme(profile)

        self.assertIn("### [mcp-breakbench]", rendered)
        self.assertIn("launches configured servers over stdio", rendered)
        self.assertIn("src/mcp_breakbench/runner.py", rendered)
        self.assertNotIn("plate-mcp-breakbench", rendered)


if __name__ == "__main__":
    unittest.main()
