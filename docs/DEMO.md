# DEMO.md — 6-minute live demo

## Script (click → say)

| # | Time | Click | Say |
|---|---|---|---|
| 1 | 0:00 | Title slide / Nearby | "Every city has places big maps don't know. Truvel is where locals share them and visitors find them." |
| 2 | 0:30 | Nearby: swipe 3 cards, use the Save button once | "The deck learns what you like: each category keeps a Beta distribution and we *draw* from it, so it still explores — Thompson sampling." |
| 3 | 1:00 | Watch: play one video, tap **Go here** | "Short videos of places, each with a way to go there." |
| 4 | 1:20 | Place page: Pulse, last-mile steps, Safety card | "Live conditions, steps written by people who went, and a safety card that is never hidden." |
| 5 | 1:50 | Settings → names in Tamil, then Hindi; back to a place | "Names in 22 Indian languages, in the right script and font." |
| 6 | 2:20 | Explore: **Top** vs **Most liked** | "One like from one person isn't 100 %. Wilson's lower bound ranks by how sure we are." |
| 7 | 2:50 | Open the place you added on site (A3) | "Added by me, standing there. It became verified only when two other people visited." |
| 8 | 3:20 | Nearby → dev simulator → check in | "Your location is used for this one request and never stored. Only distance and accuracy are kept." |
| 9 | 3:50 | You → Passport: fog cleared, stamp | "Check-ins clear the fog on your city map." |
| 10 | 4:20 | You → Studio | "Creators are credited for visits they caused, by time-decay attribution. The money is a **simulated** pool, and it says so everywhere." |
| 11 | 5:00 | `results/attribution/latest/figure.svg` | "Time-decay is best or near-best whatever the true decay; ρ = 0.864." |
| 12 | 5:30 | Limitations slide | "These are simulations, not user studies; one deep city; GPS can be spoofed; the pool is simulated." |

## What can fail, and the fallback

| Failure | Fallback |
|---|---|
| Wi-Fi down | Everything runs on localhost; map tiles cached by browsing the map once before; else show the recording |
| Map tiles blank | Switch to Explore List; mention tiles come from OpenFreeMap |
| Geolocation refused | Use the dev simulator (that is what step 8 uses anyway) |
| Video won't play | Use the poster and move on; the recording shows playback |
| Backend crash | `uvicorn app.main:app --port 8000` again (≈ 5 s); keep the terminal open |
| Laptop dies | Recording on phone + USB stick |

## Pre-demo checklist (30 min before)

- [ ] `$env:DEV_ALLOW_FAKE_LOCATION=1`; `VITE_DEV_TOOLS=1` in `frontend/.env.development.local`
- [ ] Backend and frontend running; log in as the demo account
- [ ] Browse Explore Map once (tile cache); open the step-7 place once (photo cache)
- [ ] Studio shows numbers (`python -m scripts.demo_data` then run the Partner month if empty)
- [ ] Settings back to English; light theme; browser zoom 100 %; notifications off
- [ ] Tabs ready: app, `attribution/latest/figure.svg`, limitations slide
- [ ] Recording file open in a second window
