<script lang="ts">
	import { api } from '$lib/api';
	import { session } from '$lib/stores/session.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { focusable } from '$lib/nav';
	import type { Profile } from '$lib/types';
	import Modal from './Modal.svelte';
	import TextField from './form/TextField.svelte';
	import EmojiPicker from './EmojiPicker.svelte';
	import ColorPicker from './ColorPicker.svelte';
	import Avatar from './Avatar.svelte';

	let { profile = null, onClose }: { profile?: Profile | null; onClose: () => void } = $props();
	// svelte-ignore state_referenced_locally
	let name = $state(profile?.name ?? '');
	// svelte-ignore state_referenced_locally
	let emoji = $state(profile?.emoji ?? '😺');
	// svelte-ignore state_referenced_locally
	let color = $state(profile?.color ?? '#ff6b9a');
	let confirmDelete = $state(false);
	let busy = $state(false);

	async function save() {
		if (!name.trim()) return toast.warn('Give the profile a name first.');
		busy = true;
		try {
			if (profile) await api.updateProfile(profile.id, { name: name.trim(), emoji, color });
			else {
				const p = await api.createProfile({ name: name.trim(), emoji, color });
				toast.success(`Added ${p.name}`);
			}
			await session.loadProfiles();
			onClose();
		} finally {
			busy = false;
		}
	}

	async function remove() {
		if (!profile) return;
		if (!confirmDelete) return (confirmDelete = true);
		await api.deleteProfile(profile.id);
		toast.success(`Removed ${profile.name}`);
		await session.loadProfiles();
		if (session.profileId === profile.id && session.profiles[0]) await session.switchProfile(session.profiles[0].id);
		onClose();
	}
</script>

<Modal title={profile ? `Edit ${profile.name}` : 'New profile'} subtitle="Each person gets their own playlists, history and AI memory." size="md" {onClose}>
	<div class="stack">
		<div class="preview">
			<Avatar {emoji} {color} size="4.5rem" />
			<div class="pname">{name || 'Name'}</div>
		</div>
		<TextField label="Name" bind:value={name} placeholder="e.g. Maja" autofocus id="profile-name" />
		<div class="field"><span class="label">Emoji</span><EmojiPicker bind:value={emoji} /></div>
		<div class="field"><span class="label">Colour</span><ColorPicker bind:value={color} /></div>
	</div>
	{#snippet footer()}
		{#if profile && session.profiles.length > 1}
			<button class="btn danger" use:focusable={{ onSelect: remove, scroll: 'nearest' }}>{confirmDelete ? 'Press again to delete everything' : 'Delete profile'}</button>
		{/if}
		<span class="spacer"></span>
		<button class="btn" use:focusable={{ onSelect: onClose, scroll: 'nearest' }}>Cancel</button>
		<button class="btn primary" disabled={busy} use:focusable={{ id: 'profile-save', onSelect: save, scroll: 'nearest' }}>{profile ? 'Save' : 'Add profile'}</button>
	{/snippet}
</Modal>

<style>
	.preview {
		display: flex;
		align-items: center;
		gap: 1rem;
	}
	.pname {
		font-size: 1.4rem;
		font-weight: 700;
	}
</style>
