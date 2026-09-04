"""Prove the token works before anything tries to use it.

Four reads, in the order things actually break. Run this first whenever
something stops working: it tells you which of the four links in the chain is
the broken one, which is faster than reading a publish error and guessing.

It also prints the token's expiry date. `pulse` warns 14 days out, but `pulse`
only warns on a token that still works: once it has expired, the warning that
would have prevented it is exactly what stops running. Saying the date here, at
setup, is what gives someone the chance to write it down.
"""

from __future__ import annotations

from .graph import GraphError
from .pulse import token_expiry_date, token_days_left

# A dead token is a setup problem, not a campaign problem, and the two must not
# be reported the same way. Anything polling this has to be able to tell "your
# key needs regenerating" apart from "your ads are in trouble".
OK = 0
CAMPAIGN_PROBLEM = 1
SETUP_PROBLEM = 3


def run_check(api, env: dict) -> int:
    account, page = env["META_AD_ACCOUNT_ID"], env["META_PAGE_ID"]
    account_states = {1: "active", 2: "disabled", 3: "unsettled", 7: "pending review",
                      8: "pending closure", 9: "in grace period", 101: "closed"}
    ok = True

    print("Checking your Meta connection. The token itself is never printed.\n")

    try:
        me = api.get("me", fields="id,name")
        print(f"  Token works. System user: {me.get('name')}")
    except GraphError as exc:
        print(f"  Token failed: {exc.message}\n\n  {exc.explain()}")
        return SETUP_PROBLEM

    # Best effort. A token that works but whose expiry cannot be read is still a
    # working token, and losing this line must not fail the check.
    try:
        payload = api.debug_self()
        days = token_days_left(payload)
        on = token_expiry_date(payload)
        if days is None:
            print("     It does not expire. Nothing to diary, but it stays a live key to "
                  "this ad account until somebody revokes it.")
        else:
            print(f"     It expires in {days} days, on {on}. Write that date down: when it "
                  f"passes, the ads keep running and every command here stops.")
    except Exception:
        print("     Could not read its expiry date. Check it by hand in Business Settings.")

    try:
        data = api.get(account, fields="name,account_status,currency,timezone_name,amount_spent")
        state = account_states.get(data.get("account_status"), data.get("account_status"))
        print(f"  Ad account reachable: {data.get('name')} ({state}, {data.get('currency')})")
        if data.get("account_status") != 1:
            print(f"     Heads up: the account is {state}, so delivery may be stopped.")
            ok = False
    except GraphError as exc:
        print(f"  Ad account unreachable: {exc.message}\n     {exc.explain()}")
        ok = False

    try:
        data = api.get(page, fields="name")
        print(f"  Page reachable: {data.get('name')}")
    except GraphError as exc:
        print(f"  Page unreachable: {exc.message}\n     {exc.explain()}")
        ok = False

    # Done last on purpose. It is the step that fails when the system user has
    # the ad account but was never given a task on the page, and that is the
    # single most common setup mistake.
    try:
        forms = api.get(f"{page}/leadgen_forms", fields="id,name,status")
        print(f"  Lead forms readable: {len(forms.get('data', []))} on this page")
    except GraphError as exc:
        print(f"  Lead forms unreadable: {exc.message}\n     {exc.explain()}")
        print("     This is usually a missing page task. Give the system user")
        print("     MANAGE or ADVERTISE on the page in Business Settings.")
        ok = False

    print("\n" + ("Everything checks out. You can publish." if ok
                  else "Something above needs fixing before you publish."))
    return OK if ok else CAMPAIGN_PROBLEM
