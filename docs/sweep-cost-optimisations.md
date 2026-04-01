# Tag Sweep Cost Optimisations

Tracked improvements to reduce token cost for `generate.tags` while maintaining accuracy.
Background: switching from `claude-haiku-4-5` to `claude-sonnet-4-6` is necessary for classification quality (Haiku was tagging cards whose own reason said "no mana production"), raising the per-sweep cost from ~$9.50 to ~$35.60. The items below target ~$15–18 for a full sweep with Sonnet.

---

## 1. Prompt caching via system-prompt consolidation

**What:** Move the tag description out of the user message and into the system prompt, so every page of a sweep pays 0.1× the input price for the stable tokens after the first request.

**Current structure:**
- System prompt: static tagger instructions (`system_prompt.md`)
- User message: `{tag_description}\n\nCards:\n{cards_json}` (from `user_prompt.md`)

**Target structure:**
- System prompt: static instructions + tag description (built once in `SweepClaudeClient.__init__`, passed `cache_control: {"type": "ephemeral"}` in the SDK call)
- User message: just the cards JSON array — `user_prompt.md` is removed entirely

**Code changes:**
- `SweepClaudeClient.__init__` gains a `tag_description: str` parameter; concatenates it onto the static system prompt at construction time
- `SweepClaudeClient.call()` drops `tag_description`; user message is just the serialised card list
- SDK `.messages.create()` call changes `system=SYSTEM_PROMPT` (string) to `system=[{"type": "text", "text": ..., "cache_control": {"type": "ephemeral"}}]` (list)
- Client construction moves into `_run()` after the tag is resolved (currently constructed before tag description is known)
- `user_prompt.md` deleted

**Estimated saving:** ~$5 per full sweep (700 stable tokens × 2,638 pages × 90% cache discount).

---

## 2. Compact JSON serialisation

**What:** Remove indentation from the cards JSON sent to Claude.

**Change:** In `claude_client.py` `_build_user_message`, replace `json.dumps(cards, indent=2)` with `json.dumps(cards, separators=(',', ':'))`.

**Estimated saving:** 15–20% of the cards block size (~2k tokens per request across a full sweep).

---

## 3. Strip reminder text from oracle_text

**What:** Reminder text is parenthesised explanatory text that appears in rules text to clarify keywords (e.g. `Flying (This creature can't be blocked except by creatures with flying or reach.)`). It is non-binding and never relevant to classification. Stripping it before serialisation reduces oracle_text size without losing any information Claude needs.

**Confirmed safe:**
- The `text` field in the payload is `card.oracle_text` — pure rules text only. Flavor text is a separate MTGJSON field and is not stored in the model at all, so there is no flavor text to worry about.
- All parenthetical text in oracle_text is reminder text. No other use of parentheses appears in MTG oracle text.

**Change:** Add a `_strip_reminder_text(text: str) -> str` helper in `card_payload.py` that removes `\s*\([^)]+\)` matches, and call it on `card.oracle_text` before inserting into the payload dict.

**Estimated saving:** Varies by card. Keyword-heavy cards (e.g. `Flying (...) First strike (...) Trample (...)`) can be 50–100 chars shorter. Across a full sweep, probably 5–10% off the cards block.

---

## 4. Batch size is now a tuning knob, not a fixed default

**What:** With prompt caching (item 1), the system prompt + tag description tokens are billed at 0.1× after the first page. This changes the economics: the fixed overhead per batch is nearly free, so the cost is dominated almost entirely by per-card oracle_text tokens regardless of batch size. This makes very small batches (even batch=1) cost-comparable to the current batch=20 without caching.

**Cost breakdown at 52k oracle IDs (Sonnet + caching, after reminder-text strip and compact JSON):**

| Batch size | Requests | Cost (est.) |
|---|---|---|
| 1 | 52,760 | ~$32 |
| 5 | 10,552 | ~$30 |
| 20 | 2,638 | ~$28 |
| 40 | 1,319 | ~$27 |

The differences are small. Batch=40 is modestly cheaper than batch=1 but not dramatically so — the savings come from the other items, not batch size.

**Haiku + batch=1 as a quality experiment:**
The two distinct Haiku failure modes observed in the audit are:
1. **Cross-card reason contamination** — reason for card A is written for a different card B in the same batch (e.g. Mindswipe's reason describes Chandra's ability). Eliminated entirely at batch=1.
2. **Wrong bucket despite correct reasoning** — Haiku correctly writes "no mana production; not a mana rock or mana dork" but still places the card in `tag`. This is a fundamental Haiku reliability issue unrelated to batch size and would persist at batch=1.

With caching, Haiku batch=1 costs ~$12 for a full sweep (vs $9.50 current, vs $32 Sonnet). It is worth running as a test to quantify how many false positives are caused by type-1 vs type-2 failures. If type-2 turns out to be rare, Haiku batch=1 may be a viable cheap option.

**Change:** Keep `tag_sweep_limit` in `settings.py` as the tuning knob. Ensure value `1` is valid (it already is — `ge=1`). No logic changes needed.

---

## 5. Card type / supertype include list on the tag model

**What:** Each tag can optionally declare which card types and/or supertypes are eligible for its sweep. Cards not matching the include list are skipped entirely — never sent to Claude. This is schema-level filtering only; it does not pre-judge rules text.

**Examples:**
- A `ramp` tag might include types `creature`, `artifact`, `enchantment`, `planeswalker` — lands are never ramp (already excluded by the description), and this avoids sending 20k+ land oracle IDs to Claude
- A `removal` tag might include types `instant`, `sorcery`, `creature` for permanent-based removal
- No rows in the include table = all card types are swept (current behaviour, preserved as default)

**Design: include lists as FK child tables**

Two new child tables hanging off `magic_boto.tags` — same pattern as `card_types` / `card_supertypes` hang off `cards`:

```
magic_boto.tag_sweep_include_types
  tag_id     UUID  PK, FK → magic_boto.tags.id  ON DELETE CASCADE
  card_type  TEXT  PK

magic_boto.tag_sweep_include_supertypes
  tag_id          UUID  PK, FK → magic_boto.tags.id  ON DELETE CASCADE
  card_supertype  TEXT  PK
```

No rows for a tag = no filter on that dimension. Deleting a tag cascades automatically.

**Schema / model changes:**
- Migration: create the two tables
- `MagicBotoTagSweepIncludeTypeModel` and `MagicBotoTagSweepIncludeSupertypeModel` ORM models (same pattern as `MagicBotoCardTypeModel`)
- `MagicBotoTagModel` gains two `relationship` fields: `sweep_include_types` and `sweep_include_supertypes` (both `lazy="selectin"`, `cascade="all, delete-orphan"`)
- `tag_schema.py` `Tag` schema: add `sweep_include_types: Sequence[str]` and `sweep_include_supertypes: Sequence[str]` (empty list = no filter)
- `tag_service.py` `create_tag`: accept and persist the new fields

**Sweep integration:**
- `OracleTagSweepService._fetch_page` takes the tag model and, when its include lists are non-empty, adds an `EXISTS` subquery or `INNER JOIN` against `card_types` / `card_supertypes`
- `resume_sweep` and `advance_and_fetch` load the tag model (already resolved for the tag_id) and pass it into `_fetch_page`

**Surface area — `sweep_include_types` and `sweep_include_supertypes` are first-class tag fields:**

These are properties of the tag itself, not sweep-specific config. Every interface that creates or reads a tag must expose them:
- `tag_service.py` `create_tag` and any future `update_tag`: accept and persist both fields
- HTTP `POST /tags` and `GET /tags/{name}`: include in request body and response
- MCP `create_tag` tool: optional parameters in the tool schema
- MCP `get_tag` / `list_tags` tools: include in returned tag objects
- CLI `tag create` (if it exists): optional flags

The `Tag` schema dataclass in `tag_schema.py` is the single source of truth — updating it propagates to all serialisation points automatically.

**Estimated saving:** Highly tag-dependent. For a ramp sweep, omitting all lands (~20k oracle IDs out of ~52k) cuts the sweep nearly in half.

---

## 6. Verification pass as a separate sweep task

**What:** A standalone task — `generate.verify-tags` — that iterates over already-tagged cards for a given tag, re-presents each card to a model alongside its stored `reason`, and asks the simpler binary question: "does this reason actually support tagging this card?" Cards that fail verification are untagged (or moved to `{tag}_unsure` for manual review).

This is designed as a complement to a Haiku sweep, catching the two failure modes Haiku exhibits:
- **Type 1 — cross-card reason contamination** (reason describes a different card): eliminated at batch=1 during the sweep, but the verify pass catches any that slipped through from larger batches
- **Type 2 — correct reason, wrong bucket** (reason says "no mana production" but card was tagged anyway): the verify pass confronts Haiku's own contradiction with a much simpler, binary task that the model handles reliably

**What it does not catch:**
- **Type 3 — hallucinated abilities** (model fabricates rules text that doesn't exist on the card, e.g. claiming a card "taps for {G}" when it has no such ability): if the same model hallucinated the ability in pass 1, it may repeat the hallucination in pass 2. The verify pass reduces but does not eliminate this risk. Sonnet remains the safer choice for tags where subtle fabrication is a concern.

**Prompt design:**
The verify pass system prompt is distinct from the sweep system prompt — it receives:
- The tag description (cached, same caching strategy as item 1)
- For each card: `name`, `oracle_text`, and the stored `reason` from the original sweep

It asks only: does the stated reason actually justify this tag given the card's actual text and the tag criteria? Reply with `keep` or `remove` (plus an optional correction note). No re-classification from scratch.

**Implementation:**
- New entrypoint `app/tag/verify/main.py`, wired as `uv run invoke generate.verify-tags --tag <name>`
- New `claude_client.py` under `app/tag/verify/` with its own system and user prompts — separate from the sweep client
- Uses `tag_service.sample_cards_for_tag` (which already returns `(card, reason)` pairs) but needs a full-scan variant rather than a random sample — add `list_cards_for_tag` to `TagService` that pages through all tagged oracle IDs
- On `remove` verdict: calls `tag_service.remove_card_tags` or `add_card_tags` against `{tag}_unsure`
- Batch size: can be larger than the sweep (batch=20 is fine — the task is simpler and reason+card text is the full context per card with no cross-card ambiguity risk)
- Model: configurable via settings (`tag_verify_model`), defaults to same model as sweep; can be set to Haiku even if sweep uses Sonnet since verification is an easier task

**Cost at batch=20, Haiku, with caching (verifying 10% tagged from a 52k sweep):**
~5,200 cards / 20 per batch = 260 requests × ~$0.0004/request ≈ **~$0.10**

Even at Sonnet for verification: ~260 × ~$0.013 ≈ **~$3.40**

The verify pass is cheap regardless of model because the tagged population is small relative to the full catalog.

**Haiku sweep + Haiku verify vs Sonnet sweep:**

| Option | Cost | Type 1 risk | Type 2 risk | Type 3 risk |
|---|---|---|---|---|
| Haiku batch=20, no verify | ~$9.50 | High | High | Medium |
| Haiku batch=1, no verify | ~$18 | None | High | Medium |
| Haiku batch=1 + verify | ~$20 | None | Low | Medium |
| Sonnet batch=40 | ~$27–32 | None | None | Low |

Haiku batch=1 + verify is the cost-competitive option. Sonnet remains the quality ceiling.

---

## Separate issue: replace `pg_insert` with portable upsert

`tag_service.py` `add_card_tags` uses `sqlalchemy.dialects.postgresql.insert` for its `ON CONFLICT DO UPDATE` / `ON CONFLICT DO NOTHING` upsert. This is the only PostgreSQL-dialect-specific construct in the service layer. It should be replaced with a portable alternative (e.g. `merge` via SQLAlchemy 2's `merge` statement, or a select-then-insert/update pattern) so the service layer has no dialect dependency. Tracked here as a related housekeeping item; not a blocker for the optimisations above.
