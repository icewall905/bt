<script lang="ts">
	import { api } from '$lib/api';
	import { session } from '$lib/stores/session.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { focusable } from '$lib/nav';
	import type { CookieTestResult } from '$lib/types';
	import Section from './Section.svelte';
	import TextField from '$lib/components/form/TextField.svelte';

	let text = $state('');
	let busy = $state(false);
	let checking = $state(false);
	let result = $state<CookieTestResult | null>(null);
	let fileInput = $state<HTMLInputElement>();
	const present = $derived(!!session.settings?.cookies?.present);

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
</style>
