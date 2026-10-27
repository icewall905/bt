<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { preview } from '$lib/preview';
	import { agent } from '$lib/stores/agent.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { focusable } from '$lib/nav';
	import { fmtBytes, fmtCountdown, isVideo, timeAgo } from '$lib/util';
	import type { DownloadItem, DownloadsResponse } from '$lib/types';
	import Section from './Section.svelte';
	import SaveBar from './SaveBar.svelte';
	import { SettingsDraft } from './useSettings.svelte';
	import Toggle from '$lib/components/form/Toggle.svelte';
	import Slider from '$lib/components/form/Slider.svelte';
	import Select from '$lib/components/form/Select.svelte';
	import Stepper from '$lib/components/form/Stepper.svelte';

	const d = new SettingsDraft('cache');
	let data = $state<DownloadsResponse | null>(null);
	let failed = $state(false);
	let filter = $state<'all' | 'done' | 'active' | 'error'>('all');
	let confirmClear = $state(false);
	let clearing = $state(false);
	let reencoding = $state(false);

	async function load() {
		try {
			data = await api.downloads();
			failed = false;
		} catch {
			failed = true;
			data = data ?? { items: [], totals: { used_bytes: 0, max_bytes: 0 }, downloader: null };
		}
	}
	onMount(() => {
		load();
		const t = setInterval(load, 5000);
		return () => clearInterval(t);
	});

	const dl = $derived(agent.downloader.state !== 'offline' ? agent.downloader : (data?.downloader ?? agent.downloader));
	const used = $derived(dl?.used_bytes ?? data?.totals.used_bytes ?? 0);
	const max = $derived(dl?.max_bytes || data?.totals.max_bytes || (d.value.max_gb ?? 0) * 1e9);
	const pct = $derived(max ? Math.min(100, (used / max) * 100) : 0);
	const items = $derived(
		(data?.items ?? [])
			.filter((i) => i.status !== 'evicted')
			.filter((i) => (filter === 'all' ? true : filter === 'done' ? i.status === 'done' : filter === 'active' ? i.status === 'queued' || i.status === 'downloading' : i.status === 'error'))
	);
	const count = (st: string) => (data?.items ?? []).filter((i) => (st === 'active' ? i.status === 'queued' || i.status === 'downloading' : i.status === st)).length;

	const titleOf = (i: DownloadItem) => (isVideo(i.video) ? i.video.title : i.title) || i.video_id;
	const progressOf = (i: DownloadItem) => (i.status === 'downloading' && dl?.video_id === i.video_id ? (dl.progress ?? i.progress) : i.progress) || 0;

	async function remove(i: DownloadItem) {
		await api.removeDownload(i.video_id);
		toast.success(`Removed ${titleOf(i)}`);
		load();
	}
	async function clearAll() {
		if (!confirmClear) return (confirmClear = true);
		clearing = true;
		try {
			const r = await api.clearDownloads();
			toast.success(`Removed ${r.removed} saved video${r.removed === 1 ? '' : 's'}`);
			confirmClear = false;
			load();
		} finally {
			clearing = false;
		}
	}
	async function reencodeSaved() {
		reencoding = true;
		try {
			const r = await api.reencodeDownloads();
			toast.success(r.queued ? `Queued ${r.queued} saved video${r.queued === 1 ? '' : 's'} for GPU re-encoding` : 'No additional saved videos to queue');
			await load();
		} finally {
			reencoding = false;
		}
	}

	const HEIGHTS = [480, 720, 1080, 1440].map((h) => ({ value: h, label: `${h}p`, hint: h === 1080 ? 'About 0.5 to 1 GB per 20 minutes' : h === 720 ? 'About half the size of 1080p' : undefined }));
	const RATES = [
		{ value: 2_000_000, label: '2 MB/s', hint: 'Barely noticeable on most connections' },
		{ value: 4_000_000, label: '4 MB/s' },
		{ value: 8_000_000, label: '8 MB/s', hint: 'Default' },
		{ value: 16_000_000, label: '16 MB/s' },
		{ value: 32_000_000, label: '32 MB/s' },
		{ value: 0, label: 'Unlimited', hint: 'Fastest, but can slow down streaming in the house' }
	];
	const AUTO = [
		{ value: 'accepted' as const, label: 'Every AI pick', hint: 'Download everything the AI accepts, best first, until the cap.' },
		{ value: 'manual' as const, label: 'Only what I save', hint: 'Download only videos you mark with "Save offline".' }
	];
	const DL_LABEL: Record<string, string> = {
		offline: 'Download service not running', idle: 'Everything wanted is saved', sleeping: 'Resting between downloads',
		full: 'Storage full', paused: 'Paused with the AI', disabled: 'Downloads turned off', backoff: 'Waiting for YouTube',
		transcoding: 'Re-encoding on the GPU'
	};
	const STATUS: Record<string, string> = { queued: 'Waiting', downloading: 'Downloading', done: 'Saved', error: 'Failed', evicted: 'Removed' };
</script>

<Section title="Storage" intro="Save videos on the server so they play instantly, at full quality, without asking YouTube again. Saved copies are shared by every profile.">
	<div class="usage panel">
		<div class="uh">
			<div>
				<div class="big">{fmtBytes(used)}</div>
				<div class="small muted">used of {max ? fmtBytes(max) : '…'}</div>
			</div>
			<div class="dlstate small">
				{#if dl?.state === 'downloading'}
					<strong>Downloading</strong> {dl.title || dl.video_id}
					<span class="muted">{Math.round((dl.progress ?? 0) * 100)}%{dl.speed ? `, ${fmtBytes(dl.speed)}/s` : ''}{dl.eta ? `, ${fmtCountdown(Math.round(dl.eta))} left` : ''}</span>
				{:else if dl?.state === 'transcoding'}
					<strong>Re-encoding on the GPU</strong> {dl.title || dl.video_id}
					<span class="muted">{Math.round((dl.progress ?? 0) * 100)}%</span>
				{:else if dl}
					<span class="muted">{DL_LABEL[dl.state] ?? dl.state}{dl.detail ? `: ${dl.detail}` : ''}</span>
				{/if}
				{#if dl?.queue}<span class="muted">{dl.queue} waiting</span>{/if}
			</div>
		</div>
		<div class="bar" role="meter" aria-label="Storage used" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
			<span style:width="{pct}%" class:hot={pct > 90}></span>
		</div>
	</div>

	<Toggle label="Save videos on the server" hint="Off stops new downloads. Saved videos keep playing." bind:checked={d.value.enabled} />
	<Select label="What to save" bind:value={d.value.auto} options={AUTO} />
	<div class="one">
		<Slider label="Space to use" hint="When full, the oldest watched videos are removed first. Videos you saved yourself are kept." bind:value={d.value.max_gb} min={10} max={2000} step={10} format={(v) => (v >= 1000 ? `${(v / 1000).toFixed(v % 1000 ? 2 : 0)} TB` : `${v} GB`)} />
		<Select label="Download quality" bind:value={d.value.max_height} options={HEIGHTS} />
		<Select label="Download speed limit" hint="Keeps downloads from hogging the internet connection." bind:value={d.value.rate_limit} options={RATES} />
		<Stepper label="Pause between downloads" hint="A short random wait keeps the traffic pattern polite." bind:value={d.value.min_gap_s} min={0} max={3600} step={10} format={(v) => (v >= 60 ? `${Math.round(v / 60)} min` : `${v} s`)} />
		<Toggle label="HW Transcoding" hint="Shrink new downloads about 40–50% by re-encoding them on the server's NVIDIA GPU (NVENC). Needs the GPU wired to the downloader; when it is missing, files are kept as downloaded." bind:checked={d.value.hw_transcode} />
		<div><button class="btn" disabled={reencoding || !(data?.items ?? []).some((i) => i.status === 'done')} use:focusable={{ onSelect: reencodeSaved }}>Re-encode saved videos on GPU</button>
			<p class="small muted">Processes existing saved videos in the background, independently of the toggle above. Originals stay playable and are kept if encoding fails or does not save space.{data?.reencode?.queued ? ` ${data.reencode.queued} waiting or in progress.` : ''}{data?.reencode?.failed ? ` ${data.reencode.failed} were not re-encoded; see activity for details or press the button to retry.` : ''}</p></div>
	</div>
	<SaveBar dirty={d.dirty} busy={d.busy} onsave={() => d.save('Storage settings saved')} onreset={() => d.reset()} />
</Section>

<div style="height:2.2rem"></div>

<Section title="Saved videos">
	{#snippet actions()}
		{#if (data?.items ?? []).some((i) => i.status !== 'evicted')}
			<button class="btn danger" disabled={clearing} use:focusable={{ group: 'st-top', onSelect: clearAll }}>{confirmClear ? 'Press again to delete every saved video' : 'Clear all'}</button>
		{/if}
	{/snippet}
	<div class="hstack">
		{#each [['all', 'All'], ['done', `Saved ${count('done')}`], ['active', `In progress ${count('active')}`], ['error', `Failed ${count('error')}`]] as [k, l]}
			<button class="chip" class:on={filter === k} use:focusable={{ group: 'st-filter', onSelect: () => (filter = k as typeof filter) }}>{l}</button>
		{/each}
	</div>
	{#if data === null}
		<div class="skeleton" style="height:8rem"></div>
	{:else if failed && !data.items.length}
		<p class="muted">The download list is not available. The storage service may not be running yet.</p>
	{:else if items.length === 0}
		<p class="muted">Nothing here yet. {d.value.auto === 'manual' ? 'Use "Save offline" on a video to keep it.' : 'Videos the AI picks are saved here as they are found.'}</p>
	{:else}
		<div class="list">
			{#each items as i (i.video_id)}
				<div class="item {i.status}">
					<span class="pvw" use:preview={{ id: i.video_id, offline: i.status === 'done' }}><img src={api.thumb(i.video_id, 'mq')} alt="" loading="lazy" /></span>
					<div class="info">
						<strong class="t">{titleOf(i)}</strong>
						<span class="small muted">
							{STATUS[i.status] ?? i.status}{i.height ? `, ${i.height}p` : ''}{i.size_bytes ? `, ${fmtBytes(i.size_bytes)}` : ''}{i.pinned ? ', kept by you' : ''}{i.last_played_at ? `, played ${timeAgo(i.last_played_at)}` : ''}
						</span>
						{#if i.status === 'downloading' || (i.status === 'queued' && i.progress > 0)}
							<div class="pbar"><span style:width="{progressOf(i) * 100}%"></span></div>
						{/if}
						{#if i.status === 'error' && i.error}<span class="small err">{i.error}</span>{/if}
					</div>
					{#if i.status === 'done'}<a class="btn mini" href="/watch/{i.video_id}" use:focusable={{ group: `st-${i.video_id}` }}>Play</a>{/if}
					<button class="btn mini danger" use:focusable={{ group: `st-${i.video_id}`, onSelect: () => remove(i) }}>{i.status === 'done' ? 'Delete' : 'Cancel'}</button>
				</div>
			{/each}
		</div>
	{/if}
</Section>

<style>
	.usage {
		display: grid;
		gap: 0.9rem;
	}
	.uh {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
		align-items: flex-end;
	}
	.big {
		font-size: clamp(1.6rem, 1.5vw + 0.8rem, 2.4rem);
		font-weight: 800;
		letter-spacing: -0.03em;
		font-variant-numeric: tabular-nums;
	}
	.dlstate {
		display: grid;
		gap: 0.2rem;
		text-align: right;
		max-width: 34rem;
	}
	.bar,
	.pbar {
		height: 0.6rem;
		border-radius: 1rem;
		background: rgba(255, 255, 255, 0.1);
		overflow: hidden;
	}
	.pbar {
		height: 0.35rem;
		margin-top: 0.3rem;
	}
	.bar span,
	.pbar span {
		display: block;
		height: 100%;
		border-radius: inherit;
		background: linear-gradient(90deg, var(--ok), var(--info));
		transition: width 0.6s var(--ease);
	}
	.bar span.hot {
		background: linear-gradient(90deg, var(--warn), var(--bad));
	}
	.one {
		display: grid;
		gap: 0.75rem;
	}
	.list {
		display: grid;
		gap: 0.5rem;
	}
	.item {
		display: flex;
		align-items: center;
		gap: 0.9rem;
		padding: 0.6rem 0.7rem;
		border-radius: var(--r-md);
		background: rgba(255, 255, 255, 0.035);
		border: 1px solid var(--line);
	}
	.item.error {
		border-color: rgba(255, 92, 122, 0.35);
	}
	.item img {
		width: 6.5rem;
		aspect-ratio: 16/9;
		object-fit: cover;
		border-radius: 0.45rem;
		flex: none;
	}
	.pvw {
		position: relative;
		display: block;
		flex: none;
		overflow: hidden;
		border-radius: 0.45rem;
	}
	.info {
		flex: 1;
		min-width: 0;
		display: grid;
		gap: 0.15rem;
	}
	.t {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.err {
		color: #ffc2cd;
	}
	.btn.mini {
		min-height: 2.2rem;
		padding: 0.2rem 0.85rem;
		font-size: 0.85rem;
	}
</style>
