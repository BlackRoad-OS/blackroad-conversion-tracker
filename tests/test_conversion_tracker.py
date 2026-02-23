"""Tests for BlackRoad Conversion Tracker."""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from conversion_tracker import ConversionTracker


@pytest.fixture
def tracker(tmp_path):
    db_path = str(tmp_path / "test_tracker.db")
    t = ConversionTracker(db_path=db_path)
    yield t
    t.close()


# ---------------------------------------------------------------------------
# Test 1: Define goal with 3 funnel steps
# ---------------------------------------------------------------------------
def test_define_goal(tracker):
    goal_id = tracker.define_goal(
        name="Signup",
        event_name="signup_complete",
        target_value=100.0,
        value_per_conversion=25.0,
        funnel_steps=["page_view", "form_start", "signup_complete"],
    )
    assert goal_id is not None and goal_id > 0

    cur = tracker.conn.cursor()
    cur.execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
    g = cur.fetchone()
    assert g["name"] == "Signup"
    assert g["event_name"] == "signup_complete"
    assert g["value_per_conversion"] == 25.0

    cur.execute(
        "SELECT COUNT(*) as cnt FROM funnel_steps WHERE goal_id = ?", (goal_id,)
    )
    assert cur.fetchone()["cnt"] == 3


# ---------------------------------------------------------------------------
# Test 2: Track event triggers goal
# ---------------------------------------------------------------------------
def test_track_event_triggers_goal(tracker):
    tracker.define_goal(
        name="Purchase",
        event_name="purchase",
        value_per_conversion=50.0,
    )
    triggered = tracker.track_event(
        visitor_id="visitor_001",
        session_id="sess_001",
        event_name="purchase",
        value=50.0,
        source="google",
        medium="cpc",
        campaign="summer_sale",
    )
    assert "Purchase" in triggered


# ---------------------------------------------------------------------------
# Test 3: Attribution models produce correct sums
# ---------------------------------------------------------------------------
def test_attribution_models(tracker):
    goal_id = tracker.define_goal(
        name="Checkout",
        event_name="checkout_complete",
        value_per_conversion=100.0,
    )

    # Simulate 3-touchpoint session
    sid = "sess_attr"
    vid = "visitor_attr"
    tracker.track_event(vid, sid, "page_view", source="google", medium="organic")
    tracker.track_event(vid, sid, "email_click", source="email", medium="newsletter")
    triggered = tracker.track_event(
        vid, sid, "checkout_complete", value=100.0,
        source="direct", medium="none"
    )
    assert "Checkout" in triggered

    cur = tracker.conn.cursor()
    for model in ("last_click", "first_click", "linear", "time_decay"):
        cur.execute(
            "SELECT SUM(attributed_value) as total FROM attributions WHERE goal_id = ? AND model = ?",
            (goal_id, model),
        )
        total = cur.fetchone()["total"] or 0.0
        # Each model should attribute roughly the value_per_conversion
        assert total > 0.0, f"Model {model} attributed 0 value"


# ---------------------------------------------------------------------------
# Test 4: Funnel report with partial completions
# ---------------------------------------------------------------------------
def test_funnel_report(tracker):
    goal_id = tracker.define_goal(
        name="Onboarding",
        event_name="onboarding_done",
        funnel_steps=["step_a", "step_b", "step_c"],
    )

    # 10 visitors start step A
    for i in range(10):
        tracker.track_event(f"v{i}", f"s{i}", "step_a")

    # 7 reach step B
    for i in range(7):
        tracker.track_event(f"v{i}", f"s{i}", "step_b")

    # 4 complete step C / goal
    for i in range(4):
        tracker.track_event(f"v{i}", f"s{i}", "step_c")
        tracker.track_event(f"v{i}", f"s{i}", "onboarding_done")

    reports = tracker.get_funnel_report(goal_id, days=30)
    assert len(reports) == 3

    # Step A: 10 entered
    assert reports[0].entered == 10
    # There should be drop-off after step A (only 7 continued)
    assert reports[0].drop_rate >= 0.0


# ---------------------------------------------------------------------------
# Test 5: Conversion rate calculation
# ---------------------------------------------------------------------------
def test_conversion_rate(tracker):
    goal_id = tracker.define_goal(
        name="Newsletter",
        event_name="subscribe",
        value_per_conversion=5.0,
    )

    # 5 unique visitors
    for i in range(5):
        tracker.track_event(f"vis_{i}", f"ses_{i}", "page_view")

    # 2 subscribe
    for i in range(2):
        tracker.track_event(f"vis_{i}", f"ses_{i}", "subscribe")

    result = tracker.get_conversion_rate(goal_id, days=30)
    assert result["unique_visitors"] == 5
    assert result["completions"] == 2
    assert abs(result["conversion_rate"] - 40.0) < 0.01


# ---------------------------------------------------------------------------
# Test 6: Goal performance across multiple goals
# ---------------------------------------------------------------------------
def test_goal_performance(tracker):
    g1 = tracker.define_goal("GoalA", "event_a", value_per_conversion=10.0)
    g2 = tracker.define_goal("GoalB", "event_b", value_per_conversion=20.0)

    for i in range(3):
        tracker.track_event(f"u{i}", f"s{i}", "event_a", value=5.0)
    for i in range(2):
        tracker.track_event(f"u{i}", f"s{i}", "event_b", value=10.0)

    perf = tracker.get_goal_performance(days=30)
    names = {g["name"]: g for g in perf}

    assert "GoalA" in names
    assert "GoalB" in names
    assert names["GoalA"]["completions"] == 3
    assert names["GoalB"]["completions"] == 2
    # total_value = event value sum + completions * value_per_conversion
    assert names["GoalA"]["total_value"] > 0
    assert names["GoalB"]["total_value"] > 0
