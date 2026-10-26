<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { focusable } from '$lib/nav';
	import { fmtBytes, fmtCount, fmtDuration } from '$lib/util';
	import type { StatsPageData } from '$lib/types';

	let data = $state<StatsPageData | null>(null);
	let days = $state(30);
	let loading = $state(false);

	async function load() {
		loading = true;
		try {
			data = await api.statsPage(days);
		} catch {
			data = data ?? null; // api already toasts
		}
		loading = false;
	}

	onMount(load);

	function setDays(d: number) {
		if (days === d) return;
		days = d;
		load();
	}

	const ov = $derived(data?.overview);
	const cats = $derived(data?.categories ?? []);
	const daily = $derived(data?.daily ?? []);
	const maxDaily = $derived.by(() => {
		let m = 0;
		for (const d of daily) m = Math.max(m, d.found + d.accepted + d.rejected_ai + d.rejected_family + d.watched);
		return m || 1;
	});

	const catOf = (id: string) => cats.find((c) => c.id === Number(id));
	const shortDate = (iso: string) => iso.slice(5).replace('-', '/');
	const watchedBreakdown = (d: Record<string, number>) =>
		Object.entries(d)
			.map(([id, n]) => `${catOf(id)?.emoji ?? '•'} ×${n}`)
			.join(' ');
</script>

<svelte:head><title>Statistics · BetterTube</title></svelte:head>

<div class="page stack stats" style="gap:2.2rem">
	<header class="head">
		<h1>Statistics</h1>
		<p class="muted">Everything the curator has done across all profiles: what is waiting, what was picked, what was rejected and by whom, and what the family actually watched.</p>
		<div class="hstack">
			{#each [7, 30, 90] as d}
				<button class="chip" class:on={days === d} use:focusable={{ group: 'stats-ctl', id: `d-${d}`, onSelect: () => setDays(d) }}>{d} days</button>
			{/each}
			<button class="btn mini" disabled={loading} use:focusable={{ group: 'stats-ctl', id: 'refresh', onSelect: load }}>↻ Refresh</button>
		</div>
	</header>

	{#if !ov}
		<div class="skeleton" style="height:10rem"></div>
		<div class="skeleton" style="height:14rem"></div>
	{:else}
		<section class="panel">
			<h2>Overview</h2>
			<div class="tiles">
				<div class="tile"><span class="v">{fmtCount(ov.videos)}</span><span>Videos known</span></div>
				<div class="tile"><span class="v">{fmtCount(ov.candidates.in_queue)}</span><span>Ready in queues</span></div>
				<div class="tile"><span class="v">{fmtCount(ov.candidates.waiting_judge)}</span><span>Waiting to be judged</span></div>
				<div class="tile"><span class="v">{fmtCount(ov.downloads.waiting ?? 0)}</span><span>Waiting to download</span></div>
				<div class="tile"><span class="v">{fmtCount(ov.downloads.done ?? 0)}</span><span class="sub">Offline copies · {fmtBytes(ov.storage_bytes)}</span></div>
				<div class="tile"><span class="v">{fmtCount(ov.watched)}</span><span class="sub">{fmtDuration(ov.watch_seconds)} watched</span></div>
				<div class="tile warn"><span class="v">{fmtCount(ov.candidates.rejected_ai)}</span><span>Judge rejected</span></div>
				<div class="tile warn"><span class="v">{fmtCount(ov.candidates.rejected_family)}</span><span>Family rejected</span></div>
				<div class="tile"><span class="v">{fmtCount(ov.candidates.dismissed)}</span><span>Dismissed</span></div>
				<div class="tile"><span class="v">{fmtCount(ov.feedback.dislike + ov.feedback.note + ov.feedback.like + ov.feedback.love)}</span><span class="sub">👍 {ov.feedback.like + ov.feedback.love} · 👎 {ov.feedback.dislike}</span></div>
				<div class="tile"><span class="v">{fmtCount(ov.lessons.active)}</span><span class="sub">Lessons ({ov.lessons.inactive} off)</span></div>
				<div class="tile"><span class="v">{fmtCount(ov.budget.day)}</span><span class="sub">YT requests today / {ov.budget.max_day}</span></div>
			</div>
		</section>

		<section class="panel">
			<h2>Per category</h2>
			{#if cats.length === 0}
				<p class="muted">No categories yet. Create one in Settings and the AI will start filling it.</p>
			{:else}
				<div class="twrap">
					<table class="table">
						<thead>
							<tr>
								<th>Category</th>
								<th>Ready</th>
								<th>In review</th>
								<th>Watched</th>
								<th>Time watched</th>
								<th>Judge rejected</th>
								<th>Family rejected</th>
								<th>Dismissed</th>
								<th>Avg score</th>
							</tr>
						</thead>
						<tbody>
							{#each cats as c (c.id)}
								<tr class:off={!c.enabled}>
									<td><span class="dot" style:--cat={c.color}></span>{c.emoji} {c.name}<span class="profile-name">{c.profile_name}</span>{#if !c.enabled}<span class="faint tiny"> off</span>{/if}</td>
									<td>
										<span class="num-s">{c.counts.in_queue}/{c.target}</span>
										<span class="gauge"><span style:width="{Math.min(100, (c.counts.in_queue / Math.max(1, c.target)) * 100)}%"></span></span>
									</td>
									<td class="num-s">{c.counts.found + c.counts.enriched}</td>
									<td class="num-s">{c.counts.watched}</td>
									<td class="num-s">{fmtDuration(c.watch_seconds)}</td>
									<td class="num-s">{c.counts.rejected_ai}</td>
									<td class="num-s you">{c.counts.rejected_family}</td>
									<td class="num-s">{c.counts.dismissed}</td>
									<td class="num-s">{c.avg_score ?? '–'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>

		<section class="panel">
			<h2>Daily activity <span class="faint small">last {days} days</span></h2>
			{#if daily.every((d) => !d.found && !d.accepted && !d.rejected_ai && !d.rejected_family && !d.watched && !d.feedback)}
				<p class="muted">Nothing recorded in this window yet.</p>
			{:else}
				<div class="twrap">
					<table class="table">
						<thead>
							<tr>
								<th>Date</th>
								<th>Activity</th>
								<th>Watched</th>
								<th>Found</th>
								<th>Accepted</th>
								<th>Judge rejected</th>
								<th>Family rejected</th>
								<th>Feedback</th>
								<th>Downloads</th>
								<th>YT reqs</th>
							</tr>
						</thead>
						<tbody>
							{#each [...daily].reverse() as d (d.date)}
								{@const activity = d.found + d.accepted + d.rejected_ai + d.rejected_family + d.watched}
								<tr class:dim={activity === 0 && !d.feedback && !d.downloads}>
									<td class="num-s">{shortDate(d.date)}</td>
									<td><span class="gauge"><span class="max" style:width="{(activity / maxDaily) * 100}%"></span></span></td>
									<td>
										<span class="num-s">{d.watched}</span>
										{#if Object.keys(d.watched_by_category).length}<span class="tiny faint">{watchedBreakdown(d.watched_by_category)}</span>{/if}
									</td>
									<td class="num-s">{d.found || '·'}</td>
									<td class="num-s ok">{d.accepted || '·'}</td>
									<td class="num-s">{d.rejected_ai || '·'}</td>
									<td class="num-s you">{d.rejected_family || '·'}</td>
									<td class="num-s">{d.feedback || '·'}</td>
									<td class="num-s">{d.downloads || '·'}</td>
									<td class="num-s">{d.yt_requests || '·'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>
	{/if}
</div>

<style>
    .stats, .stats > *, .twrap {
        min-width: 0;
        max-width: 100%;
    }
    .profile-name {
        display: block;
        color: var(--faint);
        font-size: 0.8rem;
        margin-top: 0.2rem;
    }
	.head {
		display: grid;
		gap: 0.8rem;
	}
	.btn.mini {
		min-height: 2rem;
		padding: 0.2rem 0.8rem;
		font-size: 0.8rem;
	}
	.tiles {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 9.5rem), 1fr));
		gap: 0.8rem;
	}
	.tile {
		display: grid;
		gap: 0.15rem;
		padding: 0.9rem 1rem;
		border-radius: var(--r-md);
		border: 1px solid var(--line);
		background: rgba(255, 255, 255, 0.04);
		font-size: 0.82rem;
		color: var(--muted);
	}
	.tile .v {
		font-size: 1.6rem;
		font-weight: 800;
		color: var(--text);
		font-variant-numeric: tabular-nums;
		letter-spacing: -0.02em;
	}
	.tile .sub {
		color: var(--faint);
	}
	.tile.warn .v {
		color: var(--warn);
	}
	.twrap {
		overflow-x: auto;
	}
	.table {
		width: 100%;
        min-width: 52rem;
        table-layout: fixed;
		border-collapse: collapse;
		font-size: 0.92rem;
	}
    .table th:first-child { width: 20%; }
	.table th {
		text-align: left;
		font-size: 0.78rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--faint);
		font-weight: 700;
		padding: 0.4rem 0.45rem 0.6rem;
		white-space: normal;
        overflow-wrap: anywhere;
	}
	.table td {
		padding: 0.55rem 0.45rem;
		border-top: 1px solid var(--line);
		white-space: normal;
        overflow-wrap: anywhere;
	}
	.table tr.off td {
		opacity: 0.55;
	}
	.table tr.dim td {
		opacity: 0.45;
	}
	.dot {
		width: 0.55rem;
		height: 0.55rem;
		border-radius: 50%;
		background: var(--cat, var(--accent));
		display: inline-block;
		margin-right: 0.5rem;
		box-shadow: 0 0 8px var(--cat, transparent);
	}
	.num-s {
		font-variant-numeric: tabular-nums;
	}
	.you {
		color: var(--warn);
		font-weight: 650;
	}
	.ok {
		color: var(--ok);
	}
	.gauge {
		display: inline-block;
		vertical-align: middle;
		width: min(100%, 4rem);
		height: 0.4rem;
		border-radius: 1rem;
		background: rgba(255, 255, 255, 0.1);
		overflow: hidden;
	}
	.gauge span {
		display: block;
		height: 100%;
		border-radius: inherit;
		background: var(--cat, var(--ok));
	}
	.gauge span.max {
		background: linear-gradient(90deg, var(--accent), var(--ai));
	}
</style>
