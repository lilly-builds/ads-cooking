---
name: form
description: Change the questions or wording on a live Meta lead form. Meta forms cannot be edited, so this creates a new form, a new creative pointing at it, and swaps it onto the live ad. Use when the user says "/ads-cooking:form", "change the lead form", "add a question to the form", "the form is asking the wrong things", or wants to change what leads are asked.
---

# Change a live lead form

## Say this first, because it surprises everyone

**Meta lead forms cannot be edited.** Not by this tool, not in Ads Manager, not at all. Once a
form is published it is frozen. So "add a question" means: create a new form, create a new
creative pointing at it, and point the ad at that creative. One change, three steps, no way
around it.

The old form is never deleted. It keeps the leads it already collected, which is why deleting
it would be the wrong move even if you could.

## Edit the form

In `campaign.json`, under `lead_form`. Two rules Meta enforces and will reject the form over:

- **The consent checkbox must default to unchecked.** A pre-checked box is rejected.
- **Bullets in a list-style greeting must be under 80 characters each.**

## Run it

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking form
```

Dry run first. Then, only if they confirm:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking form --go
```

## Afterwards, do not skip this

It prints a new `form_id`. **Update `live.form_id` in `campaign.json` to that value.** If you do
not, the next copy change will point the ad back at the old form and quietly undo this.

Then tell them to check where the leads go. If leads flow into an email tool or CRM, that
connection is usually tied to the *form*, not the ad. A new form often means the connection has
to be repointed, and the failure mode is silent: the ads keep running, the leads keep coming,
and nothing arrives in the tool that is supposed to receive them. Worth a test lead.

## Fewer questions get more leads

If they are adding questions, it is fair to mention the tradeoff once: each extra field costs
completions. Say it once, then do what they asked.
