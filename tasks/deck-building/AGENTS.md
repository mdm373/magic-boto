# Deck building instructions

When asked about information on Magic cards, **always use the magic-boto MCP tools** (e.g. card search / get card / edition lookup).

Never use web searches for card facts.

Never query the database directly (no SQL / no direct Postgres access) for deck-building questions.

If you get stuck because the MCP is missing a filter/field:
- Clearly state **what MCP capability is missing** (e.g. “need color identity filter”, “need card_type=creature filter”, “need aggregate count endpoint”).
- Provide a concrete suggestion for the **smallest MCP/tooling change** that would unblock the question (schema field, new filter, or a purpose-built endpoint).
- If possible, suggest an MCP-only workaround (e.g. broader search + client-side filtering on returned fields).