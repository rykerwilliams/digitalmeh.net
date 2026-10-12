# Documentation

| | |
|---|---|
| [ROADMAP.md](ROADMAP.md) | Outstanding work — link rot, media policy, taxonomy |
| [migration-plan.md](migration-plan.md) | Moving this site off WordPress onto Jekyll — phases, findings, decisions |
| [taxonomy.md](taxonomy.md) | Proposed categories and tags, replacing 499 WordPress tags |
| [backup-and-restore.md](backup-and-restore.md) | Where the archive lives, and how to bring one post back |
| [dropped-posts.md](dropped-posts.md) | The 106 posts left behind, by title — all restorable |
| [post-manifest.csv](post-manifest.csv) | Every post with a proposed keep/review/drop, traffic and taxonomy |

Background that lives elsewhere:

- **AWS box inventory** — `aws-docker` repo. What else runs on the host this site is on.
- **GitHub Pages cutover runbook** — `teamserio.us` repo, `docs/impl/gh-pages-migration/`.
  The same move was done for that site first; the runbook covers DNS, certificates and the
  one non-obvious step that cost an outage.

The archive of the live WordPress site is **not** in git — it contains `wp-config.php` with
database credentials. It lives on phatmyth at
`/files/data/backups/digitalmeh.net/2026-10-09/`.
