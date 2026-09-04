"""One read-only pulse of a live campaign.

This module never writes to Meta. Not "does not currently write": it only ever
calls `get`, and there is a test that asserts that. When money is going out the
door every hour, the thing that watches the spend should not also be able to
change it.

Three jobs per run:

  GUARD   Did anyone edit the live ad since the last check? Edits during the
          learning phase reset it, which is expensive at a small budget.
  SCORE   What is the cost per lead, and how does it compare to the benchmark
          band in your config?
  HEALTH  Are the statuses clean, is the account in good standing, and how many
          days are left on the token?

Metrics we could not find trustworthy benchmarks for are logged but never
judged. Inventing a threshold is worse than admitting there isn't one; see
context/ad-management-principles.md.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ALERT, WARN, INFO = "ALERT", "WARN", "INFO"
SEVERITY_ORDER = {INFO: 0, WARN: 1, ALERT: 2}
EXIT_CODES = {INFO: 0, WARN: 1, ALERT: 2}

# frequency and cpm are fetched so they can be logged. Nothing judges them:
# no threshold for either survived verification. See the unanchored zones in
# context/ad-management-principles.md.
INSIGHT_FIELDS = ("spend,impressions,clicks,ctr,cpc,cpm,frequency,actions,"
                  "date_start,date_stop")


def _leads(row: dict) -> int:
    """Pull the lead count out of the actions array."""
    for action in row.get("actions") or []:
        if action.get("action_type") in ("leadgen.other", "lead", "onsite_conversion.lead_grouped"):
            return int(float(action.get("value", 0)))
    return 0


def _float(row: dict, key: str) -> float:
    try:
        return float(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def gather(api, config: dict) -> dict:
    """Every read this tool makes, in one place. Nothing here writes."""
    ids = config["ids"]
    snapshot = {
        "adset": api.get(
            ids["ad_set_id"],
            fields="name,effective_status,configured_status,daily_budget,updated_time,"
                   "issues_info,learning_stage_info",
        ),
        "ad": api.get(
            ids["ad_id"],
            fields="name,effective_status,updated_time,issues_info,creative{id}",
        ),
        "campaign": api.get(ids["campaign_id"], fields="effective_status,updated_time"),
        "account": api.get(config["account_id"], fields="account_status,amount_spent,currency"),
    }
    # A failed expiry check must not take the whole report down with it. Losing
    # the token warning on a day there is a real ALERT would be the worst
    # possible trade.
    try:
        snapshot["token"] = api.debug_self()
    except Exception:
        # Deliberately broad: whatever went wrong, losing the expiry warning is
        # better than losing the whole report on a day there is a real alert.
        snapshot["token"] = {}
        snapshot["token_check_failed"] = True
    for preset in ("today", "yesterday", "maximum"):
        snapshot[preset] = (
            api.get(f"{ids['ad_set_id']}/insights", date_preset=preset, fields=INSIGHT_FIELDS)
            .get("data") or [{}]
        )[0]
    return snapshot


def evaluate(snapshot: dict, config: dict, previous: dict | None) -> list[tuple[str, str]]:
    """Turn a snapshot into findings. Pure function, so it is easy to test."""
    findings: list[tuple[str, str]] = []
    thresholds = config["thresholds"]
    benchmarks = config["benchmarks"]

    # HEALTH
    for label in ("campaign", "adset", "ad"):
        obj = snapshot.get(label) or {}
        if obj.get("issues_info"):
            findings.append((ALERT, f"{label} has issues: {json.dumps(obj['issues_info'])[:300]}"))
        status = obj.get("effective_status")
        if status and status not in ("ACTIVE", "PAUSED"):
            findings.append((ALERT, f"{label} status is {status}"))

    if (snapshot.get("account") or {}).get("account_status") not in (1, None):
        findings.append((ALERT, f"ad account status is {snapshot['account'].get('account_status')}, not active"))

    if snapshot.get("token_check_failed"):
        findings.append((WARN, "could not read the token's expiry date; check it by hand"))
    days_left = token_days_left(snapshot.get("token") or {})
    if days_left is not None and days_left <= thresholds["token_warn_days"]:
        on = token_expiry_date(snapshot.get("token") or {})
        findings.append((
            WARN,
            f"token expires in {days_left} days, on {on}. Regenerate it in Business "
            f"Settings and update your .env, or everything here goes quiet.",
        ))

    # GUARD
    if previous:
        for label in ("campaign", "adset", "ad"):
            was, now = previous.get(f"{label}_updated"), (snapshot.get(label) or {}).get("updated_time")
            if was and now and was != now:
                severity = ALERT if in_no_edit_window(config) else WARN
                findings.append((
                    severity,
                    f"{label} was edited since the last check ({was} to {now}). "
                    f"Editing a live ad set restarts the learning phase.",
                ))
        old_budget, new_budget = previous.get("daily_budget"), (snapshot.get("adset") or {}).get("daily_budget")
        if old_budget and new_budget and old_budget != new_budget:
            change = abs(int(new_budget) - int(old_budget)) / int(old_budget) * 100
            if change > thresholds["budget_step_warn_pct"]:
                findings.append((
                    WARN,
                    f"budget moved {change:.0f} percent in one step. Larger jumps tend to "
                    f"restart learning; smaller, more frequent nudges hold delivery steadier.",
                ))

    # SCORE
    lifetime = snapshot.get("maximum") or {}
    spend, leads = _float(lifetime, "spend"), _leads(lifetime)
    if leads == 0 and spend >= thresholds["alert_spend_no_lead_usd"]:
        findings.append((ALERT, f"${spend:.2f} spent, no leads yet"))
    elif leads == 0 and spend >= thresholds["warn_spend_no_lead_usd"]:
        findings.append((WARN, f"${spend:.2f} spent, no leads yet"))
    elif leads >= thresholds["min_leads_for_cpl_verdict"]:
        cpl = spend / leads
        low, high = benchmarks["cpl_band_usd"]
        if cpl > thresholds["cpl_warn_usd"]:
            findings.append((WARN, f"cost per lead is ${cpl:.2f} against a ${low}-${high} band"))
        elif cpl > high:
            findings.append((INFO, f"cost per lead is ${cpl:.2f}, above the ${low}-${high} band"))
        else:
            findings.append((INFO, f"cost per lead is ${cpl:.2f}, inside the ${low}-${high} band"))
    elif leads:
        findings.append((
            INFO,
            f"{leads} lead(s) so far, too few to judge cost per lead "
            f"(needs {thresholds['min_leads_for_cpl_verdict']})",
        ))

    today = snapshot.get("today") or {}
    if _float(today, "spend") == 0 and (snapshot.get("adset") or {}).get("effective_status") == "ACTIVE":
        findings.append((WARN, "no spend recorded today on an active ad set"))

    return findings


def token_days_left(token_payload: dict) -> int | None:
    """None means the token does not expire, which is a valid answer."""
    data = token_payload.get("data", token_payload)
    expires = data.get("expires_at")
    if not expires:
        return None
    delta = datetime.fromtimestamp(int(expires), tz=timezone.utc) - datetime.now(timezone.utc)
    return max(delta.days, 0)


def token_expiry_date(token_payload: dict) -> str:
    """The date, because that is what someone puts in a calendar."""
    data = token_payload.get("data", token_payload)
    expires = data.get("expires_at")
    if not expires:
        return "never"
    return datetime.fromtimestamp(int(expires), tz=timezone.utc).strftime("%-d %B %Y")


def in_no_edit_window(config: dict) -> bool:
    """True while the campaign is still learning and edits are most costly."""
    until = config.get("no_edit_window_until")
    if not until:
        return False
    try:
        return datetime.now(timezone.utc).date() <= datetime.strptime(until, "%Y-%m-%d").date()
    except ValueError:
        return False


def snapshot_state(snapshot: dict) -> dict:
    """The few fields we compare against next run to detect an edit."""
    return {
        "campaign_updated": (snapshot.get("campaign") or {}).get("updated_time"),
        "adset_updated": (snapshot.get("adset") or {}).get("updated_time"),
        "ad_updated": (snapshot.get("ad") or {}).get("updated_time"),
        "daily_budget": (snapshot.get("adset") or {}).get("daily_budget"),
        "creative_id": ((snapshot.get("ad") or {}).get("creative") or {}).get("id"),
    }


def worst(findings: list[tuple[str, str]]) -> str:
    return max((f[0] for f in findings), key=lambda s: SEVERITY_ORDER[s], default=INFO)


def render(findings: list[tuple[str, str]], snapshot: dict) -> str:
    lifetime = snapshot.get("maximum") or {}
    spend, leads = _float(lifetime, "spend"), _leads(lifetime)
    cpl = f"${spend / leads:.2f}" if leads else "n/a"
    lines = [
        f"Lifetime: ${spend:.2f} spent, {leads} leads, {cpl} per lead",
        f"Status:   ad set {(snapshot.get('adset') or {}).get('effective_status', 'unknown')}",
        "",
    ]
    for severity in (ALERT, WARN, INFO):
        for found_severity, text in findings:
            if found_severity == severity:
                lines.append(f"  [{severity}] {text}")
    if not findings:
        lines.append("  Nothing to report.")
    return "\n".join(lines)


def read_state(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def write_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, indent=2) + "\n")


def append_history(path: Path, snapshot: dict, findings: list[tuple[str, str]]) -> None:
    """Your own baseline data, which is worth more than any published benchmark
    once you have a few weeks of it."""
    lifetime = snapshot.get("maximum") or {}
    today = snapshot.get("today") or {}
    row = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "spend_today": _float(today, "spend"),
        "spend_lifetime": _float(lifetime, "spend"),
        "leads_lifetime": _leads(lifetime),
        "ctr_today": _float(today, "ctr"),
        "cpc_today": _float(today, "cpc"),
        # Logged, never judged. These build your own baseline over time, which
        # is what eventually answers the questions no published benchmark did.
        "cpm_today": _float(today, "cpm"),
        "frequency_today": _float(today, "frequency"),
        "worst": worst(findings),
    }
    with path.open("a") as handle:
        handle.write(json.dumps(row) + "\n")
