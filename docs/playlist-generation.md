# Playlist generation performance

The curator overlaps its serial AI work (feedback learning, then judging) with
researching one candidate. Discovery runs after both finish, so search planning
sees the latest queue and lessons. AI calls still share the existing GPU lock;
YouTube operations still share one worker request stream and its existing delays,
caps, playback hold, quiet hours and circuit breaker.

Completed metadata and transcripts are checkpointed in `research:<video_id>`
settings. A restart or interruption during comments can resume without repeating
those steps. Empty transcripts count as a completed attempt, as before. Caption
discovery data expires after one hour until a transcript has been saved. Successful
completion removes the checkpoint. Existing databases need no schema migration.

Within each category, research prioritises videos whose enrichment is already
cached, then channels with positive profile feedback, with FIFO order for ties.
This changes research order only; evidence budgets and acceptance checks remain
unchanged. Metadata and comment extraction remain separate to preserve filtering
before the cost of comment collection.

Worker logs report elapsed metadata, transcript, comment and judge times, plus the
overlapping research/judge pass. Use these measurements on representative queues
to assess throughput; no fixed speedup is assumed.
