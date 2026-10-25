<script lang="ts">
	// "Save offline" / "Remove download" toggle (Ticket D cache).
	import { api } from '$lib/api';
	import { toast } from '$lib/stores/toast.svelte';
	import { focusable } from '$lib/nav';
	import type { DownloadStatus } from '$lib/types';

	interface Props {
		videoId: string;
		/** finished local copy */
		offline?: boolean;
		/** full status when known (video detail) */
		status?: DownloadStatus | null;
		progress?: number;
		group?: string;
		size?: 'small' | 'normal';
	}
	let { videoId, offline = false, status = null, progress = 0, group, size = 'small' }: Props = $props();
	// svelte-ignore state_referenced_locally
	let st = $state<DownloadStatus | 'none'>(status ?? (offline ? 'done' : 'none'));
	let busy = $state(false);
	const saved = $derived(st === 'done' || st === 'queued' || st === 'downloading');

	async function toggle() {
		if (busy) return;
		busy = true;
		try {
			if (saved) {
				await api.removeDownload(videoId);
				st = 'evicted';
				toast.success('Download removed');
			} else {
				await api.saveOffline(videoId);
				st = 'queued';
				toast.success('Saving offline. It downloads in the background.');
			}
		} finally {
			busy = false;
		}
	}
	const label = $derived(
		st === 'done' ? 'Remove download' : st === 'downloading' ? `Downloading ${Math.round(progress * 100)}%, cancel` : st === 'queued' ? 'Queued, cancel' : 'Save offline'
	);
</script>

<button class="btn off {size}" class:on={st === 'done'} aria-label={label} use:focusable={{ group, onSelect: toggle }}>
	<span aria-hidden="true">{st === 'done' ? '✓' : '⤓'}</span>
	<span>{label}</span>
</button>

<style>
	.off.small {
		min-height: 2.1rem;
		padding: 0.3rem 0.85rem;
		font-size: 0.82rem;
	}
	.off.on {
		border-color: rgba(61, 220, 151, 0.5);
		color: #b9f5d8;
	}
</style>
