# Eval iteration 1

Date: 2026-07-02
Model: google/gemini-3.5-flash
Method: Parallel subagent runs, each prompt answered with `skills/youtrack-cli/SKILL.md` loaded.

## Results summary

| Eval | Name | Status | Notes |
|---|---|---|---|
| search-open-project | Search open issues in a project | ✅ Pass | Gave `yt issues --all --project JT --state Open --limit 30`. Added `--all` as a safe override for the default user-unresolved filter. |
| create-bug | Create a bug with type and priority | ✅ Pass | Gave exact expected command; one subagent tool run reported "failure" but produced the correct answer. |
| global-option-order | Global option placement gotcha | ✅ Pass | Correctly identified `yt --output json issues`. |
| auth-login | Persist credentials | ✅ Pass | Recommended `yt auth login` and explained config file + env alternatives. |
| op-precedence | 1Password is the last token source | ✅ Pass | Explained `YOUTRACK_TOKEN` wins over `--op-*` and the full resolver order. |
| edit-command-language | Use raw command language for edits | ✅ Pass | Provided both `--field` and `--command` options. |
| multi-value-field | Multi-value field syntax | ✅ Pass | Provided comma-separated `--field` example. |
| comment-and-link | Comment and link issues | ✅ Pass | Provided both `yt comment` and `yt link` commands. |

**Score: 8/8 content expectations met.**

## Observations

- The skill correctly guides global option placement (the most common gotcha).
- Agents are not over-eager about adding `--all`, but when they do it is harmless and helpful.
- The resolver precedence (especially 1Password fallback) is understood and explained well.
- No hallucinated flags or incorrect command ordering observed.

## Potential improvements for iteration 2

- Consider adding a dedicated `examples/` reference for complex multi-field creates.
- Consider clarifying whether `--all` is needed for `yt issues` by default; current wording is correct but could be misread as "always required".
- Add a pressure test for `yt create` with `--dry-run` and a period field to confirm unsupported-field guidance is surfaced.
