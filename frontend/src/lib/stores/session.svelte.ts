// App-wide session: auth, profiles, active profile, cached categories + settings.
import { api, PROFILE_KEY, onUnauthorized } from '../api';
import { thumbnailPreference } from './thumbnailPreference.svelte';
import type { Category, Profile, Settings } from '../types';

class Session {
	ready = $state(false);
	authRequired = $state(false);
	authenticated = $state(true);
	profiles = $state<Profile[]>([]);
	profileId = $state<number | null>(null);
	/** Show the full-screen "Who's watching?" picker. */
	choosing = $state(false);
	categories = $state<Category[]>([]);
	settings = $state<Settings | null>(null);
	/** Bumped whenever the active profile changes: pages re-fetch on change. */
	version = $state(0);

	profile = $derived(this.profiles.find((p) => p.id === this.profileId) ?? null);
	needsLogin = $derived(this.authRequired && !this.authenticated);

	constructor() {
		onUnauthorized(() => {
			this.authRequired = true;
			this.authenticated = false;
		});
	}

	async init() {
		try {
			const st = await api.authStatus();
			this.authRequired = st.required;
			this.authenticated = st.authenticated;
		} catch {
			/* server unreachable: keep going, pages will show errors */
		}
		if (!this.needsLogin) await this.loadAll(true);
		this.ready = true;
	}

	async loadAll(firstLaunch = false) {
		await this.loadProfiles();
		let stored: number | null = null;
		try {
			const raw = localStorage.getItem(PROFILE_KEY);
			stored = raw ? Number(raw) : null;
		} catch {
			/* ignore */
		}
		const valid = this.profiles.find((p) => p.id === stored);
		if (valid) this.profileId = valid.id;
		else {
			this.profileId = this.profiles[0]?.id ?? null;
			this.persist();
			if (firstLaunch && this.profiles.length > 1) this.choosing = true;
		}
		await Promise.all([this.loadCategories(), this.loadSettings()]);
	}

	async loadProfiles() {
		try {
			this.profiles = await api.profiles();
		} catch {
			this.profiles = [];
		}
	}

	async loadCategories() {
		try {
			this.categories = await api.categories();
		} catch {
			this.categories = [];
		}
	}

	async loadSettings() {
		try {
			this.settings = await api.settings();
			thumbnailPreference.dearrow = !!this.settings.extras.dearrow_thumbnails;
		} catch {
			/* keep previous */
		}
	}

	private persist() {
		try {
			if (this.profileId != null) localStorage.setItem(PROFILE_KEY, String(this.profileId));
		} catch {
			/* ignore */
		}
	}

	async switchProfile(id: number) {
		this.choosing = false;
		if (id === this.profileId) return;
		this.profileId = id;
		this.persist();
		await this.loadCategories();
		this.version++;
	}

	async afterLogin() {
		this.authenticated = true;
		await this.loadAll(true);
		this.version++;
	}

	categoryById(id: number | null | undefined): Category | undefined {
		return id == null ? undefined : this.categories.find((c) => c.id === id);
	}
}

export const session = new Session();
