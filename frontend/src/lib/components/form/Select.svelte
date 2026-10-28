<script lang="ts" generics="T extends string | number">
	import { focusable } from '$lib/nav';
	import Modal from '../Modal.svelte';

	interface Props {
		value: T;
		options: { value: T; label: string; hint?: string }[];
		label: string;
		hint?: string;
		group?: string;
		id?: string;
		onchange?: (v: T) => void;
	}
	let { value = $bindable(), options, label, hint, group, id, onchange }: Props = $props();
	let open = $state(false);
	const current = $derived(options.find((o) => o.value === value));

	function pick(v: T) {
		value = v;
		open = false;
		onchange?.(v);
	}
</script>

<button class="select" aria-haspopup="listbox" use:focusable={{ group, id, onSelect: () => (open = true) }}>
	<span class="text">
		<span class="lbl">{label}</span>
		{#if hint}<span class="hint">{hint}</span>{/if}
	</span>
	<span class="val">{current?.label ?? String(value ?? '')}</span>
	<span class="chev" aria-hidden="true">▾</span>
</button>

{#if open}
	<Modal title={label} size="sm" portal onClose={() => (open = false)}>
		<div class="opts" role="listbox">
			{#each options as o}
				<button
					class="opt"
					role="option"
					aria-selected={o.value === value}
					class:sel={o.value === value}
					use:focusable={{ autofocus: o.value === value, onSelect: () => pick(o.value) }}
				>
					<span>{o.label}</span>
					{#if o.hint}<span class="hint">{o.hint}</span>{/if}
				</button>
			{/each}
		</div>
	</Modal>
{/if}

<style>
	.select {
		--focus-scale: 1.02;
		display: flex;
		align-items: center;
		gap: 1rem;
		width: 100%;
		text-align: left;
		padding: 0.75rem 1rem;
		border-radius: var(--r-md);
		border: 1px solid var(--line);
		background: rgba(255, 255, 255, 0.03);
		cursor: pointer;
	}
	.select:hover {
		background: rgba(255, 255, 255, 0.07);
	}
	.text {
		flex: 1;
		display: grid;
		gap: 0.15rem;
	}
	.lbl {
		font-weight: 600;
	}
	.hint {
		font-size: 0.8rem;
		color: var(--faint);
	}
	.val {
		color: var(--accent);
		font-weight: 600;
	}
	.chev {
		color: var(--muted);
	}
	.opts {
		display: grid;
		gap: 0.4rem;
	}
	.opt {
		--focus-scale: 1.03;
		display: grid;
		text-align: left;
		gap: 0.1rem;
		padding: 0.75rem 1rem;
		border-radius: var(--r-md);
		border: 1px solid var(--line);
		background: rgba(255, 255, 255, 0.04);
		cursor: pointer;
		font-weight: 600;
	}
	.opt.sel {
		border-color: var(--accent);
	}
	.opt:hover {
		background: rgba(255, 255, 255, 0.09);
	}
</style>
