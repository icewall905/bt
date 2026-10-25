<script lang="ts">
	import { focusable } from '$lib/nav';

	interface Props {
		checked: boolean;
		label: string;
		hint?: string;
		group?: string;
		id?: string;
		onchange?: (v: boolean) => void;
	}
	let { checked = $bindable(false), label, hint, group, id, onchange }: Props = $props();
</script>

<button
	class="toggle"
	role="switch"
	aria-checked={checked}
	use:focusable={{
		group,
		id,
		onSelect: () => {
			checked = !checked;
			onchange?.(checked);
		}
	}}
>
	<span class="text">
		<span class="lbl">{label}</span>
		{#if hint}<span class="hint">{hint}</span>{/if}
	</span>
	<span class="track" class:on={checked}><span class="knob"></span></span>
</button>

<style>
	.toggle {
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
	.toggle:hover {
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
	.track {
		flex: none;
		width: 3.1rem;
		height: 1.75rem;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.14);
		position: relative;
		transition: background 0.2s var(--ease);
	}
	.track.on {
		background: var(--ok);
	}
	.knob {
		position: absolute;
		top: 0.2rem;
		left: 0.2rem;
		width: 1.35rem;
		height: 1.35rem;
		border-radius: 50%;
		background: #fff;
		box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
		transition: transform 0.25s var(--ease-spring);
	}
	.track.on .knob {
		transform: translateX(1.35rem);
	}
</style>
