"""
RuleMapper — identifies which GFR/DPP rules are implicated by a query/answer.

Loads the hand-curated compliance_rules.json graph and matches rules
to retrieved chunks and query entities.
"""

from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_RULES_PATH = Path(__file__).parent.parent.parent / "config" / "compliance_rules.json"


class RuleMapper:
    """
    Matches procurement rules from compliance_rules.json to a query/answer context.
    """

    def __init__(self, rules_path: Path = DEFAULT_RULES_PATH):
        self.rules: List[dict] = []
        self._load_rules(rules_path)

    def map_rules(
        self,
        query: str,
        llm_response: str,
        retrieved_chunks: list,
    ) -> List[dict]:
        """
        Returns a list of applicable rule dicts from the compliance graph.
        Each dict has: rule_id, title, conditions, prerequisites, severity
        """
        text_corpus = " ".join([
            query,
            llm_response,
            " ".join(getattr(c, "text", "") for c in retrieved_chunks),
        ])

        matched = []
        for rule in self.rules:
            if self._rule_matches(rule, text_corpus):
                matched.append(rule)

        logger.info("RuleMapper: %d rules matched for query", len(matched))
        return matched

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_rules(self, path: Path):
        try:
            with open(path) as f:
                data = json.load(f)
            self.rules = data.get("rules", [])
            logger.info("RuleMapper: loaded %d rules from %s", len(self.rules), path)
        except FileNotFoundError:
            logger.warning("compliance_rules.json not found at %s; using empty ruleset", path)
            self.rules = []
        except json.JSONDecodeError as e:
            logger.error("Failed to parse compliance_rules.json: %s", e)
            self.rules = []

    def _rule_matches(self, rule: dict, text: str) -> bool:
        """A rule matches if any of its trigger keywords appear in the text."""
        triggers = rule.get("triggers", [])
        if not triggers:
            return False
        text_lower = text.lower()
        return any(
            re.search(re.escape(trigger.lower()), text_lower)
            for trigger in triggers
        )