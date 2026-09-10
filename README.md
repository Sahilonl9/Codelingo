# CodeLingo — a prototype

Paste unfamiliar code, get a line-by-line plain-English "translation" (with
a voice that reads it aloud), then flip into a Duolingo-style practice mode
where you're shown the English and have to write the matching code yourself.

Built for the intern scenario: someone who knows Python but has never seen
Django should be able to paste a view function and get sentence-by-sentence
English for what each line does — then drill it until they can write it
themselves.

## Stack (and why)

- **Backend: FastAPI (Python)** — one process, two real endpoints
  (`/api/explain`, `/api/check`), plus it serves the frontend directly so
  there's nothing else to run or configure.
- **Explanation engine: rule-based, not an LLM call** — an ordered list of
  regex patterns (imports, def/class, if/for/return, Django ORM idioms like
  `.filter(Q(...) | Q(...)).distinct()`, dict literals in a `render()` call,
  etc.) with a small bracket-depth stack so it can talk sensibly about
  multi-line statements. This makes the prototype fully offline and free to
  run, at the cost of only covering the patterns it knows. See "extend
  first" below — this is the piece most worth swapping out.
- **Frontend: plain HTML/CSS/JS, no build step** — a page you can open and
  read in five minutes. State lives in a small `state` object and
  `localStorage` (for XP/streak); nothing to compile.
- **Voice: the browser's built-in `SpeechSynthesisUtterance`** — genuinely
  free, offline, and instant. No API key, no audio upload. This is the
  "voice assistant" half of the idea — click "Read explanations aloud" and
  it reads each line in order, highlighting the row it's currently speaking
  (karaoke-style).

## Running it

Requires Python 3.9+.

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Then open **http://localhost:8000** — the backend serves the frontend
directly, so that's the only URL you need. It loads with the Django search
example pre-explained so you see it working immediately.

No `npm install`, no separate frontend server, no API keys required.

## How it works

1. **Explain tab** — paste code, hit "Explain this code." Each line is sent
   through `backend/explainer.py`'s rule engine and rendered as an
   *interlinear* pair: the code line in monospace, with its English
   translation right underneath (the same layout old interlinear
   translation manuscripts use for language learners — code and gloss,
   paired). Click the speaker icon on any line, or "Read explanations
   aloud" to have the whole thing read in sequence.

2. **Practice tab** — click "Practice this snippet" and the same
   line-by-line breakdown becomes a deck of flashcards: you see only the
   English, type the code you think matches, and hit "Check." Checking uses
   `difflib.SequenceMatcher` on whitespace-normalized text (so formatting
   differences don't count against you) — correct answers are worth more
   XP and extend your streak; a close-but-wrong answer still earns a couple
   of points to keep momentum. "Show the answer" is always available if
   you're stuck. XP and streak persist in `localStorage`.

## What I'd extend first

Roughly in priority order:

1. **Swap the rule engine for an LLM call (or hybrid) for real language
   coverage.** Right now `explainer.py` only understands the patterns
   someone hand-wrote — great for the demo, but it'll shrug at anything
   novel (a decorator-heavy Flask route, a Rust `impl` block, gnarly
   Pandas chains). The clean seam for this is `explain_code()` in
   `backend/explainer.py`: keep the regex rules as a fast, free first pass
   for common idioms, and fall back to an LLM call (e.g. the Claude API)
   for anything the rules don't confidently match, with the prompt
   constrained to "one plain-English sentence per line, in this style."
   That keeps the demo cheap and instant for the 80% case while making the
   other 20% actually usable.

2. **Real code parsing instead of line-by-line regex.** The current engine
   works line-by-line with a crude bracket counter, which is why it can be
   thrown off by things like brackets inside string literals, or a single
   logical statement that a formatter has spread across five lines in an
   unexpected way. A language-aware parser (Python's own `ast` module for
   Python; `tree-sitter` for everything else, since it has grammars for
   dozens of languages) would let you explain *statements* instead of
   *lines*, and handle indentation/scoping properly.

3. **Smarter practice checking.** `SequenceMatcher` on normalized text is a
   fine first cut, but it can't tell "renamed a variable" from "wrote the
   wrong method entirely." For Python specifically, comparing `ast.dump()`
   trees (ignoring variable names, or treating them as equivalent via
   alpha-renaming) would grade on structure instead of surface text, so
   `results = Article.objects.filter(...)` and
   `articles = Article.objects.filter(...)` would both register as correct.

4. **Spaced repetition instead of one-and-done decks.** Right now a
   practice set is just "go through this snippet's lines once." The
   Duolingo-shaped version of this tracks which specific idioms (this
   `Q(...) | Q(...)` pattern, this `request.GET.get(...)` pattern) a given
   learner keeps missing, and resurfaces those — pulled from a growing
   library of snippets, not just the one just pasted. That needs a real
   datastore (SQLite is enough to start) instead of `localStorage`.

5. **Accounts + a snippet library per language/framework.** Let a team lead
   curate a set of "codebase basics" snippets (the ORM patterns, the auth
   decorators, the test fixtures your team actually uses) that every new
   hire practices in their first week, with progress tracked server-side
   instead of per-browser.

6. **Voice input, not just voice output.** The "voice assistant" framing
   suggests the loop could go further: use the Web Speech API's
   `SpeechRecognition` (or a server-side STT model) to let someone *speak*
   their answer in plain English during practice ("assign the filter
   results to a variable called results") and have it graded — closer to
   how someone actually thinks before they've learned the syntax.

7. **Multi-language explanations upfront.** Right now the interface text is
   English-only; if this is aimed at interns/juniors broadly, offering the
   translations themselves in the learner's stronger language (while the
   code stays in the target language, obviously) would widen who it's
   useful for.

## File map

```
backend/
  main.py         FastAPI app: /api/explain, /api/check, sample snippets, serves frontend
  explainer.py    the rule engine — this is what to extend/replace first
  requirements.txt
frontend/
  index.html      page shell, Explain + Practice tabs
  style.css       paper/ink/teal/amber "interlinear manuscript" theme
  app.js          fetch calls, rendering, Web Speech playback, practice loop, XP/streak
```
