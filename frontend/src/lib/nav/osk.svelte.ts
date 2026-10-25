// On-screen keyboard state. The overlay component (OskOverlay) renders when `target` is set.
import { nav } from './engine';

class OskStore {
	target = $state<HTMLInputElement | HTMLTextAreaElement | null>(null);
	label = $state('');
	value = $state('');

	open(el: HTMLInputElement | HTMLTextAreaElement, label?: string) {
		this.target = el;
		this.value = el.value ?? '';
		this.label = label ?? el.getAttribute('aria-label') ?? el.placeholder ?? 'Type';
	}

	/** Write the value back into the input so `bind:value` picks it up. */
	set(v: string) {
		this.value = v;
		const el = this.target;
		if (!el) return;
		el.value = v;
		el.dispatchEvent(new Event('input', { bubbles: true }));
	}

	close(submit = false) {
		const el = this.target;
		this.target = null;
		if (el && submit) {
			el.dispatchEvent(new Event('change', { bubbles: true }));
			el.dispatchEvent(new CustomEvent('osksubmit', { bubbles: true }));
		}
	}
}

export const osk = new OskStore();
nav.oskOpener = (el, label) => osk.open(el, label);
