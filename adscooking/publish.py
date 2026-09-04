"""Create a lead campaign: campaign, ad set, video, thumbnail, form, creative, ad.

Two safety rules hold throughout, and they are the reason this file is worth
reading before you run it:

  * Dry run is the default. Without --go nothing is created; the payloads are
    printed instead. You have to opt in to spending money.
  * Everything is created PAUSED. Publishing and going live are separate
    decisions, and only a person makes the second one.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .graph import Graph


class DryRun:
    """Stands in for Graph during a dry run and records what would be sent.

    Same interface as Graph, so publish() has no idea which one it is holding
    and there is no `if dry_run` branching scattered through the steps.
    """

    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []
        self._counter = 0

    def _fake_id(self) -> str:
        self._counter += 1
        return f"dryrun-{self._counter}"

    def get(self, path, **params):
        self.calls.append(("GET", path, params))
        return {"id": self._fake_id(), "access_token": "dryrun-page-token"}

    def post(self, path, params, token=None):
        self.calls.append(("POST", path, params))
        return {"id": self._fake_id()}

    def upload(self, path, field, file_path, extra=None):
        self.calls.append(("UPLOAD", path, {"file": str(file_path), **(extra or {})}))
        return {"id": self._fake_id(), "hash": "dryrun-hash"}

    def page_token(self, page_id):
        self.calls.append(("GET", f"{page_id}?fields=access_token", {}))
        return "dryrun-page-token"


def image_hash(response: dict) -> str:
    """Pull the hash out of an /adimages response.

    The response nests it under the filename Meta chose, which is not the one
    you sent: {"images": {"<name>": {"hash": ..., "url": ...}}}. There is no
    top-level "hash". Reading for one and defaulting to "" would sail past a
    changed response shape and build a creative with an empty image, so this
    raises instead.
    """
    images = response.get("images")
    if images:
        first = next(iter(images.values()), {})
        if first.get("hash"):
            return first["hash"]
    # Some responses (and the dry run) do return it at the top level.
    if response.get("hash"):
        return response["hash"]
    raise KeyError(f"No image hash in the /adimages response: {response}")


def build_campaign(settings: dict) -> dict:
    return {
        "name": settings["name"],
        "objective": settings.get("objective", "OUTCOME_LEADS"),
        "buying_type": settings.get("buying_type", "AUCTION"),
        "special_ad_categories": settings.get("special_ad_categories", "[]"),
        # Required, and the error if you omit it does not say so clearly:
        # "Must specify True or False in is_adset_budget_sharing_enabled".
        # False means the budget lives on the ad set, not the campaign.
        "is_adset_budget_sharing_enabled": False,
        # Never ACTIVE from a script. A person flips this in Ads Manager after
        # looking at the preview.
        "status": "PAUSED",
    }


def usd_to_cents(amount) -> int:
    """Meta takes whole cents. Go through Decimal, not float.

    float(20.005) * 100 is 2000.4999999999998, which rounds down to the wrong
    cent. It is a small error on one budget and a compounding one on a hundred,
    and it is free to avoid.
    """
    return int(
        (Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def build_adset(settings: dict, campaign_id: str, page_id: str) -> dict:
    targeting = settings.get("targeting", {})
    spec: dict = {
        "geo_locations": {"countries": targeting.get("countries", ["US"])},
        "age_min": targeting.get("age_min", 18),
        "age_max": targeting.get("age_max", 65),
    }
    if targeting.get("genders"):
        spec["genders"] = targeting["genders"]

    # Advantage+ audience treats your targeting as a suggestion and forces ages
    # 25 to 65. Turning it off is the only way to hold an exact age range. But
    # the flag has to be sent explicitly even when off, or Meta rejects the ad
    # set with "Advantage Audience Flag Required".
    spec["targeting_automation"] = {
        "advantage_audience": 1 if targeting.get("advantage_audience") else 0
    }
    if targeting.get("publisher_platforms"):
        spec["publisher_platforms"] = targeting["publisher_platforms"]
    for key in ("facebook_positions", "instagram_positions"):
        if targeting.get(key):
            spec[key] = targeting[key]

    return {
        "name": settings["name"],
        "campaign_id": campaign_id,
        "daily_budget": usd_to_cents(settings["daily_budget_usd"]),
        "billing_event": settings.get("billing_event", "IMPRESSIONS"),
        "optimization_goal": settings.get("optimization_goal", "LEAD_GENERATION"),
        # Without a bid strategy Meta asks for a bid amount it never told you it
        # wanted: "Bid Amount Or Bid Constraints Required For Bid Strategy".
        # Automatic bidding with no cap is the right default at a small budget.
        "bid_strategy": settings.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP"),
        "destination_type": settings.get("destination_type", "ON_AD"),
        "promoted_object": {"page_id": page_id},
        "targeting": spec,
        "status": "PAUSED",
    }


def build_creative(settings: dict, page_id: str, video_id: str,
                   thumbnail_hash: str, form_id: str) -> dict:
    """One creative carrying several texts, so Meta can test combinations.

    asset_feed_spec is how you give Meta more than one primary text and headline
    on a single creative. It picks per person rather than splitting the budget
    across near-identical ads, which matters a lot at a small daily budget.
    """
    return {
        "name": settings["creative_name"],
        "object_story_spec": {
            "page_id": page_id,
            "video_data": {
                "video_id": video_id,
                "image_hash": thumbnail_hash,
                "call_to_action": {
                    "type": settings.get("cta_type", "SIGN_UP"),
                    "value": {"lead_gen_form_id": form_id},
                },
            },
        },
        "asset_feed_spec": {
            "bodies": [{"text": t} for t in settings["primary_texts"]],
            "titles": [{"text": t} for t in settings["headlines"]],
            "descriptions": [{"text": t} for t in settings.get("descriptions", [])],
            "ad_formats": ["SINGLE_VIDEO"],
        },
    }


def publish(campaign_config: dict, env: dict, go: bool = False,
            client: Graph | DryRun | None = None, base_dir: Path | None = None,
            resume: dict | None = None):
    """Run the six steps. Returns the ids created (or dry-run placeholders).

    `resume` carries ids from an earlier attempt, normally the `live` section of
    campaign.json. Any step whose id is already there is skipped. This matters
    because the video upload is the slow, expensive step: a failure at step 5
    should not mean pushing 55MB up the wire again to get back to it.
    """
    api = client or (Graph(env["META_SYSTEM_USER_TOKEN"]) if go else DryRun())
    account = env["META_AD_ACCOUNT_ID"]
    page_id = env["META_PAGE_ID"]
    base_dir = base_dir or Path.cwd()
    resume = {k: v for k, v in (resume or {}).items() if v and not k.startswith("_")}
    created: dict[str, str] = {}

    def step(number: int, label: str, key: str, make):
        if key in resume:
            created[key] = resume[key]
            print(f"{number}. {label}: reusing {resume[key]}")
            return
        print(f"{number}. {label}")
        created[key] = make()
        print(f"   {created[key]}")

    step(1, "Campaign", "campaign_id",
         lambda: api.post(f"{account}/campaigns",
                          build_campaign(campaign_config["campaign"]))["id"])

    step(2, "Ad set", "ad_set_id",
         lambda: api.post(f"{account}/adsets",
                          build_adset(campaign_config["ad_set"],
                                      created["campaign_id"], page_id))["id"])

    def upload_video():
        path = (base_dir / campaign_config["creative"]["video"]).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Creative video not found: {path}")
        return api.upload(f"{account}/advideos", "source", path)["id"]

    step(3, "Video", "video_id", upload_video)

    def upload_thumbnail():
        path = (base_dir / campaign_config["creative"]["thumbnail"]).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Thumbnail not found: {path}")
        return image_hash(api.upload(f"{account}/adimages", "filename", path))

    step(4, "Thumbnail", "thumbnail_hash", upload_thumbnail)

    # Page-owned endpoint, so this needs the page token, not the system-user one.
    step(5, "Lead form", "form_id",
         lambda: api.post(f"{page_id}/leadgen_forms", campaign_config["lead_form"],
                          token=api.page_token(page_id))["id"])

    step(6, "Creative", "creative_id",
         lambda: api.post(f"{account}/adcreatives",
                          build_creative(campaign_config["creative"], page_id,
                                         created["video_id"], created["thumbnail_hash"],
                                         created["form_id"]))["id"])

    step(7, "Ad", "ad_id",
         lambda: api.post(f"{account}/ads", {
             "name": campaign_config["ad"]["name"],
             "adset_id": created["ad_set_id"],
             "creative": {"creative_id": created["creative_id"]},
             "status": "PAUSED",
         })["id"])

    if isinstance(api, DryRun):
        print(summarise(campaign_config, api))
        print(f"\nDry run. {len(api.calls)} calls were built and none were sent.")
        print("Re-run with --go to create these for real. Everything lands PAUSED.")
    else:
        print("\nCreated, all PAUSED. Open Ads Manager, check the preview and the")
        print("form, then set the campaign, ad set and ad to ACTIVE yourself.")
        print("\nPaste these into the `live` section of campaign.json so the other")
        print("commands know what to change:")
        for key, value in created.items():
            print(f'    "{key}": "{value}",')
    return created


def summarise(campaign_config: dict, api: "DryRun") -> str:
    """What a dry run is for: seeing the decisions before money is involved.

    Deliberately not a JSON dump. The things worth checking before you spend
    are the budget, who it targets, and where the leads land.
    """
    adset = campaign_config["ad_set"]
    targeting = adset.get("targeting", {})
    creative = campaign_config["creative"]

    ages = f"{targeting.get('age_min', 18)} to {targeting.get('age_max', 65)}"
    genders = targeting.get("genders")
    who = {1: "men", 2: "women"}.get(genders[0]) if genders and len(genders) == 1 else "all genders"
    places = ", ".join(targeting.get("countries", ["US"]))
    daily = float(adset["daily_budget_usd"])

    lines = [
        "",
        "Check these before you run it for real:",
        "",
        f"  Budget      ${daily:.2f} a day, about ${daily * 30:.0f} a month",
        f"  Audience    {who}, {ages}, in {places}",
        f"  Placements  {', '.join(targeting.get('publisher_platforms', ['automatic']))}",
        f"  Creative    {creative['video']}",
        f"  Copy        {len(creative['primary_texts'])} primary texts, "
        f"{len(creative['headlines'])} headlines",
        f"  Leads go to the instant form '{campaign_config['lead_form']['name']}'",
        "",
        "  Everything is created PAUSED. Nothing spends until you set it active",
        "  yourself in Ads Manager.",
    ]

    privacy = (campaign_config["lead_form"].get("privacy_policy") or {}).get("url", "")
    if "example.com" in privacy:
        lines += ["", "  Warning: the lead form still points at example.com for its privacy",
                  "  policy. Meta will reject the form. Set a real URL first."]
    return "\n".join(lines)
