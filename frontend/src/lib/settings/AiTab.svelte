<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { focusable } from '$lib/nav';
	import { agent, STATE_LABEL } from '$lib/stores/agent.svelte';
	import type { LlmTestResult, ProxyProvider, ProxyTestResult } from '$lib/types';
	import Section from './Section.svelte';
	import SaveBar from './SaveBar.svelte';
	import { SettingsDraft } from './useSettings.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import Select from '$lib/components/form/Select.svelte';
	import Toggle from '$lib/components/form/Toggle.svelte';
	import Slider from '$lib/components/form/Slider.svelte';
	import Stepper from '$lib/components/form/Stepper.svelte';

	const llm = new SettingsDraft('llm');
	const ag = new SettingsDraft('agent');
	const th = new SettingsDraft('throttle');

	let testing = $state(false);
	let result = $state<LlmTestResult | null>(null);
	let tookMs = $state(0);

	async function test() {
		testing = true;
		result = null;
		const t0 = performance.now();
		try {
			result = await api.llmTest({ base_url: llm.value.base_url, model: llm.value.model, api_key: llm.value.api_key });
		} catch (e) {
			result = { ok: false, error: (e as Error).message };
		} finally {
			tookMs = Math.round(performance.now() - t0);
			testing = false;
		}
	}

	const mins = (s: number) => (s >= 3600 ? `${(s / 3600).toFixed(s % 3600 ? 1 : 0)} h` : s >= 60 ? `${Math.round(s / 60)} min` : `${s} s`);
	const perHourAvg = $derived(Math.round(3600 / Math.max(1, (th.value.min_delay_s + th.value.max_delay_s) / 2)));

	// ---- YouTube proxy helpers ---------------------------------------------
	const PROVIDERS = [
		{ value: 'direct', label: 'Direct' },
		{ value: 'pia', label: 'PIA' },
		{ value: 'local', label: 'Local VPN' },
		{ value: 'custom', label: 'Custom' }
	] as const;
	const catalog = $state<Record<string, ProxyProvider | undefined>>({});
	const px = $state({ provider: 'direct', user: '', pass: '', scheme: 'http', host: '', port: '8000', custom: '' });

	onMount(async () => {
		try {
			const { providers } = await api.proxyProviders();
			for (const p of providers) catalog[p.id] = p;
		} catch {
			// the picker still works without the region lists
		}
	});

	/** Which helper + fields correspond to a stored proxy URL (credentials come back masked). */
	function parseProxy(url: string) {
		px.provider = 'direct';
		px.user = px.pass = px.host = px.custom = '';
		px.scheme = 'http';
		px.port = '8000';
		if (!url) return;
		px.provider = 'custom';
		px.custom = url;
		try {
			const u = new URL(url);
			px.user = decodeURIComponent(u.username || '');
			px.pass = decodeURIComponent(u.password || '');
			const h = u.hostname || '';
			if (h.endsWith('.privateinternetaccess.com')) {
				px.provider = 'pia';
				px.custom = '';
			}
		} catch {
			/* not a parseable URL: keep it as the raw custom value */
		}
	}

	/** Build the URL for the selected provider. Empty string = direct. */
	function composeProxy(): string {
		switch (px.provider) {
			case 'pia':
				// PIA has a single SOCKS5 proxy, exiting in the Netherlands
				return px.user && px.pass
					? `socks5://${encodeURIComponent(px.user)}:${encodeURIComponent(px.pass)}@proxy-nl.privateinternetaccess.com:1080`
					: '';
			case 'local':
				return px.host ? `${px.scheme}://${px.host.trim()}:${px.port.trim() || '8000'}` : '';
			case 'custom':
				return px.custom.trim();
			default:
				return '';
		}
	}

	parseProxy(th.value.proxy ?? '');

	$effect(() => {
		th.value.proxy = composeProxy();
	});

	function pickProvider(p: string) {
		px.provider = p;
		if (p === 'local' && !px.port) px.port = '8000';
	}

	let proxyTesting = $state(false);
	let proxyResult = $state<ProxyTestResult | null>(null);
	let proxyMs = $state(0);

	async function testProxy() {
		const url = th.value.proxy?.trim();
		if (!url) {
			proxyResult = { ok: false, error: 'Nothing to test yet — fill in the proxy details first.' };
			return;
		}
		proxyTesting = true;
		proxyResult = null;
		const t0 = performance.now();
		try {
			proxyResult = await api.proxyTest(url);
		} catch (e) {
			proxyResult = { ok: false, error: (e as Error).message };
		} finally {
			proxyMs = Math.round(performance.now() - t0);
			proxyTesting = false;
		}
	}

	async function saveThrottle() {
		await th.save('Limits saved');
		parseProxy(th.value.proxy ?? ''); // credentials come back masked after saving
	}
</script>

<Section title="AI model" intro="BetterTube talks to any OpenAI-compatible server: llama.cpp, Ollama, vLLM, LM Studio or a hosted API. The model reads transcripts and comments, so a long context window helps.">
	<div class="conn panel">
		<TextField label="Server URL" hint="Ends in /v1 for most servers." bind:value={llm.value.base_url} placeholder="http://10.0.10.23:8080/v1" type="url" group="llm-url" id="llm-url" />
		<div class="two">
			<TextField label="Model" hint="Pick one from the test results below, or type its name." bind:value={llm.value.model} placeholder="currentmodel" group="llm-model" />
			<TextField label="API key" hint="Leave empty for local servers. Stored on the server, never shown again." type="password" bind:value={llm.value.api_key} placeholder="none" group="llm-model" />
		</div>
		<div class="test-row">
			<button class="btn primary big" disabled={testing} use:focusable={{ group: 'llm-test', id: 'llm-test', onSelect: test }}>
				{#if testing}<span class="spin"></span> Testing…{:else}Test connection{/if}
			</button>
			<p class="small faint">Lists the server's models and asks the selected model to reply "pong". Uses the values above, even before you save.</p>
		</div>
		{#if result}
			<div class="result" class:ok={result.ok} class:bad={!result.ok} role="status">
				{#if result.ok}
					<div class="rh"><span class="big">✓</span><div><strong>Connected</strong><div class="small muted">Answered in {(tookMs / 1000).toFixed(1)} s</div></div></div>
					<div class="reply"><span class="small faint">Model replied</span><code>{result.reply || '(empty reply)'}</code></div>
				{:else}
					<div class="rh"><span class="big">✕</span><div><strong>Could not reach the model</strong><div class="small muted">After {(tookMs / 1000).toFixed(1)} s</div></div></div>
					<code class="err">{result.error}</code>
					<p class="small muted">Check the URL (including /v1), that the server is running and reachable from the BetterTube container, and the model name.</p>
				{/if}
				{#if result.models?.length}
					<div class="models">
						<span class="small faint">Models on this server (select to use)</span>
						<div class="hstack">
							{#each result.models as m}
								<button class="chip" class:on={m === llm.value.model} use:focusable={{ group: 'llm-models', onSelect: () => (llm.value.model = m) }}>{m}</button>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>
	<div class="one">
		<Toggle label="Model can see images" hint="Send each thumbnail to the model too. Turn off for text-only models." bind:checked={llm.value.vision} />
		<Stepper label="Timeout" hint="How long to wait for one answer." bind:value={llm.value.timeout_s} min={30} max={1800} step={30} format={(v) => mins(v)} />
	</div>
	<Slider label="Creativity" hint="Temperature. Low keeps verdicts consistent; higher gives more varied search ideas." bind:value={llm.value.temperature} min={0} max={1.5} step={0.05} format={(v) => v.toFixed(2)} />
	<SaveBar dirty={llm.dirty} busy={llm.busy} onsave={() => llm.save('AI model settings saved')} onreset={() => llm.reset()} />
</Section>

<div class="gap"></div>

<Section title="Curator" intro="The background worker that searches, reads and judges videos for every profile's categories.">
	<div class="status small muted">Right now: <strong>{STATE_LABEL[agent.effective] ?? agent.effective}</strong>{agent.state.detail ? `, ${agent.state.detail}` : ''}</div>
	<Toggle label="Curator enabled" hint="Off stops all background searching. Search and playback keep working. For a short break use Pause AI in the top bar instead." bind:checked={ag.value.enabled} />
	<SaveBar dirty={ag.dirty} busy={ag.busy} onsave={() => ag.save(ag.value.enabled ? 'Curator enabled' : 'Curator disabled')} onreset={() => ag.reset()} />
</Section>

<div class="gap"></div>

<Section title="Pace and limits" intro="YouTube blocks servers that make too many requests. These limits keep the curator slow and polite. Your own searches and playback are not limited by them.">
	<div class="explain panel small">
		With these settings the curator makes at most <strong>{th.value.max_per_hour}</strong> YouTube requests an hour (on average about {Math.min(perHourAvg, th.value.max_per_hour)}), and
		<strong>{th.value.max_per_day}</strong> a day. If YouTube shows a bot check, it stops for {mins(th.value.backoff_min_s)} at first, up to {mins(th.value.backoff_max_s)} if it keeps happening.
	</div>
	<div class="one">
		<Stepper label="Shortest pause between requests" hint="A random wait between this and the longest pause looks more human." bind:value={th.value.min_delay_s} min={2} max={600} step={5} format={mins} />
		<Stepper label="Longest pause between requests" bind:value={th.value.max_delay_s} min={5} max={1800} step={5} format={mins} />
		<Stepper label="Requests per hour" bind:value={th.value.max_per_hour} min={5} max={1000} step={5} />
		<Stepper label="Requests per day" bind:value={th.value.max_per_day} min={20} max={20000} step={50} />
		<Stepper label="First backoff after a bot check" bind:value={th.value.backoff_min_s} min={300} max={86400} step={900} format={mins} />
		<Stepper label="Longest backoff" bind:value={th.value.backoff_max_s} min={900} max={172800} step={1800} format={mins} />
	</div>
	<Toggle label="Pause while someone is watching" hint="Keeps the internet connection free for playback and avoids two kinds of YouTube traffic at once." bind:checked={th.value.pause_while_playing} />
	<TextField label="Quiet hours" hint='No curator work in this window, e.g. "01:00-07:00". Leave empty for none.' bind:value={th.value.quiet_hours} placeholder="01:00-07:00" group="quiet" />
	<div class="proxy panel">
		<div>
			<span class="small faint">Route all YouTube traffic through a proxy, so the IP YouTube sees is not this server's.</span>
			<div class="hstack">
				{#each PROVIDERS as p}
					<button class="chip" class:on={px.provider === p.value} use:focusable={{ group: 'px-prov', onSelect: () => pickProvider(p.value) }}>{p.label}</button>
				{/each}
			</div>
		</div>
		{#if catalog[px.provider]?.hint && px.provider !== 'direct'}
			<p class="small muted">{catalog[px.provider]?.hint}</p>
		{/if}
		{#if px.provider === 'pia'}
			<div class="two">
				<TextField label="SOCKS5 username" bind:value={px.user} placeholder="generated in the panel" group="px" />
				<TextField label="SOCKS5 password" hint="Not your PIA login — generate these under Downloads → VPN Settings → SOCKS." type="password" bind:value={px.pass} group="px" />
			</div>
			<p class="small muted">The proxy exits in the Netherlands (PIA's only SOCKS5 location).</p>
		{:else if px.provider === 'local'}
			<div class="two">
				<Select label="Type" bind:value={px.scheme} group="px" options={[{ value: 'http', label: 'HTTP' }, { value: 'socks5', label: 'SOCKS5' }]} />
				<TextField label="Host" hint="On this server's network, e.g. the gluetun container." bind:value={px.host} placeholder="gluetun" group="px" />
				<TextField label="Port" bind:value={px.port} placeholder="8000" group="px" />
			</div>
		{:else if px.provider === 'custom'}
			<TextField label="Proxy URL" hint="Any http(s) or socks5 URL. Saved credentials are never shown again." bind:value={px.custom} type="password" placeholder="socks5://user:pass@host:1080" group="px" />
		{:else}
			<p class="small muted">All YouTube requests go straight out from this server. That is the default and works fine at these request rates.</p>
		{/if}
		<div class="test-row">
			<button class="btn" disabled={proxyTesting || !th.value.proxy} use:focusable={{ group: 'px-test', id: 'px-test', onSelect: testProxy }}>
				{#if proxyTesting}<span class="spin"></span> Testing…{:else}Test this proxy{/if}
			</button>
			<p class="small faint">Fetches one YouTube channel feed through the proxy using the values above, before you save. Counts as one YouTube request.</p>
		</div>
		{#if proxyResult}
			<div class="result" class:ok={proxyResult.ok} class:bad={!proxyResult.ok} role="status">
				{#if proxyResult.ok}
					<div class="rh"><span class="big">✓</span><div><strong>Works</strong><div class="small muted">YouTube answered in {(proxyMs / 1000).toFixed(1)} s through this proxy.</div></div></div>
				{:else}
					<div class="rh"><span class="big">✕</span><div><strong>Could not use this proxy</strong></div></div>
					{#if proxyResult.error}<code class="err">{proxyResult.error}</code>{/if}
					{#if proxyResult.hint}<p class="small muted">{proxyResult.hint}</p>{/if}
				{/if}
			</div>
		{/if}
	</div>
	<div class="one">
		<Stepper label="Results per search" hint="How many videos the AI looks at per search." bind:value={th.value.search_results} min={5} max={50} step={1} />
		<Stepper label="Comments to read" hint="Top comments often reveal what a video is really like." bind:value={th.value.max_comments} min={0} max={200} step={5} />
		<Stepper label="Transcript length" hint="Longer gives the AI more to judge with, but is slower." bind:value={th.value.transcript_max_chars} min={2000} max={200000} step={2000} format={(v) => `${Math.round(v / 1000)}k chars`} />
	</div>
	<SaveBar dirty={th.dirty} busy={th.busy} onsave={saveThrottle} onreset={() => { th.reset(); parseProxy(th.value.proxy ?? ''); }} />
</Section>

<style>
	.conn {
		display: grid;
		gap: 1rem;
	}
	.two {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr));
		gap: 0.9rem;
	}
	/* Steppers use Left/Right to change values, so they sit in one column: Up/Down reaches every one. */
	.one {
		display: grid;
		gap: 0.75rem;
	}
	.proxy {
		display: grid;
		gap: 0.9rem;
	}
	.test-row {
		display: flex;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
	}
	.test-row p {
		flex: 1;
		min-width: 14rem;
	}
	.spin {
		width: 1em;
		height: 1em;
		border-radius: 50%;
		border: 2px solid currentColor;
		border-right-color: transparent;
		animation: spin 0.8s linear infinite;
	}
	.result {
		display: grid;
		gap: 0.9rem;
		padding: 1rem 1.1rem;
		border-radius: var(--r-md);
		animation: rise 0.25s var(--ease);
	}
	.result.ok {
		background: rgba(61, 220, 151, 0.08);
		border: 1px solid rgba(61, 220, 151, 0.4);
	}
	.result.bad {
		background: rgba(255, 92, 122, 0.08);
		border: 1px solid rgba(255, 92, 122, 0.45);
	}
	.rh {
		display: flex;
		align-items: center;
		gap: 0.8rem;
	}
	.rh .big {
		display: grid;
		place-items: center;
		width: 2.4rem;
		height: 2.4rem;
		border-radius: 50%;
		font-weight: 800;
		background: rgba(255, 255, 255, 0.08);
	}
	.ok .rh .big {
		color: var(--ok);
	}
	.bad .rh .big {
		color: var(--bad);
	}
	.reply {
		display: grid;
		gap: 0.25rem;
	}
	code {
		font-size: 0.9rem;
		padding: 0.5rem 0.7rem;
		border-radius: var(--r-sm);
		background: rgba(0, 0, 0, 0.3);
		white-space: pre-wrap;
		word-break: break-word;
	}
	.err {
		color: #ffc2cd;
	}
	.models {
		display: grid;
		gap: 0.45rem;
	}
	.explain {
		line-height: 1.6;
		background: rgba(108, 198, 255, 0.07);
		border-color: rgba(108, 198, 255, 0.25);
	}
	.gap {
		height: 2.4rem;
	}
</style>
