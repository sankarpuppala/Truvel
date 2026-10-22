"""Deterministic demo data (SPEC §17 item 9).

    python -m scripts.demo_data            # add to whatever is already seeded
    python -m scripts.demo_data --reset    # wipe and rebuild from scratch

This builds the content the design reference shows -- Hyderabad, Khajaguda
Rocks, Golconda Fort, Durgam Cheruvu, the Qutb Shahi Tombs, Bansilalpet
Stepwell, a fragile stepwell, Athirappilly Falls in Kerala -- with 12 users
(3 of them creators), names in several scripts, likes, views, saves, visits,
Pulse reports, last-mile steps, touches and videos.

Everything it writes is flagged:

* users have `demo = True`
* visits have `simulated = False` but are historical, so they verify places and
  clear fog while staying out of the dev-simulator exclusion -- they are
  *fabricated*, not *simulated location*, and the report says so
* no rupee figure is invented: the Studio derives earnings from the simulated
  pool in config

Place and city names are real. Every count, user, tip, live report, last-mile
direction and safety note is invented for illustration, exactly as the design
reference's footnote says.

Photos are **not** fabricated: demo places carry no uploaded images, so the UI
shows the category illustration (SPEC §12.6), which is what the reference
mock-ups do. Real photos and videos come from the two places and two videos
added on site (PLAN.md Day 5).
"""
from __future__ import annotations

import argparse
import io
import random
import sys
from datetime import datetime, timedelta

from PIL import Image, ImageDraw
from sqlmodel import Session, func, select

from app import kadam
from app.auth import hash_password
from app.config import regional_langs
from app.db import engine, init_db, rebuild_fts
from app.media_store import process_photo
from app.models import (
    Attribution,
    CategoryPref,
    City,
    Follow,
    LastMileStep,
    LastMileVote,
    Like,
    Media,
    MediaLike,
    MediaView,
    Neighbourhood,
    Place,
    PlaceName,
    Pulse,
    Save,
    Touch,
    User,
    View,
    Visit,
    utcnow,
)
from app.partner.attribution import TouchRow, attribute

PASSWORD = "truvel demo"          # every demo account, so the viva can log in
RNG = random.Random(20261020)       # fixed seed: the demo is reproducible

# --------------------------------------------------------------------------- #
# The content
# --------------------------------------------------------------------------- #

HYDERABAD_AREAS = [
    ("Banjara Hills", 17.4156, 78.4347),
    ("Gachibowli", 17.4401, 78.3489),
    ("Madhapur", 17.4483, 78.3915),
    ("Golconda", 17.3833, 78.4011),
    ("Secunderabad", 17.4399, 78.4983),
    ("Mehdipatnam", 17.3953, 78.4389),
    ("Kondapur", 17.4615, 78.3639),
    ("Khajaguda", 17.4186, 78.3391),
    ("Jubilee Hills", 17.4319, 78.4073),
    ("Charminar", 17.3616, 78.4747),
    ("Begumpet", 17.4439, 78.4738),
    ("Ameerpet", 17.4374, 78.4487),
]

USERS = [
    ("meera_k", "Meera K.", "Finds rocks and ridges around Hyderabad.", True),
    ("rohit_walks", "Rohit", "Walks the city. Posts the way in, not just the view.", True),
    ("keralawanders", "Kerala Wanders", "Waterfalls, monsoon, Western Ghats.", True),
    ("riya_s", "Riya S.", "Weekend explorer. Hyderabad.", False),
    ("arjun_t", "Arjun T.", "", False),
    ("sana_m", "Sana M.", "", False),
    ("vikram_r", "Vikram R.", "", False),
    ("priya_n", "Priya N.", "", False),
    ("kiran_b", "Kiran B.", "", False),
    ("deepa_v", "Deepa V.", "", False),
    ("naveen_p", "Naveen P.", "", False),
    ("fatima_z", "Fatima Z.", "", False),
]

# name, category, lat, lng, area, source, fame, status, fragile, names, description,
# activities, safety, finder
PLACES: list[dict] = [
    {
        "en": "Khajaguda Rocks",
        "names": {
            "te": "ఖాజాగూడ గుట్టలు",
            "hi": "खाजागूड़ा चट्टानें",
            "ur": "خاجہ گوڑا چٹانیں",
        },
        "category": "viewpoint",
        "lat": 17.4186,
        "lng": 78.3391,
        "area": "Khajaguda",
        "source": "community",
        "fame": "hidden",
        "finder": "meera_k",
        "description": (
            "Giant granite boulders stacked on a ridge, a short scramble above the lane. "
            "People come for the sunset over the Financial District skyline; mornings are "
            "quiet and cool."
        ),
        "activities": ["Sunset", "Photography", "Short climb", "Bouldering"],
        "best_time": {
            "time": "Evening, 5:00-6:30 pm - early morning",
            "months": "Oct-Feb best - hot Apr-May",
            "avoid": "Right after rain: the rock is slippery",
        },
        "entry_fee_text": "Free - open ground, no fixed hours",
        "timings_text": "No fixed hours",
        "access": {
            "road": "Bike or car to the end of the lane",
            "walk_min_from_road": 10,
            "nearest_transit_text": "Nearest bus stop: Khajaguda, 1.2 km",
            "parking": "On the lane",
        },
        "accessibility": {
            "wheelchair": "no",
            "steps_count_text": "No - rocky path and a scramble",
            "toilets": "None nearby",
            "drinking_water": "Carry your own",
            "shade": "Little; go after 4 pm",
            "food_nearby": "Tea stall on the main road",
        },
        "safety": {
            "steep_edge": "yes",
            "slippery_in_monsoon": "yes",
            "isolated": "yes",
            "no_mobile_signal": "no",
            "water_danger": "no",
            "wildlife": "no",
            "permit_needed": "no",
            "sacred": "no",
        },
        "steps": [
            "Park where the paved lane ends, next to the water tank.",
            "Take the mud path that starts behind the tank. Keep the boundary wall on your left.",
            "At the lone neem tree the path splits. Go right; the left path dead-ends.",
            "Climb the flat face of the big boulder. There are natural footholds; go slow.",
        ],
        "tip": "Go 20 min before sunset; the city lights come on behind you.",
        "likes": 96,
        "viewers": 112,
    },
    {
        "en": "Golconda Fort",
        "names": {
            "te": "గోల్కొండ కోట",
            "hi": "गोलकुंडा किला",
            "ur": "گولکندہ قلعہ",
            "ta": "கோல்கொண்டா கோட்டை",
            "bn": "গোলকুন্ডা কেলা",
        },
        "category": "fort_heritage",
        "lat": 17.3833,
        "lng": 78.4011,
        "area": "Golconda",
        "source": "wikidata",
        "fame": "famous",
        "sitelinks": 42,
        "wikidata": "Q1134499",
        "description": (
            "A 16th-century hill fort of the Qutb Shahi dynasty, famous for its acoustics: "
            "a clap at the entrance carries to the top."
        ),
        "activities": ["Heritage walk", "Sunset", "Photography"],
        "best_time": {"time": "Morning or late afternoon", "months": "Oct-Feb"},
        "entry_fee_text": "Rs 25 (Indian nationals) - Rs 300 (others)",
        "timings_text": "9:00 am - 5:30 pm",
        "access": {
            "road": "Auto or bus to the fort gate",
            "walk_min_from_road": 2,
            "nearest_transit_text": "Golconda Fort bus stop at the gate",
            "parking": "Paid parking at the gate",
        },
        "accessibility": {
            "wheelchair": "partly",
            "steps_count_text": "About 380 steps to the top pavilion",
            "toilets": "Yes, near the entrance",
            "drinking_water": "Yes",
            "shade": "Little on the climb",
            "food_nearby": "Stalls outside the gate",
        },
        "safety": {
            "steep_edge": "yes",
            "slippery_in_monsoon": "yes",
            "no_mobile_signal": "no",
            "isolated": "no",
            "water_danger": "no",
            "wildlife": "no",
            "permit_needed": "no",
            "sacred": "no",
        },
        "likes": 820,
        "viewers": 1180,
    },
    {
        "en": "Qutb Shahi Tombs",
        "names": {
            "te": "కుతుబ్ షాహీ సమాధులు",
            "ur": "قطب شاہی مقابر",
            "hi": "कुतुबशाही मकबरे",
        },
        "category": "fort_heritage",
        "lat": 17.3947,
        "lng": 78.3966,
        "area": "Ibrahim Bagh",
        "source": "wikidata",
        "fame": "famous",
        "sitelinks": 21,
        "wikidata": "Q2630839",
        "description": (
            "Seven generations of Qutb Shahi rulers in one walled garden of domed tombs, "
            "restored over the last decade."
        ),
        "activities": ["Heritage walk", "Photography", "Gardens"],
        "best_time": {"time": "Early morning", "months": "Oct-Mar"},
        "entry_fee_text": "Rs 20",
        "timings_text": "9:30 am - 6:30 pm, closed Friday",
        "access": {
            "road": "Auto from Golconda, 1.5 km",
            "walk_min_from_road": 3,
            "nearest_transit_text": "Golconda bus stop, 1.5 km",
            "parking": "Yes",
        },
        "accessibility": {
            "wheelchair": "yes",
            "steps_count_text": "Paved paths; a few steps at each tomb",
            "toilets": "Yes",
            "drinking_water": "Yes",
            "shade": "Trees along the paths",
            "food_nearby": "No",
        },
        "safety": {
            "sacred": "yes",
            "steep_edge": "no",
            "water_danger": "no",
            "slippery_in_monsoon": "no",
            "no_mobile_signal": "no",
            "isolated": "no",
            "wildlife": "no",
            "permit_needed": "no",
        },
        "likes": 540,
        "viewers": 760,
    },
    {
        "en": "Durgam Cheruvu",
        "names": {
            "te": "దుర్గం చెరువు",
            "hi": "दुर्गम झील",
            "ur": "درگم جھیل",
        },
        "category": "lake",
        "lat": 17.4316,
        "lng": 78.3853,
        "area": "Madhapur",
        "source": "osm",
        "fame": "known",
        "osm_type": "way",
        "osm_id": 123456789,
        "description": (
            "A rock-bound lake between Jubilee Hills and Madhapur, with a cable bridge over "
            "the gorge and a walking path along the water."
        ),
        "activities": ["Walk", "Kayaking", "Sunset", "Photography"],
        "best_time": {"time": "Evening", "months": "All year"},
        "entry_fee_text": "Rs 50 for the park",
        "timings_text": "11:00 am - 9:00 pm",
        "access": {
            "road": "Road to the gate",
            "walk_min_from_road": 2,
            "nearest_transit_text": "Jubilee Hills Check Post metro, 2 km",
            "parking": "Yes",
        },
        "accessibility": {
            "wheelchair": "partly",
            "steps_count_text": "Paved promenade; steps down to the water",
            "toilets": "Yes",
            "drinking_water": "Yes",
            "shade": "Some",
            "food_nearby": "Cafes at the gate",
        },
        "safety": {
            "water_danger": "yes",
            "steep_edge": "yes",
            "slippery_in_monsoon": "no",
            "no_mobile_signal": "no",
            "isolated": "no",
            "wildlife": "no",
            "permit_needed": "no",
            "sacred": "no",
        },
        "likes": 330,
        "viewers": 920,
    },
    {
        "en": "Bansilalpet Stepwell",
        "names": {
            "te": "బంసిలాల్‌పేట్ మెట్లబావి",
            "hi": "बंसीलालपेठ बावडी",
        },
        "category": "beach_river",
        "lat": 17.4452,
        "lng": 78.4983,
        "area": "Secunderabad",
        "source": "community",
        "fame": "hidden",
        "finder": "riya_s",
        "description": (
            "A 17th-century stepwell in Secunderabad, buried under rubbish for decades and "
            "cleaned out by a community restoration. The stonework steps are back."
        ),
        "activities": ["Heritage walk", "Photography"],
        "best_time": {"time": "Morning", "months": "All year"},
        "entry_fee_text": "Free",
        "timings_text": "8:00 am - 6:00 pm",
        "access": {
            "road": "Lane off Bansilalpet main road",
            "walk_min_from_road": 3,
            "nearest_transit_text": "Secunderabad station, 2 km",
            "parking": "On the street",
        },
        "accessibility": {
            "wheelchair": "no",
            "steps_count_text": "Deep stone steps on all four sides",
            "toilets": "No",
            "drinking_water": "No",
            "shade": "Little",
            "food_nearby": "Yes, on the main road",
        },
        "safety": {
            "steep_edge": "yes",
            "water_danger": "yes",
            "slippery_in_monsoon": "yes",
            "no_mobile_signal": "no",
            "isolated": "no",
            "wildlife": "no",
            "permit_needed": "no",
            "sacred": "no",
        },
        "steps": [
            "From the main road, take the lane beside the water tank.",
            "The gate is 200 m in on the right, past the temple.",
            "Steps start immediately inside. Hold the rail on the way down.",
        ],
        "tip": "Go before 9 am: the light reaches the bottom step.",
        "likes": 74,
        "viewers": 96,
    },
    {
        "en": "Hussain Sagar",
        "names": {
            "te": "హుస్సెన్ సాగర్",
            "ur": "حسین ساگر",
            "hi": "हुसैन सागर",
        },
        "category": "lake",
        "lat": 17.4239,
        "lng": 78.4738,
        "area": "Begumpet",
        "source": "wikidata",
        "fame": "famous",
        "sitelinks": 28,
        "wikidata": "Q1636646",
        "description": "The lake at the centre of the city, dug in 1563, with the Buddha statue on its island.",
        "activities": ["Boat ride", "Walk", "Sunset"],
        "best_time": {"time": "Evening", "months": "All year"},
        "entry_fee_text": "Free - boat tickets extra",
        "timings_text": "Open all day",
        "access": {"road": "Tank Bund road", "walk_min_from_road": 0, "nearest_transit_text": "Secunderabad, 3 km", "parking": "Yes"},
        "accessibility": {"wheelchair": "yes", "toilets": "Yes", "drinking_water": "Yes", "shade": "Some", "food_nearby": "Yes", "steps_count_text": "Flat promenade"},
        "safety": {"water_danger": "yes", "steep_edge": "no", "slippery_in_monsoon": "no", "no_mobile_signal": "no", "isolated": "no", "wildlife": "no", "permit_needed": "no", "sacred": "no"},
        "likes": 410,
        "viewers": 1320,
    },
    {
        "en": "Ananthagiri Hills",
        "names": {
            "te": "అనంతగిరి కొండలు",
            "hi": "अनंतगिरि पहाड़ियाँ",
        },
        "category": "hill_trek",
        "lat": 17.3300,
        "lng": 78.0100,
        "area": "Vikarabad",
        "source": "osm",
        "fame": "known",
        "osm_type": "node",
        "osm_id": 234567891,
        "description": "Forested hills about 80 km west of the city, with a temple, a reservoir and easy walking trails.",
        "activities": ["Trek", "Birdwatching", "Camping"],
        "best_time": {"time": "Early morning", "months": "Jul-Feb"},
        "entry_fee_text": "Free",
        "timings_text": "Daylight hours",
        "access": {"road": "Road to Vikarabad, then 5 km", "walk_min_from_road": 15, "nearest_transit_text": "Vikarabad railway station, 6 km", "parking": "At the temple"},
        "accessibility": {"wheelchair": "no", "toilets": "At the temple", "drinking_water": "Carry your own", "shade": "Good, forested", "food_nearby": "Vikarabad town", "steps_count_text": "Forest trails, uneven"},
        "safety": {"isolated": "yes", "no_mobile_signal": "yes", "wildlife": "yes", "slippery_in_monsoon": "yes", "steep_edge": "no", "water_danger": "no", "permit_needed": "no", "sacred": "yes"},
        "likes": 180,
        "viewers": 300,
    },
    {
        "en": "Sunset ridge",
        "names": {"te": "సన్సెట్ రిడ్జ్"},
        "category": "viewpoint",
        "lat": 17.4502,
        "lng": 78.3285,
        "area": "Gachibowli",
        "source": "community",
        "fame": "hidden",
        "finder": "riya_s",
        "description": (
            "A low rocky ridge behind the university land. Nobody is ever here. The whole "
            "western sky opens up and the sun goes down behind the water tank."
        ),
        "activities": ["Sunset", "Photography", "Short walk"],
        "best_time": {"time": "5:30-6:15 pm", "months": "Oct-Feb", "avoid": "After dark: no lights"},
        "entry_fee_text": "Free",
        "timings_text": "No fixed hours",
        "access": {"road": "Bike to the end of the service road", "walk_min_from_road": 8, "nearest_transit_text": "Gachibowli bus stop, 2 km", "parking": "On the road"},
        "accessibility": {"wheelchair": "no", "toilets": "No", "drinking_water": "No", "shade": "None", "food_nearby": "No", "steps_count_text": "Rough path, one short scramble"},
        "safety": {"isolated": "yes", "steep_edge": "yes", "no_mobile_signal": "no", "slippery_in_monsoon": "yes", "water_danger": "no", "wildlife": "no", "permit_needed": "no", "sacred": "no", "women_safety_note": "Quiet after dark. Better in a group, and leave before the light goes."},
        "steps": [
            "Ride to the end of the service road, past the last apartment gate.",
            "Walk left along the fence line for about 300 m.",
            "Where the fence turns, a footpath goes up the rock. Follow it to the flat top.",
        ],
        "tip": "Carry water. There is no shade and no shop for 2 km.",
        "likes": 52,
        "viewers": 61,
    },
    {
        "en": "Peacock Lake stepwell",
        "names": {"te": "నెమలి చెరువు మెట్లబావి"},
        "category": "beach_river",
        "lat": 17.4690,
        "lng": 78.3120,
        "area": "Kondapur",
        "source": "community",
        "fame": "hidden",
        "finder": "riya_s",
        "fragile": True,
        "description": (
            "A small unrestored stepwell on private farmland, with original carving still "
            "intact. The owner allows visitors who ask. Please do not post the exact pin."
        ),
        "activities": ["Heritage", "Photography"],
        "best_time": {"time": "Morning", "months": "Nov-Feb"},
        "entry_fee_text": "Free - ask the farm owner first",
        "timings_text": "Daylight, with permission",
        "access": {"road": "Farm track", "walk_min_from_road": 12, "nearest_transit_text": "Kondapur, 4 km", "parking": "On the track"},
        "accessibility": {"wheelchair": "no", "toilets": "No", "drinking_water": "No", "shade": "Some", "food_nearby": "No", "steps_count_text": "Original stone steps, no rail"},
        "safety": {"steep_edge": "yes", "water_danger": "yes", "permit_needed": "yes", "isolated": "yes", "slippery_in_monsoon": "yes", "no_mobile_signal": "yes", "wildlife": "no", "sacred": "no"},
        "steps": [
            "Ask at the farmhouse on the main track first. They will point you down.",
            "The well is behind the mango trees, 200 m past the pump house.",
            "The steps are original and have no rail. Do not go down alone.",
        ],
        "likes": 28,
        "viewers": 34,
    },
    {
        "en": "Athirappilly Falls",
        "names": {
            "ml": "അതിരപ്പിള്ളി വെള്ളച്ചാട്ടം",
            "ta": "அதிரப்பிள்ளி அருவி",
            "hi": "अथिरप्पल्ली जलप्रपात",
        },
        "category": "waterfall",
        "lat": 10.2850,
        "lng": 76.5690,
        "area": "Thrissur",
        "state": "Kerala",
        "source": "wikidata",
        "fame": "famous",
        "sitelinks": 19,
        "wikidata": "Q2867470",
        "description": (
            "The widest waterfall in Kerala, 24 m high on the Chalakudy river at the edge of "
            "the Vazhachal forest. Thunderous in the monsoon."
        ),
        "activities": ["Waterfall", "Photography", "Forest walk"],
        "best_time": {"time": "Morning", "months": "Jun-Sep for full flow", "avoid": "Peak monsoon days when the path closes"},
        "entry_fee_text": "Rs 40",
        "timings_text": "8:00 am - 6:00 pm",
        "access": {"road": "Road to the gate from Chalakudy, 30 km", "walk_min_from_road": 10, "nearest_transit_text": "Chalakudy railway station, 30 km", "parking": "Yes, at the gate"},
        "accessibility": {"wheelchair": "partly", "steps_count_text": "Viewpoint is level; the base needs about 100 steps", "toilets": "Yes", "drinking_water": "Yes", "shade": "Forest canopy", "food_nearby": "Stalls at the gate"},
        "safety": {"water_danger": "yes", "slippery_in_monsoon": "yes", "steep_edge": "yes", "wildlife": "yes", "no_mobile_signal": "yes", "isolated": "no", "permit_needed": "no", "sacred": "no"},
        "likes": 1240,
        "viewers": 1900,
    },
]

VIDEOS = [
    ("keralawanders", "Athirappilly Falls", 24.0,
     "Monsoon is the time. The viewpoint is a 10-minute walk from the gate; wear shoes with grip.", "ml"),
    ("riya_s", "Sunset ridge", 41.0,
     "Sunset ridge - how to get there. Park at the last gate and follow the fence line.", "en"),
    ("meera_k", "Khajaguda Rocks", 24.0,
     "Khajaguda at golden hour. Come up the right-hand path, the left one dead-ends.", "en"),
    ("rohit_walks", "Bansilalpet Stepwell", 18.0,
     "Bansilalpet stepwell after the restoration. Go before 9 am for the light.", "en"),
    ("meera_k", "Khajaguda Rocks", 32.0,
     "The scramble up the big boulder, filmed slowly so you can see the footholds.", "en"),
    ("keralawanders", "Athirappilly Falls", 52.0,
     "Full flow in July. You can feel the spray from the top viewpoint.", "ml"),
]

PULSES = [
    ("Khajaguda Rocks", "riya_s", 0.7, {"crowd": "quiet", "path": "dry", "open": "yes"},
     "Breezy on top, carry water."),
    ("Athirappilly Falls", "keralawanders", 3.0, {"water": "flowing", "crowd": "busy", "open": "yes"},
     "Flowing strongly, spray reaches the viewpoint."),
    ("Durgam Cheruvu", "arjun_t", 2.0, {"crowd": "busy", "path": "dry", "open": "yes"}, ""),
    ("Golconda Fort", "sana_m", 20.0, {"crowd": "packed", "open": "yes"}, "Weekend crowd, go early."),
    ("Sunset ridge", "riya_s", 30.0, {"crowd": "quiet", "path": "dry"}, "Nobody here at all."),
]


def illustration_photo(category: str, seed: int) -> bytes:
    """A flat layered landscape as a stand-in poster for demo videos.

    Not a photograph and not pretending to be one: it is the same flat
    illustration language the UI uses for places without photos (SPEC §12.6),
    rendered to a file so video posters have something real to show.
    """
    palettes = {
        "waterfall": [(38, 70, 83), (42, 157, 143), (138, 177, 125), (233, 196, 106)],
        "viewpoint": [(44, 42, 85), (180, 80, 63), (238, 154, 60), (248, 210, 126)],
        "lake": [(143, 191, 211), (94, 154, 164), (243, 217, 177), (120, 160, 140)],
        "fort_heritage": [(201, 150, 98), (166, 110, 70), (120, 80, 60), (240, 220, 180)],
        "hill_trek": [(220, 231, 225), (126, 163, 148), (76, 122, 105), (47, 93, 80)],
        "beach_river": [(230, 215, 185), (190, 170, 140), (120, 145, 150), (80, 105, 115)],
    }
    colours = palettes.get(category, palettes["viewpoint"])
    rng = random.Random(seed)
    width, height = 1080, 1920
    img = Image.new("RGB", (width, height), colours[0])
    draw = ImageDraw.Draw(img)

    # Sky bands, then three layered ridges: the "flat layered landscape" motif.
    for i in range(6):
        y0 = int(height * 0.08 * i)
        draw.rectangle([0, y0, width, y0 + int(height * 0.08)], fill=colours[min(2, i // 2)])
    base = int(height * 0.45)
    for layer, colour in enumerate(colours[1:], start=1):
        points = [(0, height)]
        y = base + layer * int(height * 0.12)
        for x in range(0, width + 120, 120):
            points.append((x, y - rng.randint(0, 140)))
        points.append((width, height))
        draw.polygon(points, fill=colour)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def reset() -> None:
    """Drop and recreate every table. Only for `--reset`.

    Dropping the schema rather than deleting rows avoids having to get the
    foreign-key order right by hand, and it clears the FTS index and triggers
    too (`init_db` rebuilds them).
    """
    from sqlalchemy import text
    from sqlmodel import SQLModel

    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        for trigger in ("placename_ai", "placename_ad", "placename_au"):
            conn.execute(text(f"DROP TRIGGER IF EXISTS {trigger}"))
        conn.execute(text("DROP TABLE IF EXISTS placename_fts"))
    SQLModel.metadata.drop_all(engine)
    init_db()


def build(session: Session, now: datetime, viewers_n: int = 60) -> dict:
    # --- city and neighbourhoods ------------------------------------------ #
    city = session.exec(select(City).where(City.slug == "hyderabad")).first()
    if city is None:
        city = City(slug="hyderabad", name_en="Hyderabad", state="Telangana")
    city.bbox = [17.20, 78.20, 17.62, 78.70]
    city.centre_lat, city.centre_lng = 17.3850, 78.4867
    city.regional_langs = regional_langs("Telangana")
    session.add(city)
    session.commit()
    session.refresh(city)

    # The city's own name in its scripts, for the Explore header.
    for lang, name in (
        ("te", "హైదరాబాద్"),
        ("ur", "حیدرآباد"),
        ("hi", "हैदराबाद"),
    ):
        pass  # city names live in the frontend's city list; places carry PlaceName rows

    for name, lat, lng in HYDERABAD_AREAS:
        existing = session.exec(
            select(Neighbourhood).where(
                Neighbourhood.city_id == city.id, Neighbourhood.name == name
            )
        ).first()
        if existing is None:
            session.add(Neighbourhood(city_id=int(city.id), name=name, lat=lat, lng=lng))
    # Pad out to 87 areas so the fog headline reads like the reference
    # ("12 of 87 neighbourhoods"). These are grid points, not invented names.
    existing_count = len(
        session.exec(select(Neighbourhood).where(Neighbourhood.city_id == city.id)).all()
    )
    session.commit()
    extra_needed = max(0, 87 - max(existing_count, len(HYDERABAD_AREAS)))
    for i in range(extra_needed):
        lat = 17.24 + (i % 9) * 0.042
        lng = 78.24 + (i // 9) * 0.048
        name = f"Area {i + 1:02d}"
        if session.exec(
            select(Neighbourhood).where(
                Neighbourhood.city_id == city.id, Neighbourhood.name == name
            )
        ).first() is None:
            session.add(Neighbourhood(city_id=int(city.id), name=name, lat=lat, lng=lng))
    session.commit()

    # --- users ------------------------------------------------------------- #
    users: dict[str, User] = {}
    for index, (username, display, bio, _creator) in enumerate(USERS):
        user = session.exec(select(User).where(User.username == username)).first()
        if user is None:
            user = User(
                username=username,
                email=f"{username}@demo.invalid",   # RFC 2606: cannot reach anyone
                password_hash=hash_password(PASSWORD),
            )
        user.display_name = display
        user.bio = bio
        user.demo = True
        user.home_city_id = int(city.id)
        # Accounts 40-200 days old, so Partner eligibility can be met.
        user.created_at = now - timedelta(days=200 - index * 12)
        if username == "riya_s":
            user.names_mode = "en_local"
            user.names_lang = "te"
        session.add(user)
        users[username] = user
    session.commit()
    for user in users.values():
        session.refresh(user)

    # --- places ------------------------------------------------------------ #
    places: dict[str, Place] = {}
    for spec in PLACES:
        finder = users.get(spec.get("finder", ""))
        existing = session.exec(
            select(Place)
            .join(PlaceName, PlaceName.place_id == Place.id)
            .where(PlaceName.name == spec["en"], PlaceName.lang == "en")
        ).first()
        place = existing or Place()
        place.city_id = int(city.id) if spec.get("state", "Telangana") == "Telangana" else None
        place.state = spec.get("state", "Telangana")
        place.lat, place.lng = spec["lat"], spec["lng"]
        place.category = spec["category"]
        place.area = spec.get("area", "")
        place.source = spec["source"]
        place.fame = spec["fame"]
        place.sitelinks = int(spec.get("sitelinks", 0))
        place.wikidata = spec.get("wikidata")
        place.osm_type = spec.get("osm_type")
        place.osm_id = spec.get("osm_id")
        place.status = "verified"
        place.fragile = bool(spec.get("fragile", False))
        place.added_by = int(finder.id) if finder else None
        place.description = spec["description"]
        place.activities = spec.get("activities", [])
        place.best_time = spec.get("best_time", {})
        place.entry_fee_text = spec.get("entry_fee_text", "")
        place.timings_text = spec.get("timings_text", "")
        place.access = spec.get("access", {})
        place.accessibility = spec.get("accessibility", {})
        place.safety = spec.get("safety", {})
        place.created_at = now - timedelta(days=RNG.randint(40, 220))
        place.updated_at = now
        session.add(place)
        session.commit()
        session.refresh(place)
        places[spec["en"]] = place

        name_source = {"community": "user", "osm": "osm", "wikidata": "wikidata"}[spec["source"]]
        rows = {"en": spec["en"], **spec.get("names", {})}
        for lang, name in rows.items():
            source = name_source if lang == "en" else name_source
            existing_name = session.exec(
                select(PlaceName).where(
                    PlaceName.place_id == place.id,
                    PlaceName.lang == lang,
                    PlaceName.source == source,
                )
            ).first()
            if existing_name is None:
                session.add(
                    PlaceName(
                        place_id=int(place.id),
                        lang=lang,
                        name=name,
                        source=source,
                        votes=5 if source == "user" else 0,
                    )
                )
            else:
                existing_name.name = name
                session.add(existing_name)
        session.commit()

    # --- views, likes, saves ----------------------------------------------- #
    all_users = list(users.values())
    for spec in PLACES:
        place = places[spec["en"]]
        target_viewers = int(spec.get("viewers", 20))
        target_likes = int(spec.get("likes", 5))
        # The named cast is only twelve people, so the per-place view and like
        # counts are scaled to whoever exists, preserving each place's **like
        # rate** -- which is the only part of these numbers the ranking uses
        # (SPEC §9.1). The wider audience built later raises the absolute
        # counts to something that looks like a real city.
        viewers = min(len(all_users), max(2, round(target_viewers / 10)))
        rate = target_likes / max(1, target_viewers)
        likes = max(0, min(viewers, round(rate * viewers)))

        chosen = RNG.sample(all_users, viewers)
        for i, user in enumerate(chosen):
            if place.added_by == user.id:
                continue
            if session.exec(
                select(View).where(View.user_id == user.id, View.place_id == place.id)
            ).first() is None:
                session.add(
                    View(
                        user_id=int(user.id),
                        place_id=int(place.id),
                        first_seen_at=now - timedelta(days=RNG.randint(1, 60)),
                    )
                )
            if i < likes:
                if session.exec(
                    select(Like).where(Like.user_id == user.id, Like.place_id == place.id)
                ).first() is None:
                    session.add(
                        Like(
                            user_id=int(user.id),
                            place_id=int(place.id),
                            at=now - timedelta(days=RNG.randint(1, 28)),
                        )
                    )
        session.commit()

    # Saves: Riya's "Want to go" list in the reference.
    riya = users["riya_s"]
    for name in ("Qutb Shahi Tombs", "Athirappilly Falls", "Ananthagiri Hills"):
        place = places[name]
        if session.exec(
            select(Save).where(Save.user_id == riya.id, Save.place_id == place.id)
        ).first() is None:
            session.add(Save(user_id=int(riya.id), place_id=int(place.id), at=now - timedelta(days=3)))
    session.commit()

    # --- follows ----------------------------------------------------------- #
    creators = [users[u] for u, _, _, is_creator in USERS if is_creator]
    # Riya posts too (the reference's Studio is hers), so she is followable.
    followable = creators + [users["riya_s"]]
    for user in all_users:
        for creator in followable:
            if user.id == creator.id:
                continue
            if RNG.random() < 0.6:
                if session.exec(
                    select(Follow).where(
                        Follow.follower_id == user.id, Follow.creator_id == creator.id
                    )
                ).first() is None:
                    session.add(
                        Follow(follower_id=int(user.id), creator_id=int(creator.id))
                    )
    session.commit()

    # --- last-mile steps --------------------------------------------------- #
    for spec in PLACES:
        if not spec.get("steps"):
            continue
        place = places[spec["en"]]
        author = users.get(spec.get("finder", "")) or users["rohit_walks"]
        group = f"demo-{place.id}"
        if session.exec(
            select(LastMileStep).where(LastMileStep.version_group == group)
        ).first() is None:
            for order, text in enumerate(spec["steps"], start=1):
                session.add(
                    LastMileStep(
                        place_id=int(place.id),
                        author_id=int(author.id),
                        version_group=group,
                        order=order,
                        text=text,
                        created_at=now - timedelta(days=RNG.randint(10, 90)),
                    )
                )
            session.commit()
            # Helpful votes from everyone else.
            for voter in all_users:
                if voter.id == author.id or RNG.random() > 0.55:
                    continue
                if session.exec(
                    select(LastMileVote).where(
                        LastMileVote.user_id == voter.id, LastMileVote.version_group == group
                    )
                ).first() is None:
                    session.add(
                        LastMileVote(
                            user_id=int(voter.id),
                            version_group=group,
                            helpful=RNG.random() < 0.92,
                            at=now - timedelta(days=RNG.randint(1, 30)),
                        )
                    )
            session.commit()
            kadam.award(
                session,
                int(author.id),
                kadam.STEPS_HELPFUL,
                ref_type="steps",
                ref_id=int(place.id),
                now=now - timedelta(days=5),
            )

    # --- videos ------------------------------------------------------------ #
    made_videos: list[Media] = []
    for index, (username, place_name, duration, caption, lang) in enumerate(VIDEOS):
        creator = users[username]
        place = places[place_name]
        existing = session.exec(
            select(Media).where(
                Media.user_id == creator.id, Media.place_id == place.id, Media.caption == caption
            )
        ).first()
        if existing is not None:
            made_videos.append(existing)
            continue
        poster = process_photo(illustration_photo(place.category, 1000 + index), now)
        media = Media(
            place_id=int(place.id),
            user_id=int(creator.id),
            kind="video",
            # No real video file is fabricated: the player falls back to the
            # poster, which is also the saveData behaviour (SPEC §8.3).
            path_display="",
            path_poster=poster.path_display,
            path_thumb=poster.path_thumb,
            width=1080,
            height=1920,
            duration_s=duration,
            phash=poster.phash,
            caption=caption,
            lang=lang,
            source="upload",
            shot_here=True,
            status="ok",
            created_at=now - timedelta(days=RNG.randint(2, 40)),
        )
        session.add(media)
        session.commit()
        session.refresh(media)
        made_videos.append(media)

    # --- media views (engaged views for the Studio) ------------------------ #
    for media in made_videos:
        watchers = [u for u in all_users if u.id != media.user_id]
        # Spread views over the last 28 days so the sparkline has a shape.
        for day_offset in range(28, 0, -1):
            daily = RNG.randint(1, 4) + (28 - day_offset) // 8
            for _ in range(daily):
                watcher = RNG.choice(watchers)
                started = now - timedelta(days=day_offset, hours=RNG.randint(0, 23))
                watched = min(media.duration_s, max(0.5, RNG.gauss(media.duration_s * 0.7, 6)))
                session.add(
                    MediaView(
                        user_id=int(watcher.id),
                        media_id=int(media.id),
                        started_at=started,
                        watched_s=round(watched, 1),
                        engaged=watched >= 3.0,
                        completed=watched >= 0.9 * media.duration_s,
                        invalid_reason=None,
                    )
                )
                # An engaged view is a touch that may later earn a visit.
                if watched >= 3.0:
                    session.add(
                        Touch(
                            user_id=int(watcher.id),
                            place_id=int(media.place_id),
                            creator_id=int(media.user_id),
                            content_type="video",
                            content_id=int(media.id),
                            at=started,
                        )
                    )
            if day_offset % 7 == 0:
                session.commit()
        session.commit()

        for liker in RNG.sample(watchers, min(len(watchers), RNG.randint(4, 9))):
            if session.exec(
                select(MediaLike).where(
                    MediaLike.user_id == liker.id, MediaLike.media_id == media.id
                )
            ).first() is None:
                session.add(MediaLike(user_id=int(liker.id), media_id=int(media.id)))
        session.commit()

    # --- place-page touches ------------------------------------------------ #
    for spec in PLACES:
        place = places[spec["en"]]
        if place.added_by is None:
            continue
        for user in all_users:
            if user.id == place.added_by or RNG.random() > 0.5:
                continue
            session.add(
                Touch(
                    user_id=int(user.id),
                    place_id=int(place.id),
                    creator_id=int(place.added_by),
                    content_type="place",
                    at=now - timedelta(days=RNG.randint(1, 25)),
                )
            )
    session.commit()

    # --- visits, attribution, kadam ---------------------------------------- #
    visit_count = 0
    # Riya is the account the demo signs in as, and she gets a deliberate set of
    # visits below (her streak and her stamps). She is kept out of the random
    # pass so that some places stay unvisited -- otherwise her Nearby deck would
    # correctly, but unhelpfully, be empty on the first run.
    random_visitors = [u for u in all_users if u.username != "riya_s"]
    for spec in PLACES:
        place = places[spec["en"]]
        visitors = RNG.sample(random_visitors, RNG.randint(4, min(9, len(random_visitors))))
        for user in visitors:
            if user.id == place.added_by:
                continue
            at = now - timedelta(days=RNG.randint(1, 45), hours=RNG.randint(0, 20))
            existing = session.exec(
                select(Visit).where(
                    Visit.user_id == user.id, Visit.place_id == place.id
                )
            ).first()
            if existing is not None:
                continue
            visit = Visit(
                user_id=int(user.id),
                place_id=int(place.id),
                at=at,
                distance_m=RNG.uniform(5, 120),
                accuracy_m=RNG.uniform(6, 40),
                verified=True,
                flag=None,
                simulated=False,
            )
            session.add(visit)
            session.commit()
            session.refresh(visit)
            visit_count += 1

            kadam.award(
                session, int(user.id), kadam.OWN_VISIT,
                ref_type="place", ref_id=int(place.id), now=at,
            )

            touches = [
                TouchRow(creator_id=int(t.creator_id), at=t.at, content_type=t.content_type)
                for t in session.exec(
                    select(Touch).where(
                        Touch.user_id == user.id, Touch.place_id == place.id, Touch.at <= at
                    )
                ).all()
            ]
            shares = attribute(touches, int(user.id), at)
            for creator_id, share in shares.items():
                session.add(
                    Attribution(visit_id=int(visit.id), creator_id=int(creator_id), share=share)
                )
                whole = int(round(share))
                if whole > 0:
                    kadam.award(
                        session, int(creator_id), kadam.VISIT_CAUSED,
                        ref_type="place", ref_id=int(place.id),
                        amount=10 * whole, now=at,
                    )
            session.commit()

        # Discovery kadam for community places that reached verified.
        if place.added_by and place.source == "community":
            kadam.award(
                session, int(place.added_by), kadam.DISCOVERY,
                ref_type="place", ref_id=int(place.id),
                now=place.created_at + timedelta(days=4),
            )

    # Riya's weekly streak: one verified visit a week for the last 6 weeks, to
    # six named places, leaving the rest for her deck.
    streak_places = [
        "Khajaguda Rocks",
        "Golconda Fort",
        "Durgam Cheruvu",
        "Bansilalpet Stepwell",
        "Hussain Sagar",
        "Sunset ridge",
    ]
    for week, place_name in enumerate(streak_places):
        place = places[place_name]
        at = now - timedelta(days=week * 7 + 1)
        if session.exec(
            select(Visit).where(Visit.user_id == riya.id, Visit.place_id == place.id)
        ).first() is None:
            session.add(
                Visit(
                    user_id=int(riya.id), place_id=int(place.id), at=at,
                    distance_m=40.0, accuracy_m=12.0, verified=True, simulated=False,
                )
            )
    session.commit()

    # --- Pulse reports ----------------------------------------------------- #
    for place_name, username, hours_ago, fields, note in PULSES:
        place = places[place_name]
        user = users[username]
        at = now - timedelta(hours=hours_ago)
        existing = session.exec(
            select(Pulse).where(Pulse.place_id == place.id, Pulse.user_id == user.id)
        ).first()
        if existing is not None:
            continue
        # Pulse needs a verified visit in the last 2 h; give it one.
        visit = Visit(
            user_id=int(user.id), place_id=int(place.id),
            at=at - timedelta(minutes=20),
            distance_m=30.0, accuracy_m=10.0, verified=True, simulated=False,
        )
        session.add(visit)
        session.commit()
        session.refresh(visit)
        session.add(
            Pulse(
                place_id=int(place.id), user_id=int(user.id), at=at,
                water=fields.get("water"), crowd=fields.get("crowd"),
                path=fields.get("path"), open=fields.get("open"),
                note=note, visit_id=int(visit.id),
            )
        )
        kadam.award(
            session, int(user.id), kadam.PULSE,
            ref_type="place", ref_id=int(place.id), now=at,
        )
    session.commit()

    # A second report at Athirappilly, so the first one counts as "confirmed"
    # for the Partner score (SPEC §10.3).
    falls = places["Athirappilly Falls"]
    confirmer = users["arjun_t"]
    if session.exec(
        select(Pulse).where(Pulse.place_id == falls.id, Pulse.user_id == confirmer.id)
    ).first() is None:
        at = now - timedelta(hours=2)
        visit = Visit(
            user_id=int(confirmer.id), place_id=int(falls.id), at=at - timedelta(minutes=30),
            distance_m=25.0, accuracy_m=9.0, verified=True, simulated=False,
        )
        session.add(visit)
        session.commit()
        session.refresh(visit)
        session.add(
            Pulse(
                place_id=int(falls.id), user_id=int(confirmer.id), at=at,
                water="flowing", crowd="busy", open="yes",
                note="Still flowing hard.", visit_id=int(visit.id),
            )
        )
        session.commit()

    # --- category preferences, so the deck has something to learn from ----- #
    for user in all_users:
        for category in ("viewpoint", "waterfall", "lake", "fort_heritage", "hill_trek"):
            pref = session.exec(
                select(CategoryPref).where(
                    CategoryPref.user_id == user.id, CategoryPref.category == category
                )
            ).first()
            if pref is None:
                pref = CategoryPref(user_id=int(user.id), category=category)
            pref.alpha = 1.0 + RNG.randint(0, 6)
            pref.beta = 1.0 + RNG.randint(0, 4)
            session.add(pref)
    session.commit()

    extra = {}
    if viewers_n > 0:
        extra = build_audience(session, city, places, creators, made_videos, now, viewers_n)

    rebuild_fts()

    return {
        "city": city.slug,
        "users": len(session.exec(select(User)).all()),
        "creators": len(creators),
        "places": len(places),
        "videos": len(session.exec(select(Media).where(Media.kind == "video")).all()),
        "visits": visit_count + extra.get("visits", 0),
        "neighbourhoods": len(
            session.exec(select(Neighbourhood).where(Neighbourhood.city_id == city.id)).all()
        ),
        **{f"audience_{k}": v for k, v in extra.items()},
    }


def build_audience(
    session: Session,
    city: City,
    places: dict[str, Place],
    creators: list[User],
    videos: list[Media],
    now: datetime,
    viewers_n: int = 60,
) -> dict:
    """An audience large enough for the Partner Program to mean something.

    The twelve named demo users are the cast of the design reference. The
    Partner thresholds (SPEC §10.4) are deliberately set where fake accounts
    cannot farm them, so demonstrating a real monthly split needs a realistic
    crowd behind them: ~60 viewers, enough videos per creator to clear the
    verified-content bar, and attributed visits spread over 90 days.

    These accounts are flagged `demo = True` and the report says every count
    here is fabricated.
    """
    # --- more videos, so each creator clears 10 pieces of verified content -- #
    place_cycle = [p for name, p in places.items() if not p.fragile]
    new_videos = 0
    # Riya is the user the reference's Passport and Studio screens belong to,
    # and that Studio shows 14 verified items, so she gets content as well.
    riya = session.exec(select(User).where(User.username == "riya_s")).first()
    posting_users = list(creators) + ([riya] if riya is not None else [])
    for creator in posting_users:
        have = len(
            session.exec(
                select(Media).where(
                    Media.user_id == creator.id, Media.kind == "video", Media.status == "ok"
                )
            ).all()
        )
        for i in range(max(0, 11 - have)):
            place = place_cycle[(int(creator.id) + i) % len(place_cycle)]
            caption = f"{place.area or 'On the way'}: part {i + 1} of the walk in."
            if session.exec(
                select(Media).where(Media.user_id == creator.id, Media.caption == caption)
            ).first() is not None:
                continue
            poster = process_photo(illustration_photo(place.category, 7000 + int(creator.id) * 20 + i), now)
            media = Media(
                place_id=int(place.id),
                user_id=int(creator.id),
                kind="video",
                path_display="",
                path_poster=poster.path_display,
                path_thumb=poster.path_thumb,
                width=1080,
                height=1920,
                duration_s=float(RNG.randint(14, 58)),
                phash=poster.phash,
                caption=caption,
                lang="en",
                source="upload",
                shot_here=True,
                status="ok",
                created_at=now - timedelta(days=RNG.randint(5, 85)),
            )
            session.add(media)
            new_videos += 1
        session.commit()

    all_videos = list(
        session.exec(select(Media).where(Media.kind == "video", Media.status == "ok")).all()
    )

    # --- the crowd ---------------------------------------------------------- #
    viewers: list[User] = []
    for i in range(viewers_n):
        username = f"viewer_{i:03d}"
        user = session.exec(select(User).where(User.username == username)).first()
        if user is None:
            user = User(
                username=username,
                email=f"{username}@demo.invalid",
                password_hash=hash_password(PASSWORD),
                display_name=f"Viewer {i:03d}",
                demo=True,
                home_city_id=int(city.id),
                created_at=now - timedelta(days=RNG.randint(45, 300)),
                names_mode=RNG.choice(["en_local", "en_local", "mine_local", "en"]),
                names_lang=RNG.choice(["te", "hi", "ta", "ml", "en"]),
            )
            session.add(user)
            viewers.append(user)
        else:
            viewers.append(user)
    session.commit()
    for user in viewers:
        session.refresh(user)

    # --- follows from the wider audience ----------------------------------- #
    posting = [u for u in posting_users if u is not None]
    for viewer in viewers:
        for creator in posting:
            if RNG.random() > 0.55:
                continue
            if session.exec(
                select(Follow.id).where(
                    Follow.follower_id == viewer.id, Follow.creator_id == creator.id
                ).limit(1)
            ).first() is None:
                session.add(Follow(follower_id=int(viewer.id), creator_id=int(creator.id)))
    session.commit()

    # --- engaged views over 90 days ---------------------------------------- #
    view_rows = 0
    for media in all_videos:
        audience = [v for v in viewers if v.id != media.user_id]
        # 120 days, not 90: a monthly Partner run measures the 90 days up to
        # the *month end*, so the data has to extend past today for any window
        # inside it to be full.
        for day_offset in range(120, 0, -1):
            # A gentle upward trend, so the Studio sparkline rises like the
            # reference screen.
            daily = RNG.randint(0, 2) + (120 - day_offset) // 40
            for _ in range(daily):
                watcher = RNG.choice(audience)
                started = now - timedelta(days=day_offset, hours=RNG.randint(0, 23), minutes=RNG.randint(0, 59))
                watched = min(media.duration_s, max(0.5, RNG.gauss(media.duration_s * 0.68, 7)))
                session.add(
                    MediaView(
                        user_id=int(watcher.id),
                        media_id=int(media.id),
                        started_at=started,
                        watched_s=round(watched, 1),
                        engaged=watched >= 3.0,
                        completed=watched >= 0.9 * media.duration_s,
                        invalid_reason=None,
                    )
                )
                view_rows += 1
                if watched >= 3.0 and RNG.random() < 0.5:
                    session.add(
                        Touch(
                            user_id=int(watcher.id),
                            place_id=int(media.place_id),
                            creator_id=int(media.user_id),
                            content_type="video",
                            content_id=int(media.id),
                            at=started,
                        )
                    )
        session.commit()

    # --- attributed visits -------------------------------------------------- #
    visit_rows = 0
    visitable = [p for p in place_cycle]
    # Spread roughly (viewers x places x 0.8) first visits over 90 days, so a
    # larger audience produces proportionally more attributed visits.
    per_day = max(3, int(len(viewers) * len(visitable) * 0.8 / 120))
    for day_offset in range(119, 0, -1):
        for _ in range(per_day):
            visitor = RNG.choice(viewers)
            place = RNG.choice(visitable)
            if place.added_by == visitor.id:
                continue
            at = now - timedelta(days=day_offset, hours=RNG.randint(6, 20))
            if session.exec(
                select(Visit).where(Visit.user_id == visitor.id, Visit.place_id == place.id)
            ).first() is not None:
                continue

            # Most visits happen because the visitor saw something about the
            # place first -- that is the premise the Partner Program rests on.
            # About a fifth are left with no touch at all, so the data also
            # contains organic visits, which attribute to nobody (SPEC §9.9).
            has_touch = session.exec(
                select(Touch.id).where(
                    Touch.user_id == visitor.id, Touch.place_id == place.id, Touch.at <= at
                ).limit(1)
            ).first()
            if has_touch is None and RNG.random() < 0.8:
                about_this_place = [
                    int(m.user_id)
                    for m in all_videos
                    if m.place_id == place.id and m.user_id
                ]
                if place.added_by:
                    about_this_place.append(int(place.added_by))
                candidates = [c for c in about_this_place if c != int(visitor.id)]
                if candidates:
                    session.add(
                        Touch(
                            user_id=int(visitor.id),
                            place_id=int(place.id),
                            creator_id=RNG.choice(candidates),
                            content_type=RNG.choice(["video", "place", "steps"]),
                            at=at - timedelta(days=RNG.uniform(0.2, 9.0)),
                        )
                    )
                    session.commit()
            visit = Visit(
                user_id=int(visitor.id),
                place_id=int(place.id),
                at=at,
                distance_m=RNG.uniform(5, 140),
                accuracy_m=RNG.uniform(6, 60),
                verified=True,
                flag=None,
                simulated=False,
            )
            session.add(visit)
            session.commit()
            session.refresh(visit)
            visit_rows += 1

            touches = [
                TouchRow(creator_id=int(t.creator_id), at=t.at, content_type=t.content_type)
                for t in session.exec(
                    select(Touch).where(
                        Touch.user_id == visitor.id,
                        Touch.place_id == place.id,
                        Touch.at <= at,
                    )
                ).all()
            ]
            shares = attribute(touches, int(visitor.id), at)
            for creator_id, share in shares.items():
                session.add(
                    Attribution(visit_id=int(visit.id), creator_id=int(creator_id), share=share)
                )
            if not shares:
                continue
        session.commit()

    # The big audience exists, so bring every place's view and like counts up to
    # the scale the design reference shows, keeping each place's like rate.
    scale_likes_and_views(session, places, viewers, now)

    top_up = top_up_reach(session, viewers, place_cycle, all_videos, now)

    return {
        "viewers": len(viewers),
        "videos": new_videos,
        "views": view_rows,
        "visits": visit_rows + top_up["visits"],
        "reach": top_up["reach"],
    }


def scale_likes_and_views(
    session: Session,
    places: dict[str, Place],
    viewers: list[User],
    now: datetime,
) -> None:
    """Raise view and like counts to the audience's size, keeping like rates.

    The counts in the design reference (9,812 hearts on Golconda) imply a city's
    worth of users. We have a few hundred, so each place gets as many viewers as
    the audience allows and keeps the **ratio** from its spec entry -- the ratio
    is what Wilson's bound reads, so the Top ordering comes out as intended
    while the absolute numbers stay honest about how many accounts exist.
    """
    pool = list(viewers)
    if not pool:
        return
    biggest = max(int(p.get("viewers", 1)) for p in PLACES) or 1

    for spec in PLACES:
        place = places[spec["en"]]
        rate = int(spec.get("likes", 0)) / max(1, int(spec.get("viewers", 1)))
        want_viewers = max(
            2, min(len(pool), round(len(pool) * int(spec["viewers"]) / biggest))
        )
        chosen = RNG.sample(pool, want_viewers)
        want_likes = round(rate * want_viewers)

        for index, user in enumerate(chosen):
            if place.added_by == user.id:
                continue
            if session.exec(
                select(View.id).where(View.user_id == user.id, View.place_id == place.id).limit(1)
            ).first() is None:
                session.add(
                    View(
                        user_id=int(user.id),
                        place_id=int(place.id),
                        first_seen_at=now - timedelta(days=RNG.randint(1, 90)),
                    )
                )
            if index < want_likes:
                if session.exec(
                    select(Like.id)
                    .where(Like.user_id == user.id, Like.place_id == place.id)
                    .limit(1)
                ).first() is None:
                    session.add(
                        Like(
                            user_id=int(user.id),
                            place_id=int(place.id),
                            at=now - timedelta(days=RNG.randint(1, 28)),
                        )
                    )
        session.commit()


# Visits caused, in the 90 days a monthly run measures, that the demo aims for.
# Riya is deliberately left just short of the 300 threshold, because that is the
# state the design reference's Studio screen shows ("3 of 4 done", 214 / 300).
# The three creators clear it, so the monthly split actually pays someone and
# the viva can show both sides of the rule.
REACH_TARGETS = {
    "meera_k": 352,
    "rohit_walks": 341,
    "keralawanders": 318,
    "riya_s": 214,
}


def top_up_reach(
    session: Session,
    viewers: list[User],
    places: list[Place],
    videos: list[Media],
    now: datetime,
) -> dict:
    """Add attributed visits until each creator hits its REACH_TARGETS figure.

    The random pass above produces a realistic but uncontrolled spread; the
    Partner thresholds are high on purpose (SPEC §10.6), so hitting a specific
    side of them takes a deliberate pass. Each visit added here has exactly one
    touch, so it contributes a share of exactly 1.0 and the arithmetic is
    checkable by hand.
    """
    from app.partner.run import month_bounds

    _, month_end = month_bounds(f"{now:%Y-%m}")
    window_start = month_end - timedelta(days=90)
    # Keep the new visits inside the window and in the past.
    latest = min(now, month_end) - timedelta(hours=2)

    added = 0
    reach: dict[str, float] = {}

    for username, target in REACH_TARGETS.items():
        creator = session.exec(select(User).where(User.username == username)).first()
        if creator is None:
            continue
        cid = int(creator.id)

        current = float(
            session.exec(
                select(func.coalesce(func.sum(Attribution.share), 0.0))
                .join(Visit, Visit.id == Attribution.visit_id)
                .where(
                    Attribution.creator_id == cid,
                    Visit.at >= window_start,
                    Visit.at <= month_end,
                    Visit.verified == True,  # noqa: E712
                    Visit.flag == None,  # noqa: E711
                    Visit.simulated == False,  # noqa: E712
                )
            ).one()
            or 0.0
        )

        # Places this creator actually has content about: a visit they caused
        # has to be to somewhere they posted about.
        their_places = [
            p for p in places if p.added_by == cid or any(m.place_id == p.id and m.user_id == cid for m in videos)
        ] or places

        needed = int(target - round(current))
        for _ in range(max(0, needed)):
            placed = False
            for _attempt in range(40):
                visitor = RNG.choice(viewers)
                place = RNG.choice(their_places)
                if int(visitor.id) == cid or place.added_by == visitor.id:
                    continue
                if session.exec(
                    select(Visit.id).where(
                        Visit.user_id == visitor.id, Visit.place_id == place.id
                    ).limit(1)
                ).first() is not None:
                    continue

                at = latest - timedelta(days=RNG.uniform(0.5, 86.0), hours=RNG.randint(0, 12))
                if at < window_start:
                    continue
                session.add(
                    Touch(
                        user_id=int(visitor.id),
                        place_id=int(place.id),
                        creator_id=cid,
                        content_type=RNG.choice(["video", "place", "steps"]),
                        at=at - timedelta(days=RNG.uniform(0.2, 6.0)),
                    )
                )
                visit = Visit(
                    user_id=int(visitor.id),
                    place_id=int(place.id),
                    at=at,
                    distance_m=RNG.uniform(5, 130),
                    accuracy_m=RNG.uniform(6, 55),
                    verified=True,
                    flag=None,
                    simulated=False,
                )
                session.add(visit)
                session.commit()
                session.refresh(visit)
                session.add(
                    Attribution(visit_id=int(visit.id), creator_id=cid, share=1.0)
                )
                added += 1
                current += 1.0
                placed = True
                break
            if not placed:
                break          # ran out of unused (viewer, place) pairs
        session.commit()
        reach[username] = round(current, 1)

    return {"visits": added, "reach": reach}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic demo data")
    parser.add_argument("--reset", action="store_true", help="wipe the database first")
    parser.add_argument("--month", default=None, help="also run the Partner month, e.g. 2026-10")
    parser.add_argument("--small", action="store_true",
                        help="just the 12 named users, no wider audience")
    parser.add_argument("--viewers", type=int, default=60,
                        help="size of the demo audience; 220+ makes a creator "
                             "clear the Partner thresholds so the split can be shown live")
    args = parser.parse_args()

    init_db()
    if args.reset:
        print("Wiping the database...")
        reset()
    now = utcnow()
    with Session(engine) as session:
        summary = build(session, now, viewers_n=0 if args.small else args.viewers)
        print("\nDemo data built:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
        print(f"\nEvery demo account's password is: {PASSWORD!r}")
        print("Sign in as riya_s to see the Passport and Studio from the reference.")

        if args.month:
            from app.partner.run import run_month

            print(f"\nRunning the Partner month {args.month} (simulated pool)...")
            result = run_month(session, args.month)
            print(f"  pool: Rs {result['pool_paise'] / 100:,.2f} (simulated)")
            print(f"  creators: {result['creators']}, eligible: {result['eligible_creators']}")
            for line in result["lines"][:5]:
                print(
                    f"    creator {line['creator_id']}: score {line['score']}, "
                    f"Rs {line['amount_paise'] / 100:,.2f}"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
