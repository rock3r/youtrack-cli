"""YouTrack search query composer (brace-wrapping, sort syntax, AND-composition)."""

from __future__ import annotations


def compose_query(
    *,
    all: bool = False,
    project: str | None = None,
    state: str | None = None,
    assignee: str | None = None,
    query: str | None = None,
    sort: str | None = None,
) -> str:
    """Build a YouTrack search query from CLI flags.

    Rules:
    * Default (no flags): ``for: me #Unresolved``.
    * ``--all``: remove the default ``for: me #Unresolved`` filter.
    * ``--query``: overrides the default filter and all positional filters.
    * Other filters are appended after the base query.
    * ``--sort`` is appended with the YouTrack ``sort by:`` syntax.
    """
    if query is not None:
        q = query
    elif all:
        q = ""
    else:
        q = "for: me #Unresolved"

    filters: list[str] = []
    if query is None:
        if project:
            filters.append(f"project: {project}")
        if state:
            filters.append(f"state: {state}")
        if assignee:
            filters.append(f"assignee: {assignee}")
    if filters:
        q = f"{q} {' '.join(filters)}".strip()
    if sort:
        q = f"{q} sort by: {sort}".strip()
    return q
