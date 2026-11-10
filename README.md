# Aquarium Feeding Planner

A standalone Home Assistant integration for two independent feeding plans. Version 0.2.0 targets Home Assistant Core 2026.9 or newer.

## Install through HACS

1. In **HACS → ⋮ → Custom repositories**, enter the public GitHub repository URL for Aquarium Feeding Planner and choose **Integration**.
2. Download **Aquarium Feeding Planner** in HACS and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and search for **Aquarium Feeding Planner**.
4. Enter **Main tank** as the tank name and choose the **Main tank** starter plan. Add the integration again, name the second entry **Cherry shrimp**, and choose the **Cherry shrimp** starter plan.

If you already set up version 0.1.0, back up Home Assistant, install the new code in the same integration directory, and restart. The existing entries, custom portions and feeding confirmations carry over.

### Publish the source bundle to your own repository

Extract the source ZIP. Put its contents at the root of a public GitHub repository so `hacs.json`, `README.md`, and `custom_components/` are visible at the top level. The manifest's documentation URL points to the intended repository `Pogo86/aquarium-feeding-planner`. Update the documentation and issue tracker URLs in the manifest if you publish under another name. HACS can download the default branch, and a GitHub release tagged `v0.2.0` gives the download a named version.

Each entry creates one device with a **Feeding plan** sensor and a **Mark as fed** button. Find both on the device page and add them to a dashboard. Open the sensor for today's quantities and the time of the last confirmed feeding. The sensor reports `due`, `fed` or `rest_day`. Pressing the button records one confirmation per local day for that tank, even if you press twice.

## Manage foods and purchase links

On either tank's integration entry, choose **Configure → Manage foods and purchase links**. Add a food name and an optional purchase URL, or edit an existing food. The catalogue is shared across tanks. The starter foods already have Heron's product links.

Under **Add a food or portion** or **Edit a food or portion**, choose a food from the dropdown and enter the dry weight, recipient and days. Editing a catalogue name updates all portions that use that food.

## Change food, days or grams

Open the relevant entry under **Settings → Devices & services → Aquarium Feeding Planner** and choose **Configure**. Choose **Edit a food or portion** to change the grams, selected food, recipient, days or serving note. You can also add and remove portions. A portion set to 0 g is paused.

Regular weekdays repeat every week. Extra days apply on either Week A or Week B. The first Week A starts on Monday 9 November 2026, so Saturday 14 November is a bloodworm day. Use **Set the first Monday of Week A** to shift the rotation. Weights in the starter plans are dry weights for the group. The shrimp weight is per roughly 10 adults, as indicated in its serving note.

## Send the evening reminder

Open your existing aquarium feeding automation, choose **Edit in YAML**, and paste in `evening_reminder.yaml`. Replace the person entity, phone action and two sensor entity IDs with the ones shown in your Home Assistant. The reminder checks once a minute, from 18:00, and sends when you have been home for 30 continuous minutes and a tank has a meal due. It sends once per evening and includes only tanks still due when it runs.

**Run actions** can preview the message but skips the presence and time conditions. Let the automation trigger normally to test those conditions.

## Show today's meals on your dashboard

Add a **Markdown** card and paste this into its content. Use the actual sensor IDs shown on your two device pages.

```jinja
### Main tank · {{ states('sensor.main_tank_feeding_plan') | replace('_', ' ') }}
{{ (state_attr('sensor.main_tank_feeding_plan', 'meal') or 'No meal scheduled.') | replace('\n', '  \n') }}

### Cherry shrimp · {{ states('sensor.cherry_shrimp_feeding_plan') | replace('_', ' ') }}
{{ (state_attr('sensor.cherry_shrimp_feeding_plan', 'meal') or 'No meal scheduled.') | replace('\n', '  \n') }}
```

Add both **Mark as fed** buttons below the card to confirm each tank separately.

### Clickable food links

Add another Markdown card with this content. The same catalogue is available from either tank's feeding-plan sensor.

```jinja
### Where to buy food
{% set foods = state_attr('sensor.main_tank_feeding_plan', 'food_catalogue') or [] %}
{% for food in foods if food.url -%}
- [{{ food.name | replace('[', '&#91;') | replace(']', '&#93;') }}](<{{ food.url }}>)
{% endfor -%}
```

