<script lang="ts">
	import { api } from '$lib/api';
	import { session } from '$lib/stores/session.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { focusable } from '$lib/nav';
	import type { CookieTestResult, ImportFeedResult, ImportSubscriptionsResult } from '$lib/types';
	import Section from './Section.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import Select from '$lib/components/form/Select.svelte';
	import Stepper from '$lib/components/form/Stepper.svelte';

	let text = $state('');
	let busy = $state(false);
	let checking = $state(false);
	let result = $state<CookieTestResult | null>(null);
	let fileInput = $state<HTMLInputElement>();
	const present = $derived(!!session.settings?.cookies?.present);

	// ---- import from the signed-in account
	const FEED_SOURCES = [
		{ value: 'recommended', label: 'Recommended feed' },
		{ value: 'watchlater', label: 'Watch later' },
		{ value: 'liked', label: 'Liked videos' },
		{ value: 'playlist', label: 'Playlist URL' }
	];
	let source = $state('recommended');
	let playlistUrl = $state('');
	let categoryId = $state(0);
	let destination = $state('new');
	let playlistName = $state('');
	let limit = $state(50);
	let subsBusy = $state(false);
	let feedBusy = $state(false);
	let subsResult = $state<ImportSubscriptionsResult | null>(null);
	let feedResult = $state<ImportFeedResult | null>(null);
	let importError = $state('');
	const categories = $derived((session.categories ?? []).filter((c) => c.enabled));
	const chosenCategory = $derived(categories.find((c) => c.id === categoryId) ?? null);
	$effect(() => {
		if (!chosenCategory && categories.length) categoryId = categories[0].id; // sensible default
	});

	async function importSubs() {
		subsBusy = true;
		subsResult = null;
		importError = '';
		try {
			subsResult = await api.importSubscriptions();
			toast.success(`Following ${subsResult.imported} new channels.`);
		} catch (e) {
			importError = (e as Error).message;
		} finally {
			subsBusy = false;
		}
	}

	async function importFromFeed() {
		if (destination === 'new' && !playlistName.trim()) return toast.warn('Give the playlist a name.');
		if (destination === 'existing' && !chosenCategory) return toast.warn('Pick a playlist to import into.');
		feedBusy = true;
		feedResult = null;
		importError = '';
		try {
			feedResult = await api.importFeed({
				category_id: destination === 'existing' ? chosenCategory!.id : undefined,
				playlist_name: destination === 'new' ? playlistName.trim() : undefined,
				source,
				playlist_url: source === 'playlist' ? playlistUrl : undefined,
				limit
			});
			await session.loadCategories();
			toast.success(`Added ${feedResult.added} videos to ${feedResult.category}.`);
		} catch (e) {
			importError = (e as Error).message;
		} finally {
			feedBusy = false;
		}
	}

	async function check() {
		checking = true;
		result = null;
		try {
			result = await api.testCookies();
			if (result.logged_in) toast.success('Cookie session is valid — signed in to YouTube.');
		} catch (e) {
			result = { present: true, logged_in: false, error: (e as Error).message };
		} finally {
			checking = false;
		}
	}

	async function upload() {
		if (!text.trim()) return toast.warn('Paste the cookies.txt content or pick a file first.');
		busy = true;
		try {
			await api.uploadCookies(text);
			text = '';
			toast.success('Cookies saved. Checking whether the session is valid…');
			await session.loadSettings();
			await check();
		} finally {
			busy = false;
		}
	}
	async function remove() {
		await api.deleteCookies();
		result = null;
		toast.success('Cookies removed');
		await session.loadSettings();
	}
	async function onFile(e: Event) {
		const f = (e.currentTarget as HTMLInputElement).files?.[0];
		if (f) text = await f.text();
	}
</script>

<Section title="YouTube cookies" intro="Optional. Some videos (age-restricted, members-only) and heavier use need a signed-in session. Export cookies.txt from a browser where you are logged in to a spare Google account, then upload it here.">
	<div class="state panel" class:on={present}>
		<span class="dot"></span>
		<div class="grow">
			<strong>{present ? 'Cookies are installed' : 'No cookies installed'}</strong>
			<p class="small muted">{present ? 'All YouTube requests from the server use this session.' : 'The server talks to YouTube anonymously.'}</p>
		</div>
		{#if present}
			<button class="btn" disabled={checking} use:focusable={{ group: 'ck-state', onSelect: check }}>
				{#if checking}Checking…{:else}Check cookies{/if}
			</button>
			<button class="btn danger" use:focusable={{ group: 'ck-state', onSelect: remove }}>Remove cookies</button>
		{/if}
	</div>
	{#if result}
		<div class="result panel" class:ok={result.logged_in} class:bad={!result.logged_in} role="status">
			{#if result.logged_in}
				<p><strong>✓ Session is valid.</strong> YouTube served this account's watch history ({result.history_items} items), so the cookies are signed in and accepted.</p>
			{:else if result.blocked}
				<p><strong>Could not check.</strong> YouTube showed a bot check while testing these cookies.</p>
				{#if result.error}<code>{result.error}</code>{/if}
			{:else if result.error}
				<p><strong>✕ Cookies were rejected.</strong> YouTube answered with an error — the session may have expired or been signed out. Export a fresh cookies.txt and replace them.</p>
				<code>{result.error}</code>
			{:else}
				<p><strong>✕ Not signed in.</strong> The file loaded, but YouTube served the page anonymously. Re-export cookies from a browser where the account is still logged in, then replace them.</p>
			{/if}
		</div>
	{/if}
	<p class="small warn">Use a throwaway account. Anyone with these cookies can act as that account, and YouTube may restrict accounts used from servers.</p>
	<input bind:this={fileInput} class="file-input" type="file" accept=".txt,text/plain" onchange={onFile} />
	<div><button class="btn" use:focusable={{ group: 'ck-file', onSelect: () => fileInput?.click() }}>Choose cookies.txt file</button></div>
	<TextField multiline rows={8} label="…or paste the file contents" bind:value={text} placeholder={'# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t…'} group="ck-text" />
	<div><button class="btn primary big" disabled={busy} use:focusable={{ group: 'ck-save', onSelect: upload }}>{present ? 'Replace cookies' : 'Install cookies'}</button></div>
</Section>

{#if present}
	<div class="gap"></div>

	<Section title="Import from your YouTube account" intro="Bring the taste you already have into {session.profile?.name ?? 'this profile'}. Create a playlist from your videos. The AI writes a prompt from the full import and finds similar replacements as you mark videos seen.">
		<div class="panel import">
			<div>
				<strong>Subscriptions</strong>
				<p class="small muted">Follow every channel this account follows, in this profile. The curator then watches their new uploads.</p>
			</div>
			<button class="btn" disabled={subsBusy} use:focusable={{ group: 'ck-imp', id: 'ck-imp-subs', onSelect: importSubs }}>
				{#if subsBusy}Importing…{:else}Import subscriptions{/if}
			</button>
		</div>
		{#if subsResult}
			<p class="small {subsResult.imported ? 'good' : 'muted'}">
				Following {subsResult.imported} new channel{subsResult.imported === 1 ? '' : 's'}
				({subsResult.already_known} already known).
			</p>
		{/if}

		<div class="panel import">
			<div>
				<strong>Create a self-refilling playlist</strong>
				<p class="small muted">Import your starting picks directly, without AI judging. For a new playlist, every imported video helps shape an editable AI prompt. The curator uses it to refill seen spots with similar videos.</p>
			</div>
		</div>
		<div class="feedgrid">
			<Select label="Source" bind:value={source} group="ck-imp" options={FEED_SOURCES} />
			{#if source === 'playlist'}
				<TextField label="Playlist URL" bind:value={playlistUrl} placeholder="https://www.youtube.com/playlist?list=PL…" group="ck-imp" />
			{/if}
			<Select label="Destination" bind:value={destination} group="ck-imp" options={[
                { value: 'new', label: 'Create a new playlist' },
                { value: 'existing', label: 'Add to an existing playlist' }
            ]} />
            {#if destination === 'new'}
                <TextField label="Playlist name" bind:value={playlistName} placeholder="My playlist" group="ck-imp" />
            {:else}
            <Select
                label="Into playlist"
				bind:value={categoryId}
				group="ck-imp"
				options={categories.map((c) => ({ value: c.id, label: `${c.emoji} ${c.name}` }))}
			/>
			{/if}
			<Stepper label="Max videos" bind:value={limit} min={10} max={200} step={10} />
			<button class="btn primary" disabled={feedBusy} use:focusable={{ group: 'ck-imp', id: 'ck-imp-feed', onSelect: importFromFeed }}>
				{#if feedBusy}Importing & preparing…{:else if destination === 'new'}Create playlist & import{:else}Import into playlist{/if}
			</button>
		</div>
		{#if destination === 'existing' && !categories.length}
			<p class="small muted">Create a playlist first (Settings → Playlists).</p>
		{/if}
		{#if feedResult}
			<div class="result panel ok">
				<p><strong>Added {feedResult.added} of {feedResult.found} videos to {feedResult.category}.</strong> They are ready to watch; the curator will judge only future replacements.</p>
                {#if feedResult.created}
                    <p class="small muted">Your playlist refills to {feedResult.target_queue} videos as picks are seen. Edit the prompt in Settings → Playlists.</p>
                    <p class="small">{feedResult.brief}</p>
                {/if}
				{#if feedResult.skipped}
					<p class="small muted">Skipped {feedResult.skipped}: {Object.entries(feedResult.skip_reasons).map(([k, v]) => `${k} (${v})`).join(', ')}</p>
				{/if}
			</div>
		{/if}
		{#if importError}
			<p class="small bad-import">{importError}</p>
		{/if}
	</Section>
{/if}

<style>
	.state {
		display: flex;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
	}
	.dot {
		width: 0.9rem;
		height: 0.9rem;
		border-radius: 50%;
		background: var(--faint);
	}
	.on .dot {
		background: var(--ok);
		box-shadow: 0 0 12px var(--ok);
	}
	.grow {
		flex: 1;
	}
	.result {
		padding: 0.9rem 1.1rem;
	}
	.result.ok {
		background: rgba(61, 220, 151, 0.08);
		border: 1px solid rgba(61, 220, 151, 0.4);
	}
	.result.bad {
		background: rgba(255, 92, 122, 0.08);
		border: 1px solid rgba(255, 92, 122, 0.45);
	}
	.result p {
		margin: 0;
	}
	.result code {
		display: block;
		margin-top: 0.5rem;
		font-size: 0.85rem;
		white-space: pre-wrap;
		word-break: break-word;
		background: rgba(0, 0, 0, 0.3);
		padding: 0.5rem 0.7rem;
		border-radius: var(--r-sm);
	}
	.warn {
		color: #ffe3a3;
	}
	.file-input {
		display: none;
	}
	.gap {
		height: 2.4rem;
	}
	.import {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
		padding: 0.9rem 1.1rem;
	}
	.feedgrid {
		display: grid;
		gap: 0.9rem;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 20rem), 1fr));
		align-items: end;
	}
	.good {
		color: var(--ok);
	}
	.bad-import {
		color: var(--bad);
	}
</style>
