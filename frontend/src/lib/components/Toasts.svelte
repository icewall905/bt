<script lang="ts">
	import { toasts } from '$lib/stores/toast.svelte';
	import { focusable } from '$lib/nav';

	const ICON: Record<string, string> = { info: '💬', success: '✅', error: '⚠️', warn: '⏳' };
</script>

<div class="toasts" aria-live="polite" data-nav-noscroll>
	{#each toasts.items as t (t.id)}
		<div class="toast glass {t.kind}" role="status">
			<span class="ico" aria-hidden="true">{ICON[t.kind]}</span>
			<span class="msg">{t.message}</span>
			{#if t.action}
				<button
					class="btn small primary"
					use:focusable={{
						scroll: 'none',
						onSelect: () => {
							t.action?.run();
							toasts.dismiss(t.id);
						}
					}}>{t.action.label}</button
				>
			{/if}
		</div>
	{/each}
</div>

<style>
	.toasts {
		position: fixed;
		z-index: 900;
		left: 50%;
		bottom: clamp(1rem, 3vh, 2.5rem);
		transform: translateX(-50%);
		display: grid;
		gap: 0.6rem;
		width: min(92vw, 34rem);
		pointer-events: none;
	}
	.toast {
		pointer-events: auto;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.8rem 1rem 0.8rem 1.1rem;
		border-radius: var(--r-md);
		box-shadow: var(--shadow-lg);
		background: var(--toast-surface);
		animation: rise 0.3s var(--ease);
		font-weight: 550;
	}
	.toast.error {
		border-color: rgba(255, 92, 122, 0.5);
	}
	.toast.success {
		border-color: rgba(61, 220, 151, 0.45);
	}
	.msg {
		flex: 1;
	}
	.btn.small {
		min-height: 2.1rem;
		padding: 0.3rem 0.9rem;
	}
</style>
