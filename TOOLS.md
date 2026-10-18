# The tools

47 tools, generated from `harness/mcp_server.py`. Each tool's full description is what Claude sees.

| tool | what it does |
|---|---|
| `simulate_futures` | SIMULATE MANY FUTURES FOR A DRUG, THEN COUNT (the method of Epic's Curiosity model, with the next step copied from similar past drugs instead of learned). |
| `reference_models` | THE STANDARD FORMAL MODEL FOR A TOPIC, so the steelman step has something real to hold a claim against. |
| `whats_new_for_gap` | NEW PAPERS FOR ONE GAP MAP GAP, since the last look. |
| `will_this_work` | THE ODDS FOR ONE GAP MAP FIX: its counted base rate (s of n similar attempts and the rule of succession (s + 1) / (n + 2)), the forecast on the record for a near-term question, and what is known. |
| `claim_rows` | ONE ROW PER CHECKED CLAIM, SO CLAIMS CAN BE COUNTED. |
| `gaps_moving` | GAP MAP GAPS RANKED BY RECENT ACTIVITY: papers in the last `days` that the daily reading judged on topic, with the judged and unjudged counts beside them. |
| `decide_panel` | READ BACK FILLED ELICITATION SHEETS FOR A DECISION and MEASURE the shared-author bias instead of assuming it. |
| `chain` | USE THIS WHEN a claim needs several separate things to ALL go right -- 'X will happen, and then Y, and then Z'. |
| `plan_audit` | USE THIS WHEN someone says a plan is nearly done, or 'it'll probably work', and you want to know how done it really is. |
| `chain_list` | List saved chains that can be rerun by name. |
| `chain_save` | Save an inline chain so it can be rerun and revised. |
| `chain_elicit` | EMIT A BLANK ELICITATION SHEET FOR A CHAIN. |
| `chain_panel` | READ BACK FILLED ELICITATION SHEETS FOR A CHAIN and report what the claim comes to under each author. |
| `instability_score` | USE THIS FOR ANY QUESTION ABOUT A COUNTRY COMING APART -- civil war, coup, collapse, a democracy sliding. |
| `find_gaps` | USE THIS WHEN you are about to hand someone a number and you cannot say out loud what you left out of it. |
| `publication_screen` | RUN THIS BEFORE PUBLISHING ANY ANSWER. |
| `robust` | USE THIS WHEN someone says 'but you made those numbers up', or when you are about to act on a margin that looks comfortable. |
| `trial_design` | DESIGN AN N-OF-1 TRIAL BEFORE RUNNING IT. |
| `trial_worth` | USE THIS WHEN someone is about to run a test to settle a decision and nobody has asked whether its answer could change the choice. |
| `trial_assign` | GET THE ARM FOR A DAY, OR THE WHOLE SCHEDULE. |
| `trial_analyse` | ANALYSE A FINISHED OR RUNNING TRIAL. |
| `decide` | USE THIS WHEN you are about to recommend one option over another and the numbers behind the recommendation are judgements rather than measurements -- which is most of the time. |
| `decide_list` | List saved decisions that can be rerun by name. |
| `decide_save` | Save an inline decision so it can be rerun, revised and compared later. |
| `decide_elicit` | Emit a BLANK elicitation sheet for a decision: the channel list with every number stripped out and every judgement about magnitude or evidence quality removed. |
| `audit` | RUN THIS FIRST. |
| `check_budget` | USE THIS BEFORE DECIDING WHAT TO MEASURE, and before writing any model at all. |
| `check_frame` | Is the question answerable at all? |
| `check_lineage` | USE THIS WHEN a claim is widely repeated and you are about to treat the repetition as evidence. |
| `check_entailment` | USE THIS WHEN you have good sources and are about to state something slightly stronger than they support. |
| `ledger_add` | USE THIS THE MOMENT YOU STATE A PROBABILITY, before you find out whether you were right, and before you know the answer. |
| `ledger_status` | Open claims and which are due for resolution now. |
| `ledger_score` | USE THIS BEFORE TRUSTING YOUR OWN CONFIDENCE, and especially before telling someone you are 80% sure of anything. |
| `ledger_resolve` | Record what actually happened for an open claim. |
| `ledger_rerun` | USE THIS WHEN NEW INFORMATION CHANGES AN OPEN FORECAST. |
| `ledger_calibrate` | How much of your own judgment the record says to keep. |
| `ledger_due` | Only the open forecasts whose resolution date has passed, each with its resolution criteria, so they can be settled. |
| `evidence` | ASK BEFORE REPORTING ANY INTERVAL: does it settle the decision? |
| `loop` | CALL THIS BEFORE ANY OTHER TOOL ON THIS SERVER. |
| `operation` | THE FRONT DOOR. |
| `ancestry` | WHERE EVERY MODULE IN THIS SERVER ALREADY EXISTED, decades earlier, in public. |
| `steelman` | RUN THIS FIRST, BEFORE ANY OTHER CHECK. |
| `mirror` | RUN THIS LAST, ON YOUR OWN CORRECTION. |
| `route` | THE ELEVEN SHAPE QUESTIONS. |
| `constant` | USE THIS BEFORE QUOTING ANY PUBLISHED EFFECT SIZE about elections, coalitions or party systems. |
| `theory_slot` | USE THIS WHEN somebody proposes wiring a social-science theory into an analysis. |
| `render_finding` | Write a standalone HTML page presenting a result in plain English — a verdict, bar charts, and the claims that could not be tested. |
