<script lang="ts">
	import { api } from '$lib/api';
	import { session } from '$lib/stores/session.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { focusable } from '$lib/nav';
	import Section from './Section.svelte';
	import TextField from '$lib/components/form/TextField.svelte';

	let text = $state('');
	let busy = $state(false);
	let fileInput = $state<HTMLInputElement>();
	const present = $derived(!!session.settings?.cookies?.present);

	async function upload() {
		if (!text.trim()) return toast.warn('Paste the cookies.txt content or pick a file first.');
		busy = true;
		try {
			await api.uploadCookies(text);
			text = '';
			toast.success('Cookies saved. They are used for the next YouTube request.');
			await session.loadSettings();
		} finally {
			busy = false;
		}
	}
	async function remove() {
		await api.deleteCookies();
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
		{#if present}<button class="btn danger" use:focusable={{ group: 'ck-state', onSelect: remove }}>Remove cookies</button>{/if}
	</div>
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
	.warn {
		color: #ffe3a3;
	}
	.file-input {
		display: none;
	}
</style>
