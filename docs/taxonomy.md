# Taxonomy

**One taxonomy: 28 tags across the 46 kept posts.** Categories are gone, merged into tags.

Before this, the site carried both, and the distinction had collapsed. Five names —
`mtg`, `oldschool`, `vintage`, `middle school`, `food snob` — were used as *both* a tag and
a category, and in every case the tag was strictly redundant: all 18 posts tagged `mtg`
were also categorised `mtg`, 12/12 for `oldschool`, 10/10 for `vintage`, 4/4 and 3/3 for
the rest. A post showed "mtg, oldschool" under its title and then "mtg oldschool combo"
again at its foot.

Meanwhile tags were patchy. Every post had a category; **15 of 46 had no tags at all**,
including `ospb2019` and `summer-derby-2020`.

Merging fixed both. Each post's tags became the union of its old tags and categories, so
nothing was lost and every post now carries at least one tag. `mtg` went from a tag on 18
posts to a tag on 38 — which is what it always was as a category.

## The 28

| | |
|---|---|
| formats | `mtg` 38 · `oldschool` 16 · `vintage` 15 · `middle school` 6 |
| community, events | `eternal central` 9 · `tsl` 3 · `tsi` 2 · `tso` 2 · `team serious` 2 · `mtgunderground` 2 · `2020.1` 2 |
| archetypes | `combo` 8 · `workshop` 3 · `lich` 3 · `dragon` 3 · `prison` 2 · `black dragon` 2 · `romancing the stones` 2 |
| the pre-Magic blog | `sound` 3 · `theState` 3 · `media` 2 · `web` 1 · `image` 1 |
| places, kinds | `washington d.c.` 2 · `philadelphia` 2 · `food snob` 3 · `review` 2 · `report` 2 |

The last two rows are the tail the merge produced: the old blog's sections were
category-only, so they are now thin tags. That is honest — those nine non-Magic posts
exist — but it is why the list has single-post entries.

## Merges applied first

Before the categories were folded in, 33 tags were consolidated to 23. Synonyms and
abbreviations only, and checked by co-occurrence so each was lossless:

| merged away | into | why |
|---|---|---|
| `magic` | `mtg` | synonym (added `mtg` to two Magic posts that lacked it) |
| `mtgoldschool`, `9394` | `oldschool` | synonym; 93/94 *is* the old-school format |
| `vintagemtg` | `vintage` | synonym |
| `middleschoolmtg`, `ms` | `middle school` | synonym, abbreviation |
| `tsl:vintage`, `invintage` | `tsl` | same three posts; the colon also made an ugly slug |
| `Food Blog`, `Food` | `food snob` | same three posts; also the only capitalised tags |
| `ec` | `eternal central` | two letters mean nothing on a public tag list |

Kept despite merging being lossless: `mtgunderground` is a venue, `2020.1` is a league
season, and a restaurant `review` is not a tournament `report`. Narrow is not redundant.

## What changed in the theme

- Nav is **Home · Posts · Tags · Search**. `/categories/` is deleted.
- A post's title bar is **just the date**. The category line duplicated the tag chips at
  the foot of the post, and after the merge there were no categories to show.
- Home cards still carry their accent label, now taken from the first tag.
- A post's tags link to their section on `/tags/`, which emits
  `<h2 id="{{ name | slugify }}">` for every entry. They were inert text before.
- `_config.yml`'s defaults no longer carry `include_on_search`, `include_on_feed`,
  `show_date`, `show_tags`, `show_categories` or `show_breadcrumb`. Those were chulapa's
  switches; nothing in this theme reads them.

Adding the tag links exposed a bug that predated them: **every category link on every post
was broken** — 89 of them, pointing at `/categories-mtg` instead of `/categories/#mtg`,
because `slugify` had been applied to the whole URL string and ate the slash and hash with
it. `script/check-internal-links.py` now guards every site-relative href and `#anchor` in
both `build-check.yml` and `deploy-pages.yml`.

## Decided: no redirects for the old category archives

WordPress ran with an empty `category_base`, so the live site serves category archives at
`/category/mtg/` and the like. Those are **deliberately not redirected**. Nothing on the
new site links to them, the old site's real traffic was small, and a category archive is a
navigation aid rather than content anyone deep-links to — unlike the dated post permalinks,
which every post does carry a `redirect_from` for.
