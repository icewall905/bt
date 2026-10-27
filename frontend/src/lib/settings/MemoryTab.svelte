<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { session } from '$lib/stores/session.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { focusable } from '$lib/nav';
	import { timeAgo, isVideo } from '$lib/util';
	import type { Feedback, Lesson } from '$lib/types';
	import Section from './Section.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import Select from '$lib/components/form/Select.svelte';

	let lessons = $state<Lesson[] | null>(null);
	let feedback = $state<Feedback[] | null>(null);
	let draft = $state('');
	let draftCat = $state<number>(0);
	let editing = $state<number | null>(null);
	let editText = $state('');

	async function load() {
		[lessons, feedback] = await Promise.all([api.lessons().catch(() => []), api.feedbackList(100).catch(() => [])]);
	}
	onMount(load);

	const catOptions = $derived([{ value: 0, label: 'All my playlists' }, ...session.categories.map((c) => ({ value: c.id, label: `${c.emoji} ${c.name}` }))]);
	const catLabel = (id: number | null) => {
		const c = session.categoryById(id);
		return c ? `${c.emoji} ${c.name}` : 'All playlists';
	};

	async function add() {
		if (!draft.trim()) return;
		await api.createLesson({ text: draft.trim(), category_id: draftCat || null });
		draft = '';
		toast.success('Rule added. The AI follows it from the next video on.');
		load();
	}
	async function toggle(l: Lesson) {
		await api.updateLesson(l.id, { active: !l.active });
		l.active = !l.active;
	}
	async function saveEdit(l: Lesson) {
		await api.updateLesson(l.id, { text: editText.trim() });
		l.text = editText.trim();
		editing = null;
		toast.success('Rule updated');
	}
	async function del(l: Lesson) {
		await api.deleteLesson(l.id);
		lessons = (lessons ?? []).filter((x) => x.id !== l.id);
	}
	async function delFb(f: Feedback) {
		await api.deleteFeedback(f.id);
		feedback = (feedback ?? []).filter((x) => x.id !== f.id);
	}
	const RATING: Record<number, string> = { [-1]: '👎', 0: '📝', 1: '👍', 2: '❤️' };
</script>

<Section title="AI memory" intro="Rules the AI learned from your feedback, plus any you add yourself. Every rule is included when the AI plans searches and judges videos for {session.profile?.name ?? 'this profile'}.">
	<div class="add panel">
		<TextField label="Teach the AI a rule" bind:value={draft} placeholder="e.g. Avoid videos where people shout at each other" onsubmit={add} group="lesson-add" />
		<div class="row">
			<div class="grow"><Select label="Applies to" bind:value={draftCat} options={catOptions} group="lesson-add2" /></div>
			<button class="btn primary" use:focusable={{ group: 'lesson-add2', onSelect: add }}>Add rule</button>
		</div>
	</div>

	{#if lessons === null}
		<div class="skeleton" style="height:8rem"></div>
	{:else if lessons.length === 0}
		<p class="muted">No rules yet. Rate a few videos (👍 👎 📝 in the player) and the AI will distil them into rules here.</p>
	{:else}
		<div class="lessons">
			{#each lessons as l (l.id)}
				<div class="lesson" class:off={!l.active}>
					{#if editing === l.id}
						<div class="grow"><TextField bind:value={editText} multiline rows={2} group="l-edit-{l.id}" /></div>
						<button class="btn mini primary" use:focusable={{ group: `l-${l.id}`, onSelect: () => saveEdit(l) }}>Save</button>
						<button class="btn mini" use:focusable={{ group: `l-${l.id}`, onSelect: () => (editing = null) }}>Cancel</button>
					{:else}
						<div class="grow">
							<p class="lt">{l.text}</p>
							<p class="small faint">{catLabel(l.category_id)}{l.channel_id ? ', one channel' : ''}. Weight {l.weight.toFixed(1)}. Updated {timeAgo(l.updated_at)}.</p>
						</div>
						<button class="btn mini" use:focusable={{ group: `l-${l.id}`, onSelect: () => toggle(l) }}>{l.active ? 'Active' : 'Paused'}</button>
						<button class="btn mini" use:focusable={{ group: `l-${l.id}`, onSelect: () => ((editing = l.id), (editText = l.text)) }}>Edit</button>
						<button class="btn mini danger" aria-label="Delete rule" use:focusable={{ group: `l-${l.id}`, onSelect: () => del(l) }}>Delete</button>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</Section>

<div style="height:2rem"></div>

<Section title="Feedback history" intro="What you told the AI. Deleting feedback does not delete rules it already learned.">
	{#if feedback === null}
		<div class="skeleton" style="height:6rem"></div>
	{:else if feedback.length === 0}
		<p class="muted">No feedback yet.</p>
	{:else}
		<div class="lessons">
			{#each feedback as f (f.id)}
				<div class="lesson">
					<span class="r">{RATING[f.rating] ?? '•'}</span>
					<div class="grow">
						<p class="lt">{isVideo(f.video) ? f.video.title : f.video_id}</p>
						<p class="small muted">
							{[...(f.chips ?? []), f.text].filter(Boolean).join('. ') || 'No comment'}
						</p>
						<p class="tiny faint">{catLabel(f.category_id)}, {timeAgo(f.created_at)}{f.processed ? ', learned' : ', waiting for the AI'}</p>
					</div>
					<button class="btn mini danger" use:focusable={{ group: `fb-${f.id}`, onSelect: () => delFb(f) }}>Delete</button>
				</div>
			{/each}
		</div>
	{/if}
</Section>

<style>
	.add {
		display: grid;
		gap: 0.8rem;
	}
	.row {
		display: flex;
		gap: 0.8rem;
		align-items: center;
		flex-wrap: wrap;
	}
	.grow {
		flex: 1;
		min-width: min(100%, 14rem);
	}
	.lessons {
		display: grid;
		gap: 0.5rem;
	}
	.lesson {
		display: flex;
		gap: 0.7rem;
		align-items: center;
		padding: 0.8rem 0.9rem;
		border-radius: var(--r-md);
		background: rgba(255, 255, 255, 0.035);
		border: 1px solid var(--line);
		flex-wrap: wrap;
	}
	.lesson.off {
		opacity: 0.55;
	}
	.lt {
		font-weight: 600;
	}
	.r {
		font-size: 1.5rem;
	}
	.btn.mini {
		min-height: 2.2rem;
		padding: 0.2rem 0.85rem;
		font-size: 0.85rem;
	}
</style>
