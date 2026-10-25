<script lang="ts">
	import { session } from '$lib/stores/session.svelte';
	import { focusable } from '$lib/nav';
	import type { Profile } from '$lib/types';
	import Section from './Section.svelte';
	import Avatar from '$lib/components/Avatar.svelte';
	import ProfileEditor from '$lib/components/ProfileEditor.svelte';

	let editing = $state<Profile | null | undefined>(undefined);
</script>

<Section title="Profiles" intro="Family members. Each profile has its own categories, subscriptions, history and AI memory. Settings on this page are shared by everyone.">
	{#snippet actions()}
		<button class="btn primary" use:focusable={{ group: 'pf-top', onSelect: () => (editing = null) }}>＋ Add person</button>
	{/snippet}
	<div class="list">
		{#each session.profiles as p (p.id)}
			<div class="item">
				<Avatar emoji={p.emoji} color={p.color} size="3rem" />
				<div class="grow">
					<strong>{p.name}</strong>
					{#if p.id === session.profileId}<span class="small" style="color:var(--accent)">Watching now</span>{/if}
				</div>
				{#if p.id !== session.profileId}
					<button class="btn mini" use:focusable={{ group: `pf-${p.id}`, onSelect: () => session.switchProfile(p.id) }}>Switch to</button>
				{/if}
				<button class="btn mini" use:focusable={{ group: `pf-${p.id}`, onSelect: () => (editing = p) }}>Edit</button>
			</div>
		{/each}
	</div>
</Section>

{#if editing !== undefined}
	<ProfileEditor profile={editing} onClose={() => (editing = undefined)} />
{/if}

<style>
	.list {
		display: grid;
		gap: 0.5rem;
	}
	.item {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0.7rem 0.9rem;
		border-radius: var(--r-md);
		background: rgba(255, 255, 255, 0.035);
		border: 1px solid var(--line);
	}
	.grow {
		flex: 1;
		display: grid;
	}
	.btn.mini {
		min-height: 2.2rem;
		padding: 0.2rem 0.85rem;
		font-size: 0.85rem;
	}
</style>
