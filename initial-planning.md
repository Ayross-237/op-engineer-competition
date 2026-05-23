# Initial Planning — Padea Operations Engineer Competition

## The business
Padea runs weekly after-hours tutoring at 7 schools. Each session has a catered dinner — one boxed meal per student. A program coordinator currently emails each caterer every Thursday for the following week's meals, guessing items and quantities off each caterer's menu. Students complain about meal fit; food quality drifts down over time; the coordinator's manual ordering is the bottleneck.

## What's in the data (week of 1–4 May 2026)
- **4 caterers** ([caterers.xlsx](resources/caterers.xlsx)) — each with region and a tiered MOQ that depends on how many distinct menu items are picked (4/5/6 items) and applies *across all that caterer's schools for the week*, not per session.
- **Caterer contacts** ([caterer-contacts.pdf](resources/caterer-contacts.pdf)) — main order contact + chef per caterer, plus a "Serves" vs "Able to serve" split (current allocation vs flex capacity). CC rules differ per caterer (Terrific's chef doesn't want CC; GyG's chef does).
- **Menus** ([caterer-menus.pdf](resources/caterer-menus.pdf)) — prices, delivery fees structured very differently ($0 / $30 per school / $10 per school / $50 flat), GF/DF/NF/VO tags, plus the rule "non-pork = halal".
- **11 sessions** ([sessions.xlsx](resources/sessions.xlsx)) across the week, each with on-site manager + mobile, dinner time, building, and year-levels attending.
- **320 students** across 11 day-specific rosters in [students.xlsx](resources/students.xlsx) — same school on different days = different students. Dietary is a free-text field.
- **Absences** ([absences.pdf](resources/absences.pdf)) — named students out on specific dates.
- **Exclusions** ([exclusions.pdf](resources/exclusions.pdf)) — three one-off cancellations, one of which is *partial* by year level (CHAC May 3: Y12 & Y10 out, Y11 in).

## Edge cases I'd flag as material
1. **Same school, different days = different student rosters** (JPC Tue vs Wed, ISHS Mon/Tue/Thu) — the natural session key is school+day, not school.
2. **Partial year-level cancellation** — must filter the roster by year-level for that date.
3. **"Opted out of Catering"** as a dietary value — student stays enrolled but is removed from the headcount.
4. **Free-text dietary field needs normalising** — values include `Halal`, `Vegetarian`, `Nut Free`, `No Beef, No Pork`, `Gluten Free, Dairy Free`, `Nut Free, No Shellfish, Opted out of Catering` (combined). Needs mapping to menu tags + domain rules (halal → any non-pork item satisfies).
5. **"Vegetarian Option" tag ≠ vegetarian by default** — it means the caterer *can* prepare it vegetarian, so an order for a VO dish for a vegetarian student needs an explicit instruction.
6. **MOQ table only covers 4/5/6 items** — what if you'd optimise to 3? Constraint on minimum variety.
7. **Cross-school MOQ coupling** — Terrific Noodles' MOQ is summed across JPC-Tue + JPC-Wed + MSHS; you can't optimise each session in isolation.
8. **Delivery-fee structures invert the optimiser** — for Terrific you want fewer schools per week; for GyG it's a flat $50 regardless of how many schools.
9. **One-off manager substitution** — ISHS Thursday has Ethan instead of usual Lucian; the caterer needs that day's contact, not the default.
10. **Suspect contact data** — GyG's "Medium Giraffe (chef – wants to be cc'ed)" email is `dylan@padea.com.au` (Padea's own coordinator). Either a deliberate trap or real; either way worth flagging on import.
11. **Name collisions** — "Sophie Turner" appears at two schools; "Charlie Morris" is both a student and a parent name. Don't key by name.
12. **The stated hint** — "the goal is not just that meals are ordered and delivered" → the system also needs to capture feedback, monitor caterer-quality drift, and use it to inform the *next* week's meal choices and caterer allocations (the "Able to serve" list is the rotation lever).

## What the system needs to do, end-to-end
Order ← (rosters − absences − opt-outs − year-level exclusions) × dietary fit × menu × MOQ × delivery cost → email to right caterer with right CCs every Thursday → day-of contact info shared with caterer for that session's manager → post-session feedback captured per student × meal × caterer → fed back into next week's selection + caterer-quality score (triggering rotation via the "Able to serve" capacity when a caterer declines).
