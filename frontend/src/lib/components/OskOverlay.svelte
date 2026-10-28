<script lang="ts">
	import { osk, navScope } from '$lib/nav';
	import Keyboard from './Keyboard.svelte';

	const multiline = $derived(osk.target instanceof HTMLTextAreaElement);
	const secret = $derived(osk.target instanceof HTMLInputElement && osk.target.type === 'password');
</script>

{#if osk.target}
	<div class="osk-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && osk.close()}>
		<div class="osk glass" role="dialog" aria-label={osk.label} use:navScope={{ onBack: () => osk.close() }}>
			<div class="label">{osk.label}</div>
			<div class="preview" class:multi={multiline}>
				{#if secret}{'•'.repeat(osk.value.length)}{:else}{osk.value}{/if}<span class="caret"></span>
			</div>
			<Keyboard
				name="osk-overlay"
				autofocus
				value={osk.value}
				onchange={(v) => osk.set(v)}
				onsubmit={() => osk.close(true)}
				submitLabel={multiline ? 'Done' : 'OK'}
			/>
			<p class="faint tiny hint">OK types the highlighted key. Back closes the keyboard.</p>
		</div>
	</div>
{/if}

<style>
	.osk-backdrop {
		position: fixed;
		inset: 0;
		z-index: 800;
		display: grid;
		align-items: end;
		justify-items: center;
		background: rgba(5, 4, 14, 0.5);
		padding: clamp(0.5rem, 2vw, 2rem);
	}
	.osk {
		width: min(100%, 56rem);
		border-radius: var(--r-lg);
		padding: clamp(0.9rem, 1.4vw, 1.6rem);
		display: grid;
		gap: 0.8rem;
		background: var(--keyboard-surface);
		box-shadow: var(--shadow-lg);
		animation: rise 0.25s var(--ease);
	}
	.label {
		font-weight: 600;
		color: var(--muted);
		font-size: 0.9rem;
	}
	.preview {
		min-height: 3rem;
		padding: 0.7rem 1rem;
		border-radius: var(--r-md);
		background: rgba(5, 4, 14, 0.6);
		border: 1px solid var(--line-strong);
		font-size: 1.25rem;
		white-space: pre;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.preview.multi {
		white-space: pre-wrap;
		max-height: 8rem;
		overflow: auto;
		font-size: 1.05rem;
	}
	.caret {
		display: inline-block;
		width: 2px;
		height: 1.2em;
		vertical-align: -0.2em;
		background: var(--accent);
		margin-left: 2px;
		animation: pulse 1s steps(1) infinite;
	}
	.hint {
		text-align: center;
	}
</style>
