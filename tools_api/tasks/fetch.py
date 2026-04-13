"""Fetch task wrappers. Heavy logic lives under ``app.fetch``."""

from invoke import Collection, Context, task


def _comma_set_codes(s: str) -> set[str]:
    return {p.strip().upper() for p in s.split(",") if p.strip()}


@task(default=True)
def all_sets(c: Context, bust_sld: bool = True, always_refresh: str = "") -> None:
    """Run MTGJSON fetch/ingest pipeline.

    ``bust_sld`` (default True) adds SLD to the cache-bust list. Use ``--no-bust-sld`` to skip.
    ``always_refresh`` is optional extra comma-separated set codes (merged with SLD when
    ``bust_sld`` is True). If the combined list is empty, ``--always-refresh`` is not passed.
    """
    codes: set[str] = set()
    if bust_sld:
        codes.add("SLD")
    codes |= _comma_set_codes(always_refresh)
    cmd = "uv run python -m app.cmd.mtgjson_fetch"
    if codes:
        arg = ",".join(sorted(codes))
        cmd += f' --always-refresh "{arg}"'
    c.run(cmd)


ns = Collection("fetch")
ns.add_task(all_sets, name="all_sets")
