// Editable copy of one settings key with dirty tracking + save.
import { api } from '../api';
import { session } from '../stores/session.svelte';
import { toast } from '../stores/toast.svelte';
import type { Settings } from '../types';

export class SettingsDraft<K extends keyof Omit<Settings, 'cookies'>> {
	value = $state({} as Settings[K]);
	saved = $state('');
	busy = $state(false);
	dirty = $derived(JSON.stringify(this.value) !== this.saved);

	constructor(public key: K) {
		this.reset();
	}

	reset() {
		const cur = session.settings?.[this.key];
		this.value = structuredClone($state.snapshot(cur ?? ({} as Settings[K]))) as Settings[K];
		this.saved = JSON.stringify(this.value);
	}

	async save(message = 'Saved') {
		this.busy = true;
		try {
			const res = await api.saveSettings(this.key, $state.snapshot(this.value) as Settings[K]);
			if (session.settings) session.settings = { ...session.settings, [this.key]: res };
			this.value = structuredClone(res) as Settings[K];
			this.saved = JSON.stringify(this.value);
			toast.success(message);
		} finally {
			this.busy = false;
		}
	}
}
