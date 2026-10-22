# How Truvel could earn money

Today no real money moves. The Partner Program splits a **simulated** pool
(`partner.demo_pool_inr`) and every ₹ figure is labelled so. This note is the
route from that to a real business, in the order it is safe to do each step.

## What people would pay for

| Who pays | For what | Why it fits |
|---|---|---|
| **Tourism boards and city governments** | A verified "Discover <district>" partnership: featured hidden places, seasonal trails, visit counts they can report | They already budget for destination marketing and want footfall *outside* the famous five places. Truvel measures exactly that (check-ins are verified, not clicks). |
| **Local businesses near a place** (homestays, cafes, guides, rentals) | A listing that appears on the place page under "Nearby" | Paid by the business, never ranked into the main lists, always labelled "Sponsored". |
| **Travellers** | Truvel Plus: offline city packs, unlimited saved trails, trip planning | Needs the PWA/offline work (Tier 2). Free tier stays fully usable. |

## What would not be sold

- Rank. A place never pays to be higher in Top, Hidden gems or the deck.
- Data about individuals. Truvel does not store location, so there is none.
- Access to fragile places. Their exact pin stays behind the pledge.

## The creator pool

The Partner Program in this version pays out of a **simulated** pool by *visits a
creator caused*. It becomes real only when there is real income to share:

1. Revenue arrives from the rows above.
2. A fixed share (the plan is ~50%) goes to the monthly pool.
3. `partner.run_month()` splits it exactly as it does now, and payouts go
   through a payment processor, not through the app's own balances.

Steps 2 and 3 need a registered business, a bank account, KYC for creators,
TDS/GST handling and a payments partner. None of that is possible at zero
budget or as a student project, which is why the app says "Simulated" everywhere.

## Order of work

1. Launch free, grow places + verified visits (the data is the asset).
2. Sell one tourism-board pilot using the visit counts from step 1.
3. Add business listings.
4. Only then turn the simulated pool into a real one.
