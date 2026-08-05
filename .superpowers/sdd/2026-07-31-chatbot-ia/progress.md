# SDD ledger — plan: docs/superpowers/plans/2026-07-31-chatbot-ia.md
Branch: feature/livechat-ai-assistant (main tree — Docker mounts it; worktree would be invisible to the container)
Baseline: module was untracked; controller committed baseline 63a90e5 before task commits.
Task 1: implemented (111e6c5), review Spec OK / Approved, 3 Important -> fix round 1 dispatched
Task 1: minor (deferred): ToolError echoes unbounded tool name (truncate name[:64])
Task 1: minor (deferred): test_run_tool_ok_and_unknown stacks two behaviors, split
Task 1: minor (deferred): specs test checks keys only, not value round-trip
Task 1: minor (deferred): test_dryrun.py at module root — move under scripts/ or delete
Task 1: minor (deferred): stray @api.model_create_multi on _freemoov_ai_trigger_from_message (baseline)
Task 1: minor (deferred): group_user read access on ai.log (PII retention policy to decide)
Task 1: minor (deferred): _logger unused in tools/__init__.py (remove if still unused at end)
Task 1: note for Task 5 brief: agent loop must catch broad Exception around run_tool (TypeError on bad args)
Task 1: fix round 1/5 (3 addressed, 0 open; commits 63a90e5..e5692d3)
Task 1: complete (commits 3d97161..e5692d3, review clean)
Task 1: note for Task 3 brief: add negative test where _freemoov_ai_verified_partner exists and returns False
Task 2: implemented (5914850), review Spec OK / Needs work — 1 Critical (dispo ignores sellable state) + 3 Important -> fix round 1 dispatched
Task 2: minor (deferred): sort by price desc blind to stock (brief-mandated)
Task 2: minor (deferred): store_info URLs relative vs catalog absolute — unify
Task 2: minor (deferred): third copy of x_studio_marque extraction (do NOT reuse _get_brand_name, falls back to 'Freemoov')
Task 2: minor (deferred): exact stock counts exposed to anonymous visitors — client call ("en stock / sur commande" would do)
Task 2: minor (deferred): fiche_produit doesn't filter sale_ok
Task 2: minor (deferred): hardcoded https://www.freemoov.com — better: seo_base_url(env) + is_technical_host fallback
Task 2: minor (deferred): hours hardcoded vs _STORE_HOURS drift risk
Task 2: note staging/prod: check Charleroi warehouse existence + website.domain + x_studio_marque type in prod (SSH available)
Task 2: note Task 5 brief: agent loop except must cover TypeError/ValueError from tool args, not only ToolError
Task 2: fix round 1/5 (4 addressed, re-review found new Important: free_qty vs on-hand semantics in commandable; commits 5914850..d7b09d4)
Task 2: fix round 2/5 dispatched (align commandable with site on-hand; guard int() cast in warehouse map)
Task 2: fix round 2/5 (2 addressed but referential was wrong: site sale gate is free_qty in website.warehouse_id, not on-hand; 4 real false positives found; commits d7b09d4..6492ff7)
Task 2: fix round 3/5 dispatched (gate commandable on website._get_product_available_qty; invert reservation test; isinstance guard)
Task 2: minor (deferred): UnboundLocalError latent in website_freemoov get_stock_availability when no website.warehouse_id (baseline code, out of scope)
Task 2: fix round 3/5 (round-2 premise was wrong, corrected against website_sale_stock sources; 4 false positives fixed; commits 6492ff7..aa25be0)
Task 2: fix round 4/5 dispatched (any() over variants — implementer's own reserve, validated Important by re-review; same agent resumed deliberately: loop converging, not stuck)
Task 2: fix round 4/5 (any() addressed, no breakage; new Important ruled active: negative dispo relayed to visitors, 16.5% of catalog; commits aa25be0..39102b3)
Task 2: fix round 5/5 dispatched (per-variant clamp on dispo + assertion + comment realign — last round before cap)
Task 2: fix round 5/5 (clamp per variant addressed, verified on real data, 70 templates corrected; commits 39102b3..e3a20be)
Task 2: complete (commits e5692d3..e3a20be, review clean after 5 rounds)
Task 2: minor (deferred): per-product warning in _dispo_by_store becomes Sentry events (sentry_logging_level=warn) — downgrade to info or aggregate per call
Task 3: implemented (9693be0+75c0a04), security review Spec KO — C1 wildcard ilike, C2 task.name as identity, I1..I8 -> fix round 1 dispatched
Task 3: DEFERRED TO TASK 4 BRIEF (mandatory): resend cap per channel — start_verification unlink resets attempts counter (bruteforce/mail-bombing unbounded)
Task 3: minor (deferred): non-constant-time hash compare; sale.order refs sequential (enumeration oracle mitigated by rate limit); no cron purge of expired records
Task 3: process note: security reviewer printed real customer PII while probing — all future dispatches carry explicit no-PII rule
Task 3: fix round 1/5 (C1,C2,I1,I3-I8 addressed; new Important: `_` rejection blocks 2.5% of ordering customers; commits 75c0a04..540679d)
Task 3: fix round 2/5 dispatched (escape LIKE metachars on email branch instead of reject)
Task 3: note for Task 4 brief: (a) resend cap per channel MANDATORY (I2); (b) tools consume _start_verification/_check_code; (c) VERIFIED_TTL_MIN=30 -> bot must explain expired session; (d) livechat runs as public visitor env — sensitive tools must re-sudo to read partner fields; (e) agent loop catch broad Exception incl TypeError/ValueError
Task 3: fix round 2/5 (escape addressed, verified vs PostgreSQL + mutations; commits 540679d..74e7efe)
Task 3: complete (commits e3a20be..74e7efe, review clean)
EXECUTION PAUSED BY USER after Task 3 closure (2026-07-31). Resume at Task 4 (brief NOT yet generated). Carry-ins for Task 4 brief are the 'note for Task 4 brief' lines above.
