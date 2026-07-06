#!/usr/bin/env python3
"""Life Heatmap — a passive, local-only visual history of your terminal life.
No accounts. No servers. No telemetry. Everything lives in ~/.lifeheatmap.json
"""
import json, argparse, contextlib, io
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class _Dummy:
        def __getattr__(self, name): return ""
    Fore = Style = _Dummy()
DATA_FILE = Path.home() / ".lifeheatmap.json"
HOOK_FILE = Path.home() / ".lifeheatmap_hook"
LEVELS = " ░▒▓█"
COLOR_ENABLED = HAS_COLOR
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
def load_sessions():
    if not DATA_FILE.exists():
        return []
    try:
        return json.loads(DATA_FILE.read_text()).get("sessions", [])
    except (json.JSONDecodeError, OSError):
        return []
def log_entry(command, directory):
    sessions = load_sessions()
    sessions.append({
        "time": datetime.now().isoformat(timespec="seconds"),
        "directory": directory,
        "command": command,
    })
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"sessions": sessions}, indent=2))
    tmp.replace(DATA_FILE)
def parse_sessions(raw):
    parsed = []
    for s in raw:
        try:
            t = datetime.fromisoformat(s["time"])
        except (ValueError, KeyError, TypeError):
            continue
        parsed.append((t, s.get("directory", "") or "", s.get("command", "") or ""))
    return parsed
def counts_by(parsed, keyfn):
    c = Counter()
    for row in parsed:
        c[keyfn(row)] += 1
    return c
def day_counts(parsed): return counts_by(parsed, lambda r: r[0].date())
def hour_counts(parsed): return counts_by(parsed, lambda r: r[0].hour)
def weekday_counts(parsed): return counts_by(parsed, lambda r: r[0].weekday())
def command_counts(parsed):
    c = Counter()
    for _, _, cmd in parsed:
        if cmd.strip():
            c[cmd.split()[0]] += 1
    return c
def folder_counts(parsed):
    c = Counter()
    for _, d, _ in parsed:
        if d:
            c[Path(d).name or d] += 1
    return c
def sessions_from_times(times, gap_minutes=30):
    """Group a sorted list of timestamps into work sessions."""
    if not times:
        return []
    times = sorted(times)
    out, start, prev = [], times[0], times[0]
    for t in times[1:]:
        if (t - prev).total_seconds() > gap_minutes * 60:
            out.append((start, prev))
            start = t
        prev = t
    out.append((start, prev))
    return out
def compute_streaks(day_c):
    if not day_c:
        return 0, 0
    days = sorted(day_c.keys())
    longest = run = 1
    for i in range(1, len(days)):
        run = run + 1 if (days[i] - days[i - 1]).days == 1 else 1
        longest = max(longest, run)
    today = datetime.now().date()
    d = today if today in day_c else today - timedelta(days=1)
    current = 0
    while d in day_c:
        current += 1
        d -= timedelta(days=1)
    return current, longest
def longest_break(day_c):
    if len(day_c) < 2:
        return 0
    days = sorted(day_c.keys())
    return max((days[i] - days[i - 1]).days for i in range(1, len(days)))
def hr(width=41): print("=" * width)
def title(text, width=41): print(text.center(width))
def stat_line(label, value, width=41):
    value = str(value)
    print(label + " " * max(1, width - len(label) - len(value)) + value)
def format_hour(h):
    return f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}"
def level_char(count, max_count):
    if max_count == 0 or count == 0:
        return LEVELS[0]
    ratio = count / max_count
    idx = min(int(ratio * (len(LEVELS) - 1)) + 1, len(LEVELS) - 1)
    return LEVELS[idx]
def colorize(ch):
    if not COLOR_ENABLED or ch == LEVELS[0]:
        return ch
    shades = {
        LEVELS[1]: Fore.GREEN + Style.DIM,
        LEVELS[2]: Fore.GREEN,
        LEVELS[3]: Fore.GREEN + Style.BRIGHT,
        LEVELS[4]: Fore.LIGHTGREEN_EX,
    }
    return shades.get(ch, "") + ch + Style.RESET_ALL
def bar(count, max_count, width=30):
    n = 0 if max_count == 0 else round((count / max_count) * width)
    filled = "█" * n
    return colorize(filled) if COLOR_ENABLED and n else filled
def print_contribution_graph(day_c, weeks=10):
    print("Mon Tue Wed Thu Fri Sat Sun")
    today = datetime.now().date()
    start = today - timedelta(days=weeks * 7 - 1)
    start -= timedelta(days=start.weekday())
    max_c = max(day_c.values()) if day_c else 0
    d = start
    while d <= today:
        row = []
        for _ in range(7):
            row.append(colorize(level_char(day_c.get(d, 0), max_c)))
            d += timedelta(days=1)
        print("   ".join(row))
def print_hour_heatmap(hour_c):
    title("HOURLY ACTIVITY")
    max_c = max(hour_c.values()) if hour_c else 0
    for h in range(24):
        print(f"{h:02d}  {bar(hour_c.get(h, 0), max_c)}")
def print_weekday_activity(weekday_c):
    title("WEEKDAY ACTIVITY")
    max_c = max(weekday_c.values()) if weekday_c else 0
    for i, name in enumerate(WEEKDAY_NAMES):
        print(f"{name:<10}{bar(weekday_c.get(i, 0), max_c)}")
def print_ranking(counter, label, total=None, top=20):
    total = total or sum(counter.values()) or 1
    for name, count in counter.most_common(top):
        pct = f"{count / total * 100:.0f}%"
        print(f"{name:<24}{count:>8,}   {pct}")
def cmd_dashboard(parsed, args=None):
    day_c, hour_c, cmd_c, fold_c = day_counts(parsed), hour_counts(parsed), command_counts(parsed), folder_counts(parsed)
    current, _ = compute_streaks(day_c)
    today_count = day_c.get(datetime.now().date(), 0)
    top_hour = hour_c.most_common(1)
    top_cmd = cmd_c.most_common(1)
    top_folder = fold_c.most_common(1)
    hr()
    title("LIFE HEATMAP")
    hr()
    stat_line("Current Streak", f"{current} days")
    stat_line("Commands Logged", f"{len(parsed):,}")
    stat_line("Projects", len(fold_c))
    stat_line("Today's Commands", today_count)
    stat_line("Most Active Hour", format_hour(top_hour[0][0]) if top_hour else "-")
    stat_line("Favorite Command", top_cmd[0][0] if top_cmd else "-")
    stat_line("Favorite Folder", top_folder[0][0] if top_folder else "-")
    hr()
    print()
    print_contribution_graph(day_c)
    print()
def cmd_today(parsed, args=None):
    today = datetime.now().date()
    todays = [(t, d, c) for t, d, c in parsed if t.date() == today]
    title("TODAY'S SUMMARY")
    if not todays:
        print("No activity recorded yet today.")
        return
    times = [t for t, _, _ in todays]
    cmd_c = command_counts(todays)
    fold_c = folder_counts(todays)
    gaps = [(times[i] - times[i - 1]) for i in range(1, len(times))]
    longest_gap = max(gaps) if gaps else timedelta(0)
    stat_line("Commands", len(todays))
    stat_line("Projects", len(fold_c))
    stat_line("First command", times[0].strftime("%-I:%M %p"))
    stat_line("Last command", times[-1].strftime("%-I:%M %p"))
    h, m = divmod(int(longest_gap.total_seconds()) // 60, 60)
    stat_line("Longest inactive gap", f"{h}h {m}m" if h else f"{m}m")
    top = cmd_c.most_common(1)
    stat_line("Favorite command", top[0][0] if top else "-")
def _range_report(parsed, since, heading):
    ranged = [(t, d, c) for t, d, c in parsed if t.date() >= since]
    title(heading)
    if not ranged:
        print("No activity recorded in this period.")
        return
    day_c = day_counts(ranged)
    by_day = sorted(day_c.items(), key=lambda kv: kv[1])
    avg = sum(day_c.values()) / len(day_c)
    stat_line("Average commands/day", f"{avg:.0f}")
    stat_line("Most productive day", str(by_day[-1][0]))
    stat_line("Least productive day", str(by_day[0][0]))
    print()
    print("Top folders:")
    print_ranking(folder_counts(ranged), "folder", top=5)
    print()
    print("Top commands:")
    print_ranking(command_counts(ranged), "command", top=5)
    print()
    sessions = sessions_from_times([t for t, _, _ in ranged])
    longest = max(sessions, key=lambda se: se[1] - se[0]) if sessions else None
    if longest:
        mins = int((longest[1] - longest[0]).total_seconds() // 60) or 1
        stat_line("Largest coding session", f"{mins} min")
def cmd_week(parsed, args=None):
    _range_report(parsed, datetime.now().date() - timedelta(days=7), "WEEKLY REPORT")
def cmd_month(parsed, args=None):
    _range_report(parsed, datetime.now().date() - timedelta(days=30), "MONTHLY REPORT")
    day_c = day_counts([(t, d, c) for t, d, c in parsed if t.date() >= datetime.now().date() - timedelta(days=30)])
    print()
    print_contribution_graph(day_c, weeks=5)
def cmd_year(parsed, args=None):
    title("YEAR IN REVIEW")
    day_c = day_counts(parsed)
    max_c = max(day_c.values()) if day_c else 0
    year = datetime.now().year
    for m in range(1, 13):
        month_name = datetime(year, m, 1).strftime("%B")
        days_in_month = (datetime(year, m % 12 + 1, 1) - timedelta(days=1)).day if m < 12 else 31
        row = []
        for day in range(1, days_in_month + 1):
            try:
                d = datetime(year, m, day).date()
            except ValueError:
                break
            row.append(colorize(level_char(day_c.get(d, 0), max_c)))
        print(f"{month_name:<10}{''.join(row)}")
def cmd_stats(parsed, args=None):
    day_c, hour_c, weekday_c = day_counts(parsed), hour_counts(parsed), weekday_counts(parsed)
    current, longest_streak = compute_streaks(day_c)
    title("LIFETIME STATS")
    stat_line("Total commands", f"{len(parsed):,}")
    stat_line("Days with activity", len(day_c))
    stat_line("Current streak", f"{current} days")
    stat_line("Longest streak", f"{longest_streak} days")
    if day_c:
        stat_line("Average commands/day", f"{sum(day_c.values()) / len(day_c):.0f}")
        weekend = sum(v for k, v in weekday_c.items() if k >= 5)
        stat_line("Weekend commands", f"{weekend:,}")
    stat_line("Longest inactive period", f"{longest_break(day_c)} days")
    if hour_c:
        stat_line("Most productive hour", format_hour(hour_c.most_common(1)[0][0]))
    print()
    print_hour_heatmap(hour_c)
    print()
    print_weekday_activity(weekday_c)
def cmd_commands(parsed, args=None):
    title("COMMAND RANKING"); print_ranking(command_counts(parsed), "command", total=len(parsed))
def cmd_folders(parsed, args=None):
    title("FOLDER RANKING"); print_ranking(folder_counts(parsed), "folder", total=len(parsed))
def cmd_streak(parsed, args=None):
    day_c = day_counts(parsed)
    current, longest = compute_streaks(day_c)
    title("STREAKS")
    stat_line("Current streak", f"{current} days")
    stat_line("Longest streak", f"{longest} days")
    stat_line("Longest inactive period", f"{longest_break(day_c)} days")
    if day_c:
        by_count = Counter()
        for d, cnt in day_c.items():
            by_count[d.strftime("%B %Y")] += cnt
        best_month = by_count.most_common(1)[0]
        stat_line("Most productive month", f"{best_month[0]} ({best_month[1]:,} commands)")
def cmd_search(parsed, args):
    term = args.term
    matches = [(t, d, c) for t, d, c in parsed if term in c]
    title(f"SEARCH: {term}")
    if not matches:
        print("No matches found.")
        return
    stat_line("Command count", len(matches))
    days = sorted({t.date() for t, _, _ in matches})
    stat_line("First used", str(days[0]))
    stat_line("Last used", str(days[-1]))
    top_folder = folder_counts(matches).most_common(1)
    stat_line("Most common folder", top_folder[0][0] if top_folder else "-")
    print()
    print("Timeline:")
    for d in days[-20:]:
        count = sum(1 for t, _, _ in matches if t.date() == d)
        print(f"  {d}  {count}x")
def cmd_folder(parsed, args):
    name = args.name
    matches = [(t, d, c) for t, d, c in parsed if Path(d).name == name or d == name]
    title(f"PROJECT: {name}")
    if not matches:
        print("No activity found for this folder.")
        return
    times = sorted(t for t, _, _ in matches)
    sessions = sessions_from_times(times)
    avg_session = sum((e - s).total_seconds() for s, e in sessions) / len(sessions) / 60
    day_c = day_counts(matches)
    stat_line("Started", str(times[0].date()))
    stat_line("Last active", str(times[-1].date()))
    stat_line("Total commands", f"{len(matches):,}")
    stat_line("Active days", len(day_c))
    stat_line("Average session", f"{avg_session:.0f} min")
    stat_line("Longest break", f"{longest_break(day_c)} days")
    print()
    print("Most common commands:")
    print_ranking(command_counts(matches), "command", top=5)
    print()
    print_hour_heatmap(hour_counts(matches))
def cmd_export(parsed, args=None):
    global COLOR_ENABLED
    buf, prev_color, COLOR_ENABLED = io.StringIO(), COLOR_ENABLED, False
    with contextlib.redirect_stdout(buf):
        cmd_dashboard(parsed)
        print()
        cmd_stats(parsed)
        print()
        cmd_commands(parsed)
        print()
        cmd_folders(parsed)
        print()
        cmd_year(parsed)
    COLOR_ENABLED = prev_color
    Path("life-report.txt").write_text(buf.getvalue())
    print(f"Report written to {Path('life-report.txt').resolve()}")
def cmd_log(parsed, args): log_entry(args.command, args.directory)
HOOK_TEMPLATE = """\
# Life Heatmap shell hook — passively records command, time, and directory.
# Installed by `life install`. Safe to delete this file to opt out.
_lifeheatmap_bin="{bin_path}"

if [ -n "$ZSH_VERSION" ]; then
  _lifeheatmap_precmd() {{
    local last_cmd
    last_cmd=$(fc -ln -1)
    if [ "$last_cmd" != "$_LIFEHEATMAP_LAST" ]; then
      _LIFEHEATMAP_LAST="$last_cmd"
      ("$_lifeheatmap_bin" _log --command "$last_cmd" --directory "$PWD" &) 2>/dev/null
    fi
  }}
  autoload -Uz add-zsh-hook
  add-zsh-hook precmd _lifeheatmap_precmd
elif [ -n "$BASH_VERSION" ]; then
  _lifeheatmap_precmd() {{
    local last_cmd
    last_cmd=$(HISTTIMEFORMAT= history 1 | sed 's/^[ ]*[0-9]*[ ]*//')
    if [ "$last_cmd" != "$_LIFEHEATMAP_LAST" ]; then
      _LIFEHEATMAP_LAST="$last_cmd"
      ("$_lifeheatmap_bin" _log --command "$last_cmd" --directory "$PWD" &) 2>/dev/null
    fi
  }}
  PROMPT_COMMAND="_lifeheatmap_precmd${{PROMPT_COMMAND:+; $PROMPT_COMMAND}}"
fi
"""
def cmd_install(_parsed=None, _args=None):
    bin_path = str(Path(__file__).resolve())
    HOOK_FILE.write_text(HOOK_TEMPLATE.format(bin_path=bin_path))
    print(f"Hook written to {HOOK_FILE}")
    print("Add this line to your ~/.bashrc or ~/.zshrc, then restart your shell:")
    print(f"\n    source {HOOK_FILE}\n")
def build_parser():
    p = argparse.ArgumentParser(prog="life", description="A passive terminal activity heatmap.")
    sub = p.add_subparsers(dest="action")
    for name in ["today", "week", "month", "year", "stats", "commands",
                 "folders", "streak", "export", "install", "help"]:
        sub.add_parser(name)
    s = sub.add_parser("search")
    s.add_argument("term")
    f = sub.add_parser("folder")
    f.add_argument("name")
    lg = sub.add_parser("_log")
    lg.add_argument("--command", dest="command", default="")
    lg.add_argument("--directory", dest="directory", default="")
    return p
DISPATCH = {
    None: cmd_dashboard, "today": cmd_today, "week": cmd_week, "month": cmd_month,
    "year": cmd_year, "stats": cmd_stats, "commands": cmd_commands, "folders": cmd_folders,
    "streak": cmd_streak, "export": cmd_export, "search": cmd_search, "folder": cmd_folder,
    "install": cmd_install, "_log": cmd_log,
}
def main():
    args = build_parser().parse_args()
    action = args.action
    if action in ("help", "--help"):
        return build_parser().print_help()
    parsed = [] if action == "_log" else parse_sessions(load_sessions())
    DISPATCH.get(action, cmd_dashboard)(parsed, args)
if __name__ == "__main__":
    main()