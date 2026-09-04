"""Changing a live ad: new copy, or a new lead form.

Both jobs end the same way, because of a Meta constraint that surprises nearly
everyone the first time:

    An ad creative cannot be edited. A lead form cannot be edited either.

So "change the headline" is not an update, it is: build a new creative, then
point the existing ad at it. And "add a question to the form" is: build a new
form, build a new creative pointing at that form, then point the ad at the new
creative. One conceptual change, three API calls, and no way around it.

Doing it this way also happens to be safer than editing would be. The ad keeps
its id, so its learning history survives, and the old creative stays intact if
you need to look at what was running before.
"""

from __future__ import annotations

from .graph import Graph


def swap_creative(api: Graph, ad_id: str, creative_id: str) -> dict:
    """Point an existing ad at a different creative. The ad keeps its id."""
    return api.post(ad_id, {"creative": {"creative_id": creative_id}})


def build_text_creative(settings: dict, page_id: str, video_id: str,
                        thumbnail_hash: str, form_id: str,
                        primary_texts: list[str], headlines: list[str]) -> dict:
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
            "bodies": [{"text": t} for t in primary_texts],
            "titles": [{"text": t} for t in headlines],
            "ad_formats": ["SINGLE_VIDEO"],
        },
    }


def update_copy(campaign_config: dict, env: dict, live: dict, api: Graph) -> dict:
    """Swap in new ad copy. Reuses the uploaded video, thumbnail and form."""
    creative_settings = campaign_config["creative"]
    creative = api.post(
        f"{env['META_AD_ACCOUNT_ID']}/adcreatives",
        build_text_creative(
            creative_settings,
            env["META_PAGE_ID"],
            live["video_id"],
            live["thumbnail_hash"],
            live["form_id"],
            creative_settings["primary_texts"],
            creative_settings["headlines"],
        ),
    )
    print(f"1. New creative {creative['id']}")
    swap_creative(api, live["ad_id"], creative["id"])
    print(f"2. Ad {live['ad_id']} now uses it")
    print("\nThe ad kept its id, so its delivery history carries over.")
    return {"creative_id": creative["id"]}


def update_form(campaign_config: dict, env: dict, live: dict, api: Graph) -> dict:
    """Publish a changed lead form. Forms are immutable, so this makes a new one."""
    page_id = env["META_PAGE_ID"]
    form = api.post(
        f"{page_id}/leadgen_forms",
        campaign_config["lead_form"],
        token=api.page_token(page_id),
    )
    print(f"1. New form {form['id']} (the old one is untouched and keeps its leads)")

    creative_settings = campaign_config["creative"]
    creative = api.post(
        f"{env['META_AD_ACCOUNT_ID']}/adcreatives",
        build_text_creative(
            creative_settings,
            page_id,
            live["video_id"],
            live["thumbnail_hash"],
            form["id"],
            creative_settings["primary_texts"],
            creative_settings["headlines"],
        ),
    )
    print(f"2. New creative {creative['id']} pointing at it")
    swap_creative(api, live["ad_id"], creative["id"])
    print(f"3. Ad {live['ad_id']} now uses it")
    print("\nUpdate form_id in your campaign.json to the new id above, or the next")
    print("run will still reference the old form.")
    return {"form_id": form["id"], "creative_id": creative["id"]}
