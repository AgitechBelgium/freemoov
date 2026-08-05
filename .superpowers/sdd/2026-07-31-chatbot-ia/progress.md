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
EXECUTION RESUMED BY USER (commit ledger + continue through Task 11).
Task 4: implemented (d76407f), review Spec OK — 3 Important (bill-to recipient lie, lookup-free probing, invoice vs refund) -> fix round 1 dispatched
Task 4: minor (deferred): send_mail sync PDF in chat turn; last-picking-by-id heuristic; dead _STATE_FR entries; check-then-act race on cap; cap policy only in tool (model bare); reparation_number fallback to t.name; stage False when no stage; no arg-type validation in run_tool (str casts); repair_tool_enabled not in Settings UI (Task 11 will add it)
Task 4: note for Task 5 brief: ALL tool calls must route through run_tool (never TOOLS[name]["fn"]) — invariant holds only there; rate_limit counts responses not tool calls
Task 4: note for Task 7 brief: prompt must tell model: expired verification -> relaunch envoyer_code; child_of=company-wide visibility is assumed
Task 4: fix round 1/5 (3 addressed + 3 freebies, independently reproduced 63/63; commits d76407f..cc34d2e)
Task 4: complete (commits be67860..cc34d2e, review clean; 1 Important adjudicated to Task 5 brief: psycopg2 reraise in orders.py send_mail wrap)
Task 4: minor (deferred): empty identifier burns quota (one-line guard); FK partner_id SET NULL bypasses constrains -> add partner_id != False in _check_code domain; cap-per-channel not proven by test; renvoyer_facture description says "client vérifié" but routes to bill-to; not_found label misleading when partner resolved without contact info
Task 5: implemented (2b67794+b76035c), review Spec OK — 3 Important in-scope (max_tokens, cap message, 7th-iteration side effects) -> fix round 1 dispatched
Task 5: MANDATORY FOR TASK 6 BRIEF: (a) except psycopg2.Error: raise BEFORE except Exception in discuss_channel._freemoov_ai_respond AND MailMessage.create override; (b) worker timeout risk — 20s x 7 iterations synchronous in visitor request vs limit_time_real 120s: reduce client timeout and/or per-turn time budget in run_agent
Task 5: minor (deferred): no prompt caching (check 4096-token min for Haiku cacheable); tool_calls arguments persisted raw (identifiers) — Task 6 decides; parallel-block test doesn't pin tool_use_id routing; shared dict in [_resp()]*10; latency naming ambiguity
Task 5: fix round 1/5 (3 addressed, independently reproduced 88/88; commits b76035c..1d49cb3)
Task 5: complete (commits cc34d2e..1d49cb3, review clean)
Task 5: minor (deferred): report misattributes bug masking to _resp order (editorial); >= vs == on cap guard; renvoyer_facture still uncapped per channel within a turn
Task 6: implemented (f56bf6f), review Spec KO — C1 card price rounding, C2 typing undeliverable pre-commit, I1-I6 -> fix round 1 dispatched
Task 6: ADJUDICATED: C2 typing indicator -> MANDATORY Task 9 carry-in (client-side indicator while RPC pending; server bus emit stays but lands post-commit)
Task 6: parked with ruling: I4 psycopg2 retrying replays side-effect sends (2 codes/2 invoices on rare serialization failures) — accepted v1 risk, documented in report; real fix = per-turn idempotency guard, out of scope
Task 6: minor (deferred): dry_run arbitrage Task 11 (disable side-effect tools in dry_run recommended by reviewer); delay_seconds param dead — Task 11 decides; card CSS in Task 9; bot membership visibility to validate in staging; requests timeout is socket-level not total budget
Task 6: fix round 1/5 (C1,I1-I6 addressed, independently reproduced 128/128; commits f56bf6f..84ee4ce)
Task 6: complete (commits 1d49cb3..84ee4ce; residual 2-line psycopg2 reraise in _freemoov_ai_post_apology folded into Task 7 dispatch)
PROCESS CHANGE BY USER: per-task reviews stopped; user will arrange review at end of development. Implementers keep TDD + self-review; controller keeps ledger.
Task 6: minor (deferred): report inexactitudes (FALLBACK_TEXT not shared; I4 "same record" wording); assertNotIn("1300") collision risk; TVAC label assumes price_include (verify staging); bot-partner-missing self-reply loop guard (Task 11); int() nu on 3 legacy params (Task 11)
Task 7: complete no-review (commits c16107f+d12b8f9, 144/144, 17 mutations)
Task 7: minor (deferred): str.format brace fragility in prompt template (one-line .replace fix, Task 11); return-fees aligned on JSON-LD (customer pays) — client arbitrage if wrong; behavioral validation of prompt in staging (Task 10)
Task 8: complete no-review (commit c980120, 168/168, 13 mutations)
Task 8: minor (deferred): api_token/api_rate_per_min not in Settings (Task 11); no GC cron on api.log; approximate rate counter; form-encoded treated as no-args; API independent of enabled param (own kill switch = empty token) — confirm with client
Task 9: complete no-review (commit 6f30ad9, 174/174; client-side typing indicator delivered per C2 adjudication)
Task 9: minor (deferred): NO browser JS execution — runtime patches unverified, MANDATORY visual check before prod (Task 10/staging); channel color picker overridden by !important; suggestions shown even if assistant disabled server-side; contrast 3.9:1 AA-large only
Task 10: complete no-review (commit 1a17492, 183/183, 10 mutations 10/10 attrapées)
Task 10: écart brief: repair_tool_enabled est LIVRÉ à "False" (pas absent) — assertFalse(get_param) échoue, assertion sur != "True"
Task 10: écart brief: dispo d'un magasin non cartographié vaut None, pas 0 — assertion all(q==0) du brief invalide
Task 10: injection du brief remplacée (doublon registry+outils sensibles) par un e2e run_agent avec arguments de preuve fabriqués
Task 10: minor (deferred): _Recorder/_resp importés de test_agent_loop (couplage inter-suites); recouvrement partiel de 3 tests avec les suites unitaires
Task 10: RÉSERVE OUVERTE: validation comportementale du prompt + vérification visuelle du widget (Task 9) toujours à faire en staging
Task 10: complete no-review (commit 1a17492, 183/183, 10/10 mutations caught)
Task 11: complete no-review (commits d433540 + c1128fa + 8841d20, 212/212, 16 mutations 16/16 attrapées)
Task 11: BUG BLOQUANT trouvé hors brief : message_post force author_id=False + guest du visiteur quand user public + guest en contexte (mail_thread.py:2183) -> le bot postait sous l'identité du visiteur ET se répondait à lui-même en récursion (quota/budget écrits après l'envoi). Corrigé en 3 couches (guest=None, marqueur de contexte, refus si partenaire bot absent)
Task 11: hors brief : l'écran Réglages lisait les booléens avec bool("False")==True (cases cochées sur base éteinte) et dry_run ne pouvait pas être décoché (set_param supprime la ligne, absence = dry run) -> get_values/set_values à la main
Task 11: hors brief : 0 non enregistrable sur les entiers (set_values -> False -> suppression) ; budget de jetons passe à `budget > 0`, -1 documenté dans l'aide du champ
Task 11: migration 17.0.0.1.1 ajoutée (les enregistrements noupdate ne sont jamais nettoyés par _process_end, delay_seconds aurait survécu à son champ)
Task 11: tests/common.py fixe dry_run=False pour toutes les suites (le registre refuse les outils à effet de bord en mode observation)
Task 11: 2 tests faibles trouvés par mutation et corrigés (purges dérivant l'âge de leur propre constante ; test dry_run off vide de sens à cause du socle)
Task 11: minor (deferred): purges en une passe sans lot ; crons en noupdate (modif ultérieure non propagée) ; repair_stage_map/store_warehouse_map hors UI ; test_dryrun.py toujours à la racine du module
Task 11: RÉSERVE OUVERTE (héritée 9/10, désormais obligatoire) : vérification navigateur du widget — en particulier que les réponses du bot s'affichent côté assistant et non côté visiteur
Task 11: complete no-review (commits d433540+c1128fa+8841d20, 212/212, 16/16 mutations)
Task 11: CRITICAL FOUND OUT-OF-BRIEF AND FIXED: message_post under public+guest forced author_id False -> bot posted as visitor AND self-replied in recursion; fixed 3 layers, tested; browser verification mandatory before enabling
ALL 11 TASKS COMPLETE (2026-07-31). Suite: 212 tests green. Final whole-branch review: deferred to user (their call). Remaining before prod: browser/staging visual+behavioral checks (widget, 2FA flow, settings), enable flags, staging deploy.
