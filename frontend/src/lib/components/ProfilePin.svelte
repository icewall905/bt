<script lang="ts">
	import { api } from '$lib/api';
	import { session } from '$lib/stores/session.svelte';
	import { focusable } from '$lib/nav';
	import type { Profile } from '$lib/types';
	import Modal from './Modal.svelte';
	import TextField from './form/TextField.svelte';

	let { profile }: { profile: Profile } = $props();
	let pin = $state('');
	let error = $state('');
	let busy = $state(false);
	async function unlock() {
		if (busy || !pin) return;
		busy = true; error = '';
		try {
			await api.unlockProfile(profile.id, pin);
			await session.loadProfiles();
			session.answerPin(true);
		} catch (e) { error = (e as Error).message; pin = ''; }
		finally { busy = false; }
	}
</script>

<Modal title="Unlock {profile.name}" subtitle="Enter this profile's PIN to continue." size="sm" onClose={() => { if (!busy) session.answerPin(false); }}>
	<TextField label="Profile PIN" type="password" inputmode="numeric" bind:value={pin} autofocus group="profile-pin" onsubmit={unlock} />
	{#if error}<p role="alert" class="pin-error">{error}</p>{/if}
	<p class="small muted recovery">Forgot the PIN? On your server, open the maintenance menu and choose Reset profile PIN.</p>
	{#snippet footer()}
		<button class="btn" disabled={busy} use:focusable={{ group: 'pin-actions', onSelect: () => session.answerPin(false) }}>Cancel</button>
		<button class="btn primary" disabled={busy || !pin} use:focusable={{ group: 'pin-actions', onSelect: unlock }}>{busy ? 'Unlocking…' : 'Unlock profile'}</button>
	{/snippet}
</Modal>

<style>.pin-error { color: var(--bad); margin-top: 1rem; } .recovery { margin-top: 1rem; line-height: 1.5; }</style>
