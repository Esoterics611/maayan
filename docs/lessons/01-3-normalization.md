# Lesson 1.3 — Hebrew normalization (and what you deliberately *don't* do)

> Module 1, Lesson 3 · ~15 min read + a short hands-on.
> The one question this answers: **between fetching raw text from Sefaria and storing it as a
> chunk, what gets cleaned up — and what does maayan refuse to touch, on purpose?**

In Lesson 1.2 you saw `segment_to_chunks` call `normalize_text` before emitting a chunk. The
text that gets embedded and stored is the *normalized* text, never the raw fetch. This lesson
opens that one step. It's short, but it carries a real lesson about restraint: the most
important normalization decision maayan makes is a thing it **declines** to do.

---

## Why raw text needs cleaning

What Sefaria hands you isn't clean text — it's text wrapped in editorial markup. A single
segment might arrive looking like:

```html
  <b>תַּנְיָא</b> בְּסוֹף<sup class="footnote-marker">1</sup><i class="footnote">הערה של העורך</i> פֶּרֶק
```

If you embedded *that*, the vector would be polluted by HTML tags, a footnote number, and an
editor's note that isn't part of the source at all. So normalization does three jobs, in
order (read them in [maayan/corpus/normalize.py](../../maayan/corpus/normalize.py), the
`normalize_text` function at the bottom):

1. **Strip markup** (`strip_markup`) — drop footnote markers *and their bodies* (editorial,
   not source), strip every remaining HTML tag, and unescape entities (`&quot;` → `"`). Empty
   Vilna page-markers fall away with the generic tag strip.
2. **Collapse whitespace** (`normalize_whitespace`) — runs of spaces, tabs, and newlines
   become a single space; trim the ends.
3. **(Optionally) expand abbreviations** — a hook that is **off by default** (the next
   section is all about why).

After this, the example above becomes exactly `תַּנְיָא בְּסוֹף פֶּרֶק` — clean source text,
ready to embed.

---

## What is protected: the nikkud

Look closely at that result: `תַּנְיָא` still has its vowel points. **Keeping nikkud is a
rule**, stated in [CLAUDE.md](../../CLAUDE.md) and enforced here: normalization strips markup
but never strips the vowel/cantillation marks, because in chassidus and Kabbalah the
pointing is *part of the text* — it can carry meaning, not just pronunciation. A normalizer
that "helpfully" stripped nikkud would be quietly corrupting the source.

> ### Under the hood — then why is there a nikkud-stripper in the file?
> You'll spot `fold_surface`, which *does* drop nikkud, geresh/gershayim, and quote marks. It
> exists for **matching**, never for storage. When the system needs to ask "does the term
> *ע״ב* appear in this passage?", it folds both sides to a tolerant surface form so that
> `ע״ב`, `ע"ב`, and `עב` all compare equal — but the **stored** corpus text keeps every mark
> intact. The comment says it outright: it "never touches stored corpus text." Cleaning for
> *comparison* and cleaning for *storage* are two different jobs, and conflating them is how
> you lose data.

---

## The thing maayan refuses to do: expand rashei-teivot

Hebrew is full of **rashei-teivot** — abbreviations like *וכו׳* (etc.), *ית׳* (may He be
blessed), *רמב״ם* (Rambam). A naive system would "help" by expanding them automatically. maayan
**won't** — and the restraint is the point.

Find `expand_rashei_teivot` in `normalize.py`. It is a deliberate no-op:

- **Off by default.** With `enabled=False` (the default) it returns the text untouched.
- **Never a guesser.** Even when enabled, it only applies an *explicit* expansions table you
  provide. There is no built-in dictionary, no heuristic. An empty table → no change.
- **Protects registered terms.** It carries a `protected` set — folded surface forms of, e.g.,
  the lexicon's terms and Holy Names — that it will **never** expand, even if they appear in
  the table.

> ### Under the hood — why such caution about a "convenience"?
> Three reasons, escalating in seriousness. (1) **Ambiguity:** the same letters expand
> different ways in different contexts; an automatic guess will sometimes be wrong, and a
> wrong expansion silently changes what the source *says*. (2) **Trust:** this whole system
> exists so you can rely on its text and citations — a clever-but-wrong expansion is exactly
> the kind of invisible fabrication maayan refuses everywhere else. (3) **Holy Names:**
> some abbreviations stand for Names that must not be altered; the `protected` set makes that
> *structurally* impossible, not merely a guideline. So the feature is built as a single
> documented chokepoint that's **wired but inert** — real expansion can be turned on later,
> config-driven, behind an explicit table, without touching any caller. CLAUDE.md says it
> directly: "do not implement it speculatively." This is what disciplined restraint looks like
> in code.

---

## Hands-on

**1. Watch raw become clean — with nikkud surviving.** From the repo root:

```bash
uv run python - <<'PY'
from maayan.corpus.normalize import strip_markup, normalize_text
raw = '  <b>תַּנְיָא</b>\n\nבְּסוֹף<sup class="footnote-marker">1</sup><i class="footnote">הערה</i> פֶּרֶק  '
print("RAW:       ", repr(raw))
print("STRIPPED:  ", repr(strip_markup(raw)))     # markup + footnote gone
print("NORMALIZED:", repr(normalize_text(raw)))   # + whitespace collapsed
PY
```

Confirm three things in the output: the HTML tags are gone, the footnote *and its body* are
gone (not left as stray text), and the vowel points (e.g. the marks on תַּנְיָא) are still
there. That last one is the rule made visible.

**2. Watch an abbreviation *not* expand — even when you ask.**

```bash
uv run python - <<'PY'
from maayan.corpus.normalize import normalize_text
print(normalize_text("וְכוּ׳ עַד אֵין סוֹף", expand_abbreviations=True))
PY
```

It prints the phrase unchanged. You explicitly asked for expansion and it still didn't guess —
because there's no table, by design. That's the restraint from the section above, in one line.

**3. Read the contract in the tests.** Open
[tests/test_normalize.py](../../tests/test_normalize.py). Every behavior above is pinned by a
test: footnotes dropped with content, entities unescaped, whitespace collapsed, nikkud kept,
and the rashei-teivot hook a no-op even when enabled. Run them:

```bash
uv run pytest tests/test_normalize.py -v
```

The test names *are* the spec. When you wonder "what is normalization promised to do?", this
file answers it — and `make test` keeps those promises honest.

---

## You should now be able to say…

- The three steps of normalization (strip markup → collapse whitespace → optional expand),
  and that the text stored/embedded is always the *normalized* text.
- Why **nikkud is kept**, and why `fold_surface` strips it only for *matching*, never for
  storage.
- Why maayan **refuses to auto-expand rashei-teivot** — ambiguity, trust, and Holy Names —
  and how the hook is built to stay safely inert until explicitly turned on.
- That the test file is the executable spec for all of this.

**That's Module 1.** You now understand the "R" *inputs*: how text becomes a searchable
vector (1.1), what unit gets embedded and why (1.2), and how it's cleaned without being
corrupted (1.3). Those chunks-as-vectors are sitting in a database, waiting.

Next: **Module 2** opens that database — where the vectors live, and how a question pulls
back the relevant few. When you're ready, ask me to **build out Module 2**.
