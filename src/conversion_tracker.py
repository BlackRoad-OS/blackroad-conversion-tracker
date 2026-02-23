"""
BlackRoad Conversion Tracker
Multi-touch attribution, funnel analysis, and conversion rate tracking.
"""

import dataclasses
import sqlite3
import datetime
import json
import argparse
import sys
import os
import math
import hashlib
from typing import List, Optional, Dict, Any
from collections import defaultdict

# ---------------------------------------------------------------------------
# ANSI Colors
# ---------------------------------------------------------------------------
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
BLUE = "\033[0;34m"
MAGENTA = "\033[0;35m"
BOLD = "\033[1m"
NC = "\033[0m"

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ConversionEvent:
    id: Optional[int]
    visitor_id: str
    session_id: str
    event_name: str
    event_category: str
    value: float
    currency: str
    timestamp: str
    source: str
    medium: str
    campaign: str
    metadata: str  # JSON string


@dataclasses.dataclass
class Goal:
    id: Optional[int]
    name: str
    event_name: str
    target_value: float
    value_per_conversion: float
    funnel_steps: List[str]
    enabled: bool


@dataclasses.dataclass
class Attribution:
    id: Optional[int]
    conversion_id: int
    goal_id: int
    model: str
    touchpoints_json: str
    attributed_value: float
    created_at: str


@dataclasses.dataclass
class FunnelStep:
    id: Optional[int]
    goal_id: int
    position: int
    event_name: str
    description: str


@dataclasses.dataclass
class FunnelReport:
    goal_id: int
    step_name: str
    entered: int
    completed: int
    drop_rate: float
    avg_time_to_complete: float


# ---------------------------------------------------------------------------
# ConversionTracker
# ---------------------------------------------------------------------------

class ConversionTracker:
    def __init__(self, db_path: str = "~/.blackroad/conversion_tracker.db"):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self):
        """Initialize 5 database tables."""
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                event_name TEXT NOT NULL,
                event_category TEXT DEFAULT '',
                value REAL DEFAULT 0.0,
                currency TEXT DEFAULT 'USD',
                timestamp TEXT NOT NULL,
                source TEXT DEFAULT '',
                medium TEXT DEFAULT '',
                campaign TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                event_name TEXT NOT NULL,
                target_value REAL DEFAULT 0.0,
                value_per_conversion REAL DEFAULT 0.0,
                enabled INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS attributions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversion_id INTEGER NOT NULL,
                goal_id INTEGER NOT NULL,
                model TEXT NOT NULL,
                touchpoints_json TEXT DEFAULT '[]',
                attributed_value REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS funnel_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                event_name TEXT NOT NULL,
                description TEXT DEFAULT '',
                UNIQUE(goal_id, position)
            );

            CREATE TABLE IF NOT EXISTS funnel_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                visitor_id TEXT NOT NULL,
                step_position INTEGER NOT NULL,
                completed_at TEXT NOT NULL
            );
        """)
        self.conn.commit()

    # ------------------------------------------------------------------
    # Goal Management
    # ------------------------------------------------------------------

    def define_goal(
        self,
        name: str,
        event_name: str,
        target_value: float = 0.0,
        value_per_conversion: float = 0.0,
        funnel_steps: Optional[List[str]] = None,
    ) -> int:
        """Insert goal and its funnel steps. Returns goal id."""
        cur = self.conn.cursor()
        cur.execute(
            """INSERT OR REPLACE INTO goals
               (name, event_name, target_value, value_per_conversion, enabled)
               VALUES (?, ?, ?, ?, 1)""",
            (name, event_name, target_value, value_per_conversion),
        )
        goal_id = cur.lastrowid
        self.conn.commit()

        if funnel_steps:
            cur.execute("DELETE FROM funnel_steps WHERE goal_id = ?", (goal_id,))
            for pos, step_event in enumerate(funnel_steps, start=1):
                cur.execute(
                    """INSERT INTO funnel_steps (goal_id, position, event_name, description)
                       VALUES (?, ?, ?, ?)""",
                    (goal_id, pos, step_event, f"Step {pos}: {step_event}"),
                )
            self.conn.commit()

        return goal_id

    # ------------------------------------------------------------------
    # Event Tracking
    # ------------------------------------------------------------------

    def track_event(
        self,
        visitor_id: str,
        session_id: str,
        event_name: str,
        event_category: str = "",
        value: float = 0.0,
        source: str = "",
        medium: str = "",
        campaign: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Insert event, check goal completions, trigger attribution. Returns triggered goal names."""
        timestamp = datetime.datetime.utcnow().isoformat()
        meta_str = json.dumps(metadata or {})
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO events
               (visitor_id, session_id, event_name, event_category, value, currency,
                timestamp, source, medium, campaign, metadata)
               VALUES (?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?, ?)""",
            (visitor_id, session_id, event_name, event_category, value,
             timestamp, source, medium, campaign, meta_str),
        )
        event_id = cur.lastrowid
        self.conn.commit()

        # Check funnel step completions
        cur.execute(
            "SELECT goal_id, position FROM funnel_steps WHERE event_name = ?",
            (event_name,),
        )
        for row in cur.fetchall():
            cur.execute(
                """INSERT OR IGNORE INTO funnel_completions
                   (goal_id, session_id, visitor_id, step_position, completed_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (row["goal_id"], session_id, visitor_id, row["position"], timestamp),
            )
        self.conn.commit()

        # Check which goals are triggered by this event
        cur.execute(
            "SELECT id, name, value_per_conversion FROM goals WHERE event_name = ? AND enabled = 1",
            (event_name,),
        )
        goals = cur.fetchall()
        triggered = []
        for g in goals:
            self.attribute_conversion(event_id, g["id"])
            triggered.append(g["name"])

        return triggered

    # ------------------------------------------------------------------
    # Attribution
    # ------------------------------------------------------------------

    def attribute_conversion(self, conversion_event_id: int, goal_id: int):
        """Compute 4 attribution models and insert records."""
        cur = self.conn.cursor()

        # Fetch the conversion event to get session & goal value
        cur.execute("SELECT * FROM events WHERE id = ?", (conversion_event_id,))
        conv_event = cur.fetchone()
        if not conv_event:
            return

        cur.execute("SELECT value_per_conversion FROM goals WHERE id = ?", (goal_id,))
        goal_row = cur.fetchone()
        goal_value = goal_row["value_per_conversion"] if goal_row else 0.0

        # Fetch all touchpoints in the session prior to or at conversion
        cur.execute(
            """SELECT id, source, medium, campaign, timestamp FROM events
               WHERE session_id = ? AND timestamp <= ?
               ORDER BY timestamp ASC""",
            (conv_event["session_id"], conv_event["timestamp"]),
        )
        touchpoints = [dict(r) for r in cur.fetchall()]
        if not touchpoints:
            touchpoints = [dict(conv_event)]

        now = datetime.datetime.utcnow()
        created_at = now.isoformat()
        models: Dict[str, List[Dict]] = {}

        # ---- Last Click ----
        last = touchpoints[-1]
        models["last_click"] = [
            {**tp, "weight": 1.0 if tp["id"] == last["id"] else 0.0}
            for tp in touchpoints
        ]

        # ---- First Click ----
        first = touchpoints[0]
        models["first_click"] = [
            {**tp, "weight": 1.0 if tp["id"] == first["id"] else 0.0}
            for tp in touchpoints
        ]

        # ---- Linear ----
        n = len(touchpoints)
        models["linear"] = [{**tp, "weight": 1.0 / n} for tp in touchpoints]

        # ---- Time Decay (half-life = 7 days) ----
        half_life_days = 7.0
        conv_time = datetime.datetime.fromisoformat(conv_event["timestamp"])
        raw_weights = []
        for tp in touchpoints:
            try:
                tp_time = datetime.datetime.fromisoformat(tp["timestamp"])
            except Exception:
                tp_time = conv_time
            days_ago = max((conv_time - tp_time).total_seconds() / 86400.0, 0.0)
            w = math.exp(-math.log(2) * days_ago / half_life_days)
            raw_weights.append(w)
        total_w = sum(raw_weights) or 1.0
        models["time_decay"] = [
            {**tp, "weight": raw_weights[i] / total_w}
            for i, tp in enumerate(touchpoints)
        ]

        # Insert attribution records
        for model_name, tps in models.items():
            total_attributed = sum(tp["weight"] for tp in tps) * goal_value
            cur.execute(
                """INSERT INTO attributions
                   (conversion_id, goal_id, model, touchpoints_json, attributed_value, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    conversion_event_id,
                    goal_id,
                    model_name,
                    json.dumps(tps),
                    total_attributed,
                    created_at,
                ),
            )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Funnel Report
    # ------------------------------------------------------------------

    def get_funnel_report(self, goal_id: int, days: int = 30) -> List[FunnelReport]:
        """Return funnel report for each step."""
        cur = self.conn.cursor()
        since = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()

        cur.execute(
            "SELECT position, event_name, description FROM funnel_steps WHERE goal_id = ? ORDER BY position",
            (goal_id,),
        )
        steps = cur.fetchall()
        if not steps:
            return []

        reports = []
        prev_sessions: Optional[set] = None

        for step in steps:
            pos = step["position"]
            cur.execute(
                """SELECT COUNT(DISTINCT session_id) as cnt FROM funnel_completions
                   WHERE goal_id = ? AND step_position = ? AND completed_at >= ?""",
                (goal_id, pos, since),
            )
            entered = cur.fetchone()["cnt"]

            cur.execute(
                """SELECT COUNT(DISTINCT session_id) as cnt FROM funnel_completions
                   WHERE goal_id = ? AND step_position > ? AND completed_at >= ?""",
                (goal_id, pos, since),
            )
            completed = cur.fetchone()["cnt"]

            drop_rate = 0.0
            if entered > 0:
                drop_rate = round((1.0 - completed / entered) * 100, 2)

            # Average time between step entries (simplified)
            cur.execute(
                """SELECT completed_at FROM funnel_completions
                   WHERE goal_id = ? AND step_position = ? AND completed_at >= ?
                   ORDER BY completed_at""",
                (goal_id, pos, since),
            )
            times = [r["completed_at"] for r in cur.fetchall()]
            avg_time = 0.0
            if len(times) > 1:
                deltas = []
                for i in range(1, len(times)):
                    try:
                        t1 = datetime.datetime.fromisoformat(times[i - 1])
                        t2 = datetime.datetime.fromisoformat(times[i])
                        deltas.append((t2 - t1).total_seconds())
                    except Exception:
                        pass
                avg_time = sum(deltas) / len(deltas) if deltas else 0.0

            reports.append(
                FunnelReport(
                    goal_id=goal_id,
                    step_name=step["event_name"],
                    entered=entered,
                    completed=completed,
                    drop_rate=drop_rate,
                    avg_time_to_complete=round(avg_time, 2),
                )
            )

        return reports

    # ------------------------------------------------------------------
    # Attribution Report
    # ------------------------------------------------------------------

    def get_attribution_report(
        self, goal_id: int, model: str = "last_click", days: int = 30
    ) -> List[Dict]:
        """Aggregate attributed value by source/medium/campaign."""
        cur = self.conn.cursor()
        since = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()

        cur.execute(
            """SELECT a.touchpoints_json, a.attributed_value
               FROM attributions a
               JOIN events e ON a.conversion_id = e.id
               WHERE a.goal_id = ? AND a.model = ? AND a.created_at >= ?""",
            (goal_id, model, since),
        )
        rows = cur.fetchall()

        agg: Dict[str, Dict] = defaultdict(lambda: {"attributed_value": 0.0, "conversions": 0})
        for row in rows:
            try:
                tps = json.loads(row["touchpoints_json"])
            except Exception:
                tps = []
            for tp in tps:
                key = f"{tp.get('source','(none)')} / {tp.get('medium','(none)')} / {tp.get('campaign','(none)')}"
                weight = tp.get("weight", 0.0)
                agg[key]["attributed_value"] += weight * row["attributed_value"]
                if weight > 0:
                    agg[key]["conversions"] += 1

        result = []
        for channel, stats in sorted(agg.items(), key=lambda x: -x[1]["attributed_value"]):
            result.append(
                {
                    "channel": channel,
                    "attributed_value": round(stats["attributed_value"], 2),
                    "conversions": stats["conversions"],
                }
            )
        return result

    # ------------------------------------------------------------------
    # Conversion Rate
    # ------------------------------------------------------------------

    def get_conversion_rate(self, goal_id: int, days: int = 30) -> Dict:
        """Return unique visitors, goal completions, conversion rate %."""
        cur = self.conn.cursor()
        since = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()

        cur.execute(
            "SELECT event_name FROM goals WHERE id = ?", (goal_id,)
        )
        goal_row = cur.fetchone()
        if not goal_row:
            return {"unique_visitors": 0, "completions": 0, "conversion_rate": 0.0}

        event_name = goal_row["event_name"]

        cur.execute(
            "SELECT COUNT(DISTINCT visitor_id) as cnt FROM events WHERE timestamp >= ?",
            (since,),
        )
        unique_visitors = cur.fetchone()["cnt"]

        cur.execute(
            """SELECT COUNT(DISTINCT visitor_id) as cnt FROM events
               WHERE event_name = ? AND timestamp >= ?""",
            (event_name, since),
        )
        completions = cur.fetchone()["cnt"]

        rate = round((completions / unique_visitors * 100), 4) if unique_visitors > 0 else 0.0

        return {
            "unique_visitors": unique_visitors,
            "completions": completions,
            "conversion_rate": rate,
        }

    # ------------------------------------------------------------------
    # Goal Performance
    # ------------------------------------------------------------------

    def get_goal_performance(self, days: int = 30) -> List[Dict]:
        """Return all goals with completions, total value, avg value, conversion rate."""
        cur = self.conn.cursor()
        since = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()

        cur.execute("SELECT id, name, event_name, value_per_conversion FROM goals WHERE enabled = 1")
        goals = cur.fetchall()

        cur.execute(
            "SELECT COUNT(DISTINCT visitor_id) as cnt FROM events WHERE timestamp >= ?",
            (since,),
        )
        total_visitors = cur.fetchone()["cnt"] or 1

        results = []
        for g in goals:
            cur.execute(
                """SELECT COUNT(DISTINCT visitor_id) as completions,
                          SUM(value) as total_value
                   FROM events
                   WHERE event_name = ? AND timestamp >= ?""",
                (g["event_name"], since),
            )
            row = cur.fetchone()
            completions = row["completions"] or 0
            total_value = (row["total_value"] or 0.0) + completions * g["value_per_conversion"]
            avg_value = round(total_value / completions, 2) if completions > 0 else 0.0
            conversion_rate = round(completions / total_visitors * 100, 4)

            results.append(
                {
                    "goal_id": g["id"],
                    "name": g["name"],
                    "completions": completions,
                    "total_value": round(total_value, 2),
                    "avg_value": avg_value,
                    "conversion_rate": conversion_rate,
                }
            )
        return results

    # ------------------------------------------------------------------
    # Cohort Analysis
    # ------------------------------------------------------------------

    def compute_cohort_analysis(self, goal_id: int, weeks: int = 8) -> List[Dict]:
        """Weekly cohorts: visitors who started in week N, what % converted within 1/2/4 weeks."""
        cur = self.conn.cursor()
        now = datetime.datetime.utcnow()
        cur.execute("SELECT event_name FROM goals WHERE id = ?", (goal_id,))
        goal_row = cur.fetchone()
        if not goal_row:
            return []
        goal_event = goal_row["event_name"]

        cohorts = []
        for w in range(weeks, 0, -1):
            week_start = now - datetime.timedelta(weeks=w)
            week_end = now - datetime.timedelta(weeks=w - 1)

            cur.execute(
                """SELECT DISTINCT visitor_id FROM events
                   WHERE timestamp >= ? AND timestamp < ?""",
                (week_start.isoformat(), week_end.isoformat()),
            )
            cohort_visitors = {r["visitor_id"] for r in cur.fetchall()}
            if not cohort_visitors:
                cohorts.append({
                    "cohort_week": week_start.strftime("%Y-W%V"),
                    "cohort_size": 0,
                    "converted_1w": 0, "rate_1w": 0.0,
                    "converted_2w": 0, "rate_2w": 0.0,
                    "converted_4w": 0, "rate_4w": 0.0,
                })
                continue

            def conv_count(within_weeks: int) -> int:
                deadline = (week_start + datetime.timedelta(weeks=within_weeks)).isoformat()
                placeholders = ",".join("?" * len(cohort_visitors))
                cur.execute(
                    f"""SELECT COUNT(DISTINCT visitor_id) as cnt FROM events
                        WHERE event_name = ? AND visitor_id IN ({placeholders})
                        AND timestamp >= ? AND timestamp < ?""",
                    [goal_event] + list(cohort_visitors) + [week_start.isoformat(), deadline],
                )
                return cur.fetchone()["cnt"]

            size = len(cohort_visitors)
            c1 = conv_count(1)
            c2 = conv_count(2)
            c4 = conv_count(4)

            cohorts.append({
                "cohort_week": week_start.strftime("%Y-W%V"),
                "cohort_size": size,
                "converted_1w": c1, "rate_1w": round(c1 / size * 100, 2),
                "converted_2w": c2, "rate_2w": round(c2 / size * 100, 2),
                "converted_4w": c4, "rate_4w": round(c4 / size * 100, 2),
            })

        return cohorts

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_report(self, goal_id: int, fmt: str = "json") -> str:
        """Full export as JSON or CSV."""
        funnel = [dataclasses.asdict(r) for r in self.get_funnel_report(goal_id)]
        attribution = {
            model: self.get_attribution_report(goal_id, model)
            for model in ("last_click", "first_click", "linear", "time_decay")
        }
        rate = self.get_conversion_rate(goal_id)
        cohort = self.compute_cohort_analysis(goal_id)

        data = {
            "goal_id": goal_id,
            "generated_at": datetime.datetime.utcnow().isoformat(),
            "conversion_rate": rate,
            "funnel": funnel,
            "attribution": attribution,
            "cohort_analysis": cohort,
        }

        if fmt == "json":
            return json.dumps(data, indent=2)

        # CSV fallback — flatten funnel report
        lines = ["step_name,entered,completed,drop_rate,avg_time_to_complete"]
        for step in funnel:
            lines.append(
                f"{step['step_name']},{step['entered']},{step['completed']},"
                f"{step['drop_rate']},{step['avg_time_to_complete']}"
            )
        return "\n".join(lines)

    def close(self):
        self.conn.close()


# ---------------------------------------------------------------------------
# ASCII Funnel Visualization
# ---------------------------------------------------------------------------

def print_funnel(reports: List[FunnelReport], goal_name: str = ""):
    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════╗{NC}")
    print(f"{BOLD}{CYAN}║  Funnel Report: {goal_name:<21}║{NC}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════╝{NC}")
    if not reports:
        print(f"  {YELLOW}No funnel steps found.{NC}\n")
        return

    max_entered = max(r.entered for r in reports) or 1
    for i, step in enumerate(reports):
        bar_len = int((step.entered / max_entered) * 30)
        bar = "█" * bar_len
        color = GREEN if step.drop_rate < 30 else (YELLOW if step.drop_rate < 60 else RED)
        print(f"  {BOLD}Step {i+1}: {step.step_name}{NC}")
        print(f"  {color}{bar}{NC} {step.entered} visitors")
        if step.drop_rate > 0:
            print(f"  {RED}↓ Drop-off: {step.drop_rate:.1f}%{NC}  "
                  f"Completed: {step.completed}  "
                  f"Avg time: {step.avg_time_to_complete:.1f}s")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def get_tracker(args) -> ConversionTracker:
    db = getattr(args, "db", "~/.blackroad/conversion_tracker.db")
    return ConversionTracker(db_path=db)


def cmd_goal(args):
    tracker = get_tracker(args)
    steps = args.funnel_steps.split(",") if args.funnel_steps else []
    goal_id = tracker.define_goal(
        name=args.name,
        event_name=args.event_name,
        target_value=args.target_value,
        value_per_conversion=args.value_per_conversion,
        funnel_steps=steps,
    )
    print(f"{GREEN}✓ Goal '{args.name}' created (id={goal_id}){NC}")
    tracker.close()


def cmd_track(args):
    tracker = get_tracker(args)
    meta = json.loads(args.metadata) if args.metadata else {}
    triggered = tracker.track_event(
        visitor_id=args.visitor_id,
        session_id=args.session_id,
        event_name=args.event_name,
        event_category=args.event_category,
        value=args.value,
        source=args.source,
        medium=args.medium,
        campaign=args.campaign,
        metadata=meta,
    )
    if triggered:
        print(f"{GREEN}✓ Event tracked. Goals triggered: {', '.join(triggered)}{NC}")
    else:
        print(f"{CYAN}✓ Event tracked (no goals triggered){NC}")
    tracker.close()


def cmd_funnel(args):
    tracker = get_tracker(args)
    reports = tracker.get_funnel_report(goal_id=args.goal_id, days=args.days)
    cur = tracker.conn.cursor()
    cur.execute("SELECT name FROM goals WHERE id = ?", (args.goal_id,))
    row = cur.fetchone()
    goal_name = row["name"] if row else str(args.goal_id)
    print_funnel(reports, goal_name)
    tracker.close()


def cmd_attribute(args):
    tracker = get_tracker(args)
    report = tracker.get_attribution_report(
        goal_id=args.goal_id, model=args.model, days=args.days
    )
    print(f"\n{BOLD}{CYAN}Attribution Report — {args.model} (last {args.days}d){NC}")
    print(f"{'Channel':<50} {'Value':>12} {'Conversions':>12}")
    print("-" * 76)
    for row in report:
        print(f"{row['channel']:<50} {row['attributed_value']:>12.2f} {row['conversions']:>12}")
    tracker.close()


def cmd_report(args):
    tracker = get_tracker(args)
    perf = tracker.get_goal_performance(days=args.days)
    print(f"\n{BOLD}{CYAN}Goal Performance Report (last {args.days}d){NC}")
    print(f"{'Goal':<30} {'Completions':>12} {'Total Value':>12} {'Avg Value':>10} {'Rate %':>8}")
    print("-" * 76)
    for g in perf:
        print(
            f"{g['name']:<30} {g['completions']:>12} {g['total_value']:>12.2f}"
            f" {g['avg_value']:>10.2f} {g['conversion_rate']:>8.4f}"
        )
    tracker.close()


def cmd_cohort(args):
    tracker = get_tracker(args)
    cohorts = tracker.compute_cohort_analysis(goal_id=args.goal_id, weeks=args.weeks)
    print(f"\n{BOLD}{CYAN}Cohort Analysis — Goal {args.goal_id}{NC}")
    print(f"{'Week':<12} {'Size':>6} {'1w%':>8} {'2w%':>8} {'4w%':>8}")
    print("-" * 46)
    for c in cohorts:
        print(
            f"{c['cohort_week']:<12} {c['cohort_size']:>6}"
            f" {c['rate_1w']:>8.2f} {c['rate_2w']:>8.2f} {c['rate_4w']:>8.2f}"
        )
    tracker.close()


def cmd_export(args):
    tracker = get_tracker(args)
    output = tracker.export_report(goal_id=args.goal_id, fmt=args.format)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"{GREEN}✓ Report exported to {args.output}{NC}")
    else:
        print(output)
    tracker.close()


def cmd_goals(args):
    tracker = get_tracker(args)
    cur = tracker.conn.cursor()
    cur.execute("SELECT id, name, event_name, value_per_conversion, enabled FROM goals")
    goals = cur.fetchall()
    print(f"\n{BOLD}{CYAN}Defined Goals{NC}")
    print(f"{'ID':>4} {'Name':<25} {'Event':<30} {'VpC':>8} {'Enabled':>8}")
    print("-" * 80)
    for g in goals:
        status = f"{GREEN}Yes{NC}" if g["enabled"] else f"{RED}No{NC}"
        print(f"{g['id']:>4} {g['name']:<25} {g['event_name']:<30} {g['value_per_conversion']:>8.2f} {status:>8}")
    tracker.close()


def main():
    parser = argparse.ArgumentParser(
        description="BlackRoad Conversion Tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", default="~/.blackroad/conversion_tracker.db", help="Database path")
    sub = parser.add_subparsers(dest="command")

    # goal
    p_goal = sub.add_parser("goal", help="Define a conversion goal")
    p_goal.add_argument("name")
    p_goal.add_argument("event_name")
    p_goal.add_argument("--target-value", type=float, default=0.0)
    p_goal.add_argument("--value-per-conversion", type=float, default=0.0)
    p_goal.add_argument("--funnel-steps", default="", help="Comma-separated event names")
    p_goal.set_defaults(func=cmd_goal)

    # track
    p_track = sub.add_parser("track", help="Track a conversion event")
    p_track.add_argument("visitor_id")
    p_track.add_argument("session_id")
    p_track.add_argument("event_name")
    p_track.add_argument("--event-category", default="")
    p_track.add_argument("--value", type=float, default=0.0)
    p_track.add_argument("--source", default="")
    p_track.add_argument("--medium", default="")
    p_track.add_argument("--campaign", default="")
    p_track.add_argument("--metadata", default="{}")
    p_track.set_defaults(func=cmd_track)

    # funnel
    p_funnel = sub.add_parser("funnel", help="Show funnel report")
    p_funnel.add_argument("goal_id", type=int)
    p_funnel.add_argument("--days", type=int, default=30)
    p_funnel.set_defaults(func=cmd_funnel)

    # attribute
    p_attr = sub.add_parser("attribute", help="Show attribution report")
    p_attr.add_argument("goal_id", type=int)
    p_attr.add_argument("--model", default="last_click",
                        choices=["last_click", "first_click", "linear", "time_decay"])
    p_attr.add_argument("--days", type=int, default=30)
    p_attr.set_defaults(func=cmd_attribute)

    # report
    p_report = sub.add_parser("report", help="Show goal performance report")
    p_report.add_argument("--days", type=int, default=30)
    p_report.set_defaults(func=cmd_report)

    # cohort
    p_cohort = sub.add_parser("cohort", help="Run cohort analysis")
    p_cohort.add_argument("goal_id", type=int)
    p_cohort.add_argument("--weeks", type=int, default=8)
    p_cohort.set_defaults(func=cmd_cohort)

    # export
    p_export = sub.add_parser("export", help="Export full report")
    p_export.add_argument("goal_id", type=int)
    p_export.add_argument("--format", default="json", choices=["json", "csv"])
    p_export.add_argument("--output", default="")
    p_export.set_defaults(func=cmd_export)

    # goals
    p_goals = sub.add_parser("goals", help="List all defined goals")
    p_goals.set_defaults(func=cmd_goals)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
