<script lang="ts">
	import { api } from '$lib/api';
	import { dialogs } from '$lib/stores/dialogs.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { focusable } from '$lib/nav';
	import Modal from './Modal.svelte';
	import TextField from './form/TextField.svelte';

	const t = $derived(dialogs.feedback!);
	// svelte-ignore state_referenced_locally
	let rating = $state<number | null>(dialogs.feedback?.rating ?? null);
	let chips = $state<string[]>([]);
	let text = $state('');
	let busy = $state(false);

	const RATINGS = [
		{ v: 2, emoji: '❤️', label: 'Loved it' },
		{ v: 1, emoji: '👍', label: 'Good' },
		{ v: 0, emoji: '📝', label: 'Just a note' },
		{ v: -1, emoji: '👎', label: 'Not for us' }
	];
	const CHIPS = ['Boring', 'Mean/cruel', 'Too long', 'Clickbait', 'Too basic', 'Too hard', 'Too babyish', 'Loud/annoying', 'Scary', 'Loved it', 'More like this'];
	const cat = $derived(session.categoryById(t?.categoryId));

	function toggle(c: string) {
		chips = chips.includes(c) ? chips.filter((x) => x !== c) : [...chips, c];
	}
	const close = () => (dialogs.feedback = null);

	async function send() {
		if (rating == null && !chips.length && !text.trim()) return toast.warn('Pick a rating, a chip or write a note.');
		busy = true;
		try {
			await api.feedback({ video_id: t.videoId, category_id: t.categoryId ?? null, rating: rating ?? 0, chips, text: text.trim() });
			toast.success(rating != null && rating < 0 ? 'Thanks. The AI will avoid videos like this.' : 'Thanks. The AI will learn from this.');
			const done = t.onDone;
			close();
			done?.(rating ?? 0);
		} finally {
			busy = false;
		}
	}
</script>

<Modal title={t.heading ?? 'How was it?'} subtitle={t.title} size="md" onClose={close}>
	<div class="stack">
		<div class="ratings">
			{#each RATINGS as r}
				<button class="rate" class:on={rating === r.v} aria-pressed={rating === r.v} use:focusable={{ group: 'fb-rate', autofocus: r.v === (rating ?? 1), onSelect: () => (rating = r.v) }}>
					<span class="e">{r.emoji}</span>
					<span>{r.label}</span>
				</button>
			{/each}
		</div>
		<div class="chips">
			{#each CHIPS as c, i}
				<button class="chip" class:on={chips.includes(c)} aria-pressed={chips.includes(c)} use:focusable={{ group: `fb-chips-${Math.floor(i / 5)}`, onSelect: () => toggle(c) }}>{c}</button>
			{/each}
		</div>
		<TextField multiline rows={3} label="Anything else? (optional)" placeholder="e.g. Fun experiment but he was mean to the cat" bind:value={text} />
		<p class="learn small">
			<span aria-hidden="true">🧠</span>
			The AI will learn from this{cat ? ` for ${cat.emoji} ${cat.name}` : ''}: it turns feedback into short rules it follows when picking new videos. You can see and edit them under Settings, Memory.
		</p>
	</div>
	{#snippet footer()}
		<button class="btn" use:focusable={{ onSelect: close }}>Skip</button>
		<button class="btn primary" disabled={busy} use:focusable={{ id: 'fb-send', onSelect: send }}>Send feedback</button>
	{/snippet}
</Modal>

<style>
	.ratings {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 0.6rem;
	}
	.rate {
		--focus-scale: 1.07;
		display: grid;
		justify-items: center;
		gap: 0.3rem;
		padding: 0.9rem 0.4rem;
		border-radius: var(--r-md);
		border: 1px solid var(--line);
		background: rgba(255, 255, 255, 0.04);
		cursor: pointer;
		font-weight: 600;
		font-size: 0.88rem;
	}
	.rate .e {
		font-size: 2rem;
	}
	.rate.on {
		border-color: var(--accent);
		background: rgba(255, 181, 71, 0.14);
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	.learn {
		display: flex;
		gap: 0.6rem;
		padding: 0.75rem 0.9rem;
		border-radius: var(--r-md);
		background: rgba(157, 134, 255, 0.1);
		border: 1px solid rgba(157, 134, 255, 0.25);
		color: #d9d0ff;
	}
</style>
