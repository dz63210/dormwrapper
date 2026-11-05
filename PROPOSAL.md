# DormWrapper
Group members: Lingkai Shen, Doreen Zheng, Khuslen Khosbayar, Palak Katiyar

## What it does

Users provide a few inputs and DormWrapper returns IKEA furniture recommendations that match their space, budget, and style.

**User inputs:**

- The dimensions of their room
- Their budget for furnishing the entire room
- The aesthetic they want to go for (if they don't have a clear aesthetic in mind, they can instead pick a color scheme they like)

**What the site does:**

- Generates recommendations for items that match the user's description and goals while staying within budget
- Lets users favorite items they like so they can start accumulating a list of items they could potentially purchase.

## Who it's for

All students moving into a new dorm or apartment (especially timely right now) who want to curate an aesthetic space for themselves while staying on budget.

## Data source

**The catalog: a public IKEA US product dataset (~30,000 items, scraped July 2025, from Hugging Face).**
Each record already has a name, product category, price, a product photo, and a
product link. 

IKEA also fits the audience as it is a popular furniture store among students for a dorm on a
budget so keeping the catalog to one source keeps the project narrow.

The ingest step fetches the dataset from its source and loads it into the app's
own database (SQLite). We then enrich each item with two fields the raw data
doesn't include:

- **style tags** (scandinavian, minimalist, modern, industrial, mid-century, boho, traditional), and
- **dominant color**, generated once by an LLM pass over each item's name and description, then cached
in the database.

**The app's own data:** every time a user generates a room or favorites an item,
that gets stored too (favorites, generated rooms, the inputs behind them). This
is the dynamic data the analysis component mainly runs on.

We are not scraping Amazon, Temu, or Wayfair — their terms of service and
anti-bot measures make that infeasible within the project timeline.

## Data analysis
- **Priority 1 — Product Recommendation:** given a room photo, a budget and an aesthetic, recommend IKEA items that fit the budget and match the style, and show them on the space.
- **Priority 2 — Leaderboard (optional for MVP):** most popular color, category, style, and specific items, ranked by the number of favorites an item has from our users.
- **Priority 3 (optional for MVP):** user data retention and aggregation for improved user experience. the web app will take into account the items favorited by users to improve our top recommendations. 

## Questions it answers

- Which items look good in your room *and* matches the vibe you're going for?

## For tomorrow

- Create product specs and more detail on the user experience / web app experience
