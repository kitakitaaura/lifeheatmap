# Life Heatmap by KitaKita

A passive visual history of your terminal life — like GitHub's
contribution graph, but for your own command line.

Everything is in a single JSON
file on your machine: `~/.lifeheatmap.json`.

---

## What it does

Once installed, Life Heatmap silently records three things every time you
run a command in your terminal:

- the timestamp
- the current directory
- the command itself

You're not meant to notice it running. Weeks or months later, you open the
dashboard and see patterns you'd never notice day-to-day: when you're most
productive, which projects took your time, when you went dark on
something, which weekends you actually spent coding.

---

## Requirements

- Python 3 (3.9+; tested on 3.12)
- Bash or Zsh
- macOS or Linux
- `colorama` (optional — enables the green color gradient; without it,
  everything still works in plain black-and-white characters)

```bash
pip install colorama --break-system-packages   # optional
```

---

## Installation

### 0. Clone the repo or copy the file

Pretty self explanatory, but I would download the `life.py` file in this repo, and open the folder its in in the terminal.

### 1. Put the script somewhere permanent

Pick a folder you don't plan to move or rename later, the install step bakes in the **absolute path** to `life.py`, so moving the file afterward
will break logging (more on this in Troubleshooting).

```bash
mkdir -p ~/bin
mv life.py ~/bin/life.py
```

### 2. Make it executable

This step matters a lot, the shell hook calls the script directly as a program, not through `python3`, so without execute permission it will fail silently.

```bash
chmod +x ~/bin/life.py
```

### 3. Run install

```bash
python3 ~/bin/life.py install
```

This writes a shell hook to `~/.lifeheatmap_hook` and prints a line to add
to your shell config, e.g.:

```
source /Users/you/.lifeheatmap_hook
```

### 4. Add that line to your shell config

- **Zsh** → `~/.zshrc`
- **Bash** → `~/.bashrc`

Not sure which shell you're on?

```bash
echo $SHELL
```

If you use a framework like Oh My Zsh, add the `source` line *after* the
`source $ZSH/oh-my-zsh.sh` line, not before, some themes/plugins reset
hook lists.

### 5. Reload your shell

```bash
source ~/.zshrc     # or source ~/.bashrc
```

### 6. Add an alias so you can just type `life`

Add this to the same `~/.zshrc` / `~/.bashrc`, then reload again:

```bash
alias life="python3 ~/bin/life.py"
```

---

## Verifying it's working

Run any command, then check the data file:

```bash
echo hello
cat ~/.lifeheatmap.json
```

You should see a JSON entry appear for `echo hello`. If the file doesn't
exist or doesn't grow, see Troubleshooting below.

---

## Using it

```bash
life                          # main dashboard
life today                    # today's summary
life week                     # weekly report
life month                    # monthly report
life year                     # full-year calendar view
life stats                    # lifetime stats + hourly/weekday heatmaps
life commands                 # top commands, ranked
life folders                  # top project folders, ranked
life streak                   # current/longest streaks, inactive periods
life search <term>            # every day a command was used, with counts
life folder <name>            # deep dive on one project folder
life export                   # writes life-report.txt in the current dir
life help                     # list all commands
```

(If you skipped the alias in step 6, replace `life` above with
`python3 ~/bin/life.py`.)

Nothing else to do from here — just use your terminal normally. Come back
whenever and run `life` to see how things have built up.

---

## Uninstalling / pausing

To stop logging, remove or comment out the `source ~/.lifeheatmap_hook`
line from your shell config and reload the shell. Your existing
`~/.lifeheatmap.json` data is untouched either way — delete that file
manually if you want to wipe your history.

---

## Troubleshooting

**`~/.lifeheatmap.json` doesn't exist, even after `install`:**

Work through these in order:

1. **Did you reload the shell after installing?**
   ```bash
   functions _lifeheatmap_precmd     # zsh
   type _lifeheatmap_precmd          # bash
   ```
   If this says "not found," the hook isn't loaded, re-check that the
   `source` line is really in your shell config, then reload the shell (or
   open a new terminal tab/window).

2. **Is the script executable?**
   ```bash
   ls -l ~/bin/life.py
   ```
   You need an `x` in the permissions (e.g. `-rwxr-xr-x`). If it just says
   `-rw-r--r--`, run `chmod +x ~/bin/life.py`. The hook invokes the script
   directly as a program (not via `python3`), so without execute
   permission, every log attempt fails — silently, because the hook
   suppresses stderr on purpose so it never clutters your prompt.

3. **Did the script move after you ran `install`?**
   `install` bakes the script's absolute path into the hook at the moment
   you run it. Check what path is actually stored:
   ```bash
   grep _lifeheatmap_bin ~/.lifeheatmap_hook
   ```
   Then confirm that path exists:
   ```bash
   ls -la "$(grep _lifeheatmap_bin ~/.lifeheatmap_hook | cut -d'"' -f2)"
   ```
   If it doesn't, either move `life.py` back to that path, or re-run
   `python3 /wherever/it/now/lives/life.py install` and reload your shell.

4. **Manual smoke test** - this isolates the Python logic from the shell
   hook entirely:
   ```bash
   python3 ~/bin/life.py _log --command "manual test" --directory "$PWD"
   cat ~/.lifeheatmap.json
   ```
   If this creates an entry, the Python side is fine and the issue is
   purely the hook (see 1–3 above). If it doesn't, something more
   fundamental is wrong (Python version, syntax error, corrupted file) —
   check the error output directly rather than through the hook.

**A logged command shows a stray `\n` in it, e.g.**
```json
"command": "life today\\ncat ~/.lifeheatmap.json"
```
This isn't a bug — it happens if you paste multiple lines into the
terminal at once. Zsh/Bash's history sometimes records a pasted block as
one entry joined by `\n`. Typing commands one at a time avoids this.

**Logging seems to only work when called manually, not automatically:**
Check permissions again (step 2 above) — this is the single most common
cause. If permissions are fine and you're using an IDE's integrated
terminal (e.g. VS Code), try a plain system terminal window instead; some
integrated terminals layer their own precmd/prompt hooks that can
interfere with custom ones.

---

## How it works (short version)

- **Capturing:** the hook uses Zsh's `precmd` mechanism or Bash's
  `PROMPT_COMMAND` — both run automatically right before a new prompt is
  drawn — to grab the last command via `fc -ln -1` (zsh) or `history 1`
  (bash), then logs it in a backgrounded, disowned subshell so it never
  blocks or clutters your terminal.
- **Storage:** each entry is appended to `~/.lifeheatmap.json` via an
  atomic write-then-rename, so concurrent shells can't corrupt the file.
- **Reporting:** every `life <command>` reads the whole JSON file, parses
  timestamps, and tallies counts with `collections.Counter` — no database,
  no external services.

---

## Notes on scale

The JSON file is fully read and rewritten on every single log event, which
is simple and safe but means write performance degrades as the file grows
into the hundreds of thousands of entries. Reading/reporting stays fast
regardless. If you log heavily enough for this to matter, a natural next
step would be splitting storage into monthly files instead of one
ever-growing one.