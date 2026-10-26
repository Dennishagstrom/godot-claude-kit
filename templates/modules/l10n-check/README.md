# Module: l10n-check

TL;DR: a test that keeps player text translatable. Controls translate plain
text by themselves (auto-translate), so a literal like `label.text = "Play"`
is fine. What breaks translation is text built at runtime without `tr()`:
`"Score: %d" % n` is never a translation key. The suite finds those.

## What it flags

- In scripts (outside tests/, addons/, tools/): assignments to `text`,
  `tooltip_text`, `placeholder_text`, `title`, `dialog_text`, ... and calls like
  `set_text()`, `add_item()`, `add_tab()` whose string literal is formatted
  (`%`, `.format()`), concatenated (`+`) or appended (`+=`) without `tr()`.
- In scenes: nodes with auto-translate disabled that still show text.
- At runtime: tr() and Control auto-translate must actually translate with a
  test locale, and unknown keys fall back to the source text.

Fix: `label.text = tr("Score: %d") % n` (the key keeps the placeholder).
Exceptions: `tests/l10n/l10n_allowlist.gd` (`STRINGS` for exact literals,
`PATHS` for dev-only folders such as `scripts/dev/`). Say why next to each entry.

The checker tests itself first (known good and bad lines), so a broken
regex fails loudly instead of passing everything.

## Run

`python3 -I tools/test_runner.py l10n` (tagged `smoke`, so `--changed` and
`--quick` always run it; it takes about a second).
