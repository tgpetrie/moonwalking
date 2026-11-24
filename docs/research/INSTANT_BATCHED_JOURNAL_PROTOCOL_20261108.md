# Bounded journal batching comparison

Use the existing synthetic startup and burst workload. Compare the single-frame
writer with a maximum of 16 frames per batch. For each writer, run three
repetitions at each combination of queue size (128 or 256) and post-startup
writer pause (0 or 450 ms). The fixture supplies five startup frames, then
160 frames over 100 ms and 40 more over one second. The writer takes only
frames already queued, with no deliberate batching delay. The source uses
local fixture data and the existing indexed recorder.

In batch mode, the writer commits the ordered input envelopes before
processing. The second transaction writes the audit rows and removes the
staged envelopes atomically. The input, quote and trade availability
clocks start with post-ingress-commit processing. The capture loop calls
decision hooks after the audit transaction returns. The recorded ingress
commit observation is an upper bound on the actual first commit instant.
Reader stamps stay intact. SQLite uses DELETE journaling and synchronous
EXTRA for both transactions. The single-frame writer remains the default.

Hard-exit probes interrupt ingress, interrupt the audit transaction after
its inserts, and exit after both commits. Recovery checks the processed
prefix and separately reads any committed input still awaiting processing.
Pending input has its original receipt stamps and no synthesized processing
or decision evidence. A fresh segment starts with a new connection identity.

For each trial, verify the exact ordered wire prefix, connection identity,
processing chronology, pending table and SQLite integrity. Report complete
trials, overflow stops, queue high-water, reader-to-writer, and
reader-through-audit-commit latency. Interpret latency for incomplete trials
only over committed frames. A 450 ms writer pause can overflow a 128-frame
queue before batching has a chance to drain it. The test measures a local
synthetic workload. The real arrival distribution and decision-age budget
remain separate pilot questions.
