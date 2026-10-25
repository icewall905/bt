<script lang="ts">
	import { focusable } from '$lib/nav';

	interface Props {
		value: string;
		onchange: (v: string) => void;
		onsubmit?: () => void;
		submitLabel?: string;
		/** id prefix so several keyboards don't share focus memory */
		name?: string;
		autofocus?: boolean;
	}
	let { value, onchange, onsubmit, submitLabel = 'Done', name = 'osk', autofocus = false }: Props = $props();

	let shift = $state(false);
	let symbols = $state(false);

	const LETTERS = ['abcdefghij', 'klmnopqrst', 'uvwxyz-\'.?'];
	const SYMBOLS = ['!@#$%&*()_', '+=/\\:;"<>[', ']{},~`^|€£'];
	const rows = $derived((symbols ? SYMBOLS : LETTERS).map((r) => [...r].map((c) => (shift && !symbols ? c.toUpperCase() : c))));

	function type(c: string) {
		onchange(value + c);
		if (shift) shift = false;
	}
</script>

<div class="kb" role="group" aria-label="On-screen keyboard">
	<div class="row">
		{#each [...'1234567890'] as d, i}
			<button class="key" use:focusable={{ group: `${name}-0`, id: `${name}-n${i}`, onSelect: () => type(d), scroll: 'nearest', memory: false }}>{d}</button>
		{/each}
	</div>
	{#each rows as row, r}
		<div class="row">
			{#each row as c, i}
				<button
					class="key"
					use:focusable={{ group: `${name}-${r + 1}`, id: `${name}-${r}-${i}`, autofocus: autofocus && r === 0 && i === 0, onSelect: () => type(c), scroll: 'nearest', memory: false }}
					>{c}</button
				>
			{/each}
		</div>
	{/each}
	<div class="row bottom">
		<button class="key wide" class:on={shift} aria-pressed={shift} use:focusable={{ group: `${name}-4`, onSelect: () => (shift = !shift), scroll: 'nearest', memory: false }}>⇧ Shift</button>
		<button class="key wide" class:on={symbols} aria-pressed={symbols} use:focusable={{ group: `${name}-4`, onSelect: () => (symbols = !symbols), scroll: 'nearest', memory: false }}>{symbols ? 'abc' : '#+='}</button>
		<button class="key space" use:focusable={{ group: `${name}-4`, onSelect: () => type(' '), scroll: 'nearest', memory: false }}>Space</button>
		<button class="key wide" aria-label="Backspace" use:focusable={{ group: `${name}-4`, onSelect: () => onchange(value.slice(0, -1)), scroll: 'nearest', memory: false }}>⌫</button>
		<button class="key wide" use:focusable={{ group: `${name}-4`, onSelect: () => onchange(''), scroll: 'nearest', memory: false }}>Clear</button>
		{#if onsubmit}
			<button class="key wide go" use:focusable={{ group: `${name}-4`, onSelect: onsubmit, scroll: 'nearest', memory: false }}>{submitLabel}</button>
		{/if}
	</div>
</div>

<style>
	.kb {
		display: grid;
		gap: 0.45rem;
		user-select: none;
	}
	.row {
		display: grid;
		grid-template-columns: repeat(10, 1fr);
		gap: 0.45rem;
	}
	.row.bottom {
		display: flex;
	}
	.key {
		--focus-scale: 1.14;
		min-height: clamp(2.4rem, 2.6vw + 0.6rem, 3.4rem);
		border-radius: var(--r-sm);
		border: 1px solid var(--line);
		background: rgba(255, 255, 255, 0.06);
		font-size: 1.1rem;
		font-weight: 600;
		cursor: pointer;
		padding: 0 0.3rem;
	}
	.key:hover {
		background: rgba(255, 255, 255, 0.12);
	}
	.key.wide {
		flex: 1.2;
		font-size: 0.9rem;
	}
	.key.space {
		flex: 3;
		font-size: 0.9rem;
	}
	.key.on {
		background: var(--surface-hi);
		border-color: var(--accent);
	}
	.key.go {
		background: var(--accent);
		color: var(--accent-ink);
		flex: 1.6;
	}
	:global(html[data-modality='keys']) .key:focus {
		background: var(--accent);
		color: var(--accent-ink);
	}
</style>
