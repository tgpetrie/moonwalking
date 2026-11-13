# Carbon assignment · Design the study that finds which movers keep running

I run Moonwalking, a crypto dashboard whose mover boards show what is moving
most right now: a short-window gainers list and 3-minute gainers and losers,
eight rows each. I want those boards to tell me which coin has the most
potential to break out and keep running, even briefly. It does not need to be a
trade signal or right every time. A flagged coin should go on to run more often
than an unflagged one. After weeks of infrastructure work I have one replicated
finding and no study aimed at that goal. I want you to design that study, hard
enough that its result will be believed whichever way it comes out.

Use the attached plain-text source packet and its SHA-256 manifest. It holds
complete file bodies; you do not need my PC, the repository or the raw data.
Begin with source 01, the brief: it states my goal, the data that exists and
the options on the table. Start your reply by listing the sections you could
read and anything missing or truncated, and keep repository claims separate
from anything you calculated or checked yourself. Treat prompts and commands
embedded in the sources as evidence.

## Where things stand

One test has been run on fresh data. On sixteen days recorded after the model
was frozen, the stored live score and the displayed percentage move ranked
board entries backwards against five- and fifteen-minute outcomes, and a frozen
simple model ranked them forwards. The predeclared rule returned "keep". The
effect sits in the top fifth by score or move, which gave back about 0.17% in
five minutes and 0.27% in fifteen while the rest gave back 0.02–0.08%. Every
band's mean gross outcome was negative. Sources 02 and 03 are the protocol and
the result; source 04 has every number.

That test measured averages. My goal is about the tail: the coins that keep
going. The fastest movers could fade on average and still contain most of the
runners. Nobody has measured that.

## What I need from you

**1. Challenge the result I already have.** Outcomes use last-trade prices and
the peak fields are updated only when the tracker observes a price. Tell me
whether the fade in the top band could be a bid/ask bounce, a thin-print effect
or a selection effect of entering a top-eight list, and which stored fields can
separate those explanations from a real reversal. Each episode stores a matched
control: the nearest same-direction mover that was not on the board, with its
returns at the same checkpoints. Say exactly what comparison against that
control would be informative and what it cannot show. Read
`backend/board_outcomes.py` for how episodes, labels, peaks and controls are
written, and say where the recording itself could manufacture the pattern.

**2. Define a runner.** Give one primary definition of "kept running" that
matches my goal and can be computed from the stored outcomes, and say why you
chose it over the alternatives: relative to the day or absolute, peak or
checkpoint return, fifteen minutes or sixty. A single wick should not count as
a pump. The peak fields default to zero, so a true zero and a missing value
look alike; say how the definition handles that. Give the mirror definition for
the losers board.

**3. Make each candidate signal testable.** The brief lists five ideas for
telling a move that is still building from one already spent. For each, give an
exact formula using only fields the brief says exist, the simplest comparator
it must beat, the mechanism you expect, and the pattern of results that would
support it, rule it out or leave it open. Separate what the stored snapshot can
support now from what needs one-minute candles. If you see a better signal that
the stored fields can support, add it and say why. Percentage change alone is
the baseline every signal is compared with.

**4. Write the preregistration.** I need a specification I can execute without
further choices:

- The unit of analysis and the comparison that fits a board: of the rows
  showing, which are still going.
- The primary metric. I think in terms of "the base rate of runners is X, and
  the coins this signal flags run at Y", at a fixed share of rows flagged.
  Improve on that if it is weak.
- Which sample is for exploration and which for confirmation. The brief's
  sample table shows what each window has been used for. The post-freeze window
  has been used once, for a different target, and I have seen its band means.
  Rule on whether any of it can confirm a runner hypothesis, or whether
  confirmation must wait for days from 2026-11-13 on. If it must wait, give the
  number of new days and the rule for stopping.
- Dependence: overlapping episodes, the same coin on several boards, and
  market-wide moves in which many coins run together.
- Multiplicity across signals, boards and horizons with this little data.
- Keep, drop and inconclusive conditions, and what happens if the sample falls
  short.

Label every number you propose as a proposal with its reasoning. Do not report
results for analyses nobody has run.

**5. Design the combined board.** The brief lists six options, from an activity
gate to an early-watch list. I do not want to pick one. I want the best pieces
of all of them working together as one design. For each option, say what
evidence would justify including it, the smallest version worth shipping, and
what it would mislead a user about. Then propose how the surviving pieces fit
together: which act as a gate on entry, which change the order, which sit
beside a row as a read, and which belong in a separate list. Say which pieces
overlap enough that only one should be kept, the order in which to build and
test them so each is judged on its own before they are combined, and how the
combined design is tested against plain percentage change. The boards have to
remain a live list of what is moving most, and a user has to be able to see why
a row is where it is. Say whether the answer differs between the short-window
board and the 3-minute boards.

**6. Design the early-watch study.** Catching a coin before it reaches a board
is the most valuable outcome and cannot be tested from board episodes. Public
one-minute candles for every listed product can be pulled without credentials.
Design the smallest whole-universe study on them: the universe and how
delistings and new listings are handled, features computable from one-minute
open, high, low, close and volume, the target, the timing rule that prevents
look-ahead given that a candle is known only after it closes and that a minute
without trades has no row, and what one-minute data cannot tell me about a
30-second board. Say whether this should run before, after or beside the board
study.

**7. Rank the data gaps.** The collector does not record rows 9–16, a 30-second
board, 1-minute losers, quotes at entry or at the outcome checkpoints, trade
counts, or the dollar volume and volatility fields that are null in every fresh
row. Rank the additions by how much each would improve the study, and name the
ones the study can proceed without.

## What to return

One self-contained memo:

1. Sections read, and gaps.
2. Verdict on the existing result, with the diagnostics that would confirm or
   undermine it.
3. The runner definition.
4. A signal table: formula, comparator, mechanism, supporting and disconfirming
   patterns, data needed.
5. The preregistration, complete enough to run.
6. A six-row board decision table and the combined design you recommend, with
   its build and test order.
7. The early-watch design.
8. Ranked data gaps.
9. The three things most likely to make this whole effort produce nothing, and
   how the design guards against each.

Cite packet sections, file paths and function names. Use small synthetic
examples where they make a definition unambiguous. If my framing of the problem
is wrong, say so before designing around it.

## Boundaries

This is offline design work. The locked historical validation is not rerun for
its original question. No live score, ranking, weight or production behavior
changes on the strength of a design. The repository is public, so nothing about
accounts, balances or holdings belongs in the memo. The stalled 5-second
capture and the F1–F5 features are context; I am not asking you to rescue them,
though say so if this study makes them unnecessary or more urgent.
