# Evidence and core memory

Core membership is a storage choice, not a confidence boost. The family identity
and safety instructions remain at the start of the system prompt. A core contains
explicit rules, supported patterns and tentative or unreviewed inferences, labelled
separately. Consolidation cannot merge explicit rules with tentative inferences.

## Learning and revision

- New lessons cite only feedback that supports that specific lesson. Whole mixed
  batches are no longer attached to every lesson. Existing legacy citations are
  reclassified against the original feedback when reviewed.
- Plain likes normally create no new rule, but the learner must request review of
  existing preferences they support or contradict, including core source IDs.
- A separate LLM call classifies the relevant history as support, contradiction or
  irrelevant, with a reason for every feedback ID. Feedback is scoped to the same
  profile and, for scoped rules, the applicable playlist/channel.
- The program counts distinct videos, with at most one vote per video. A revision
  requires **at least two opposing videos and more opposing than supporting
  videos**: a one-example inference needs two; a five-example pattern needs six.
  This is an eligibility gate, not automatic approval of the new wording.
- A generic comment such as “boring” provides no cause. When this was the only
  supporting example, the replacement preserves that video's dislike, explicitly
  states that its cause was unspecified, and removes only the subject-wide
  inference. The model cannot invent a ban on sleeping/static videos from a title.
- Otherwise a drafting call uses the full reviewed history to propose a narrower
  rule, preserving supported concerns and scope. A separate semantic audit must
  approve every revision, including the generic neutral correction.
- A positive rating on a documentary does not approve everything depicted in it.
  Ethical/safety concerns need feedback specifically about that concern to count
  as a contradiction. Direct general instructions found in the original feedback
  are protected; rules added or edited directly in Settings are also protected.
- Originals, revised text, the independent audit reason and reviewed raw feedback
  snapshots are retained in `LessonRevision`. Agent activity records the change.
  Explicitly deleting a rule/profile deletes its evidence and revision records.

Revisions happen while daily feedback is processed; they do not wait for the
nightly job. Changed wording immediately invalidates an older core, so the
current source rules apply until consolidation rebuilds it. Confidence-only
changes do not disrupt the cached core during the day, but are picked up on the
next consolidation. Repeated reinforcement without new text can therefore still
update the core's confidence labels.

LLM failures leave the rule intact and the feedback pending for retry. Missing,
duplicated, cross-profile and out-of-batch IDs are rejected. A final transaction
checks that the user has not edited the rule or its evidence during model calls.
Automatic reviews are limited to 80 feedback records per rule; larger histories
produce a manual-review notice in Agent activity instead of using partial history.

## Validation

`test_knowledge.py` tests the ferret and pet-lion asymmetry, repeated ratings of a
single video, legacy mixed batches, exact citations, explicit instructions,
scopes/profiles, evidence deletion, semantic-audit rejection and concurrent edits.

`BT_MEMORY_LIVE=1 BT_DATA_DIR=$(mktemp -d) backend/.venv/bin/python -m pytest
backend/tests/test_knowledge_live.py -q -s` checks the real configured LLM against
synthetic feedback in an isolated database. It runs the full daily learner path,
including a rule already represented by core memory. It is skipped by default.
