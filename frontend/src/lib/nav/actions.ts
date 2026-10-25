import type { Action } from 'svelte/action';
import { nav, type FocusOpts } from './engine';

/**
 * Make an element remote-navigable.
 *   <button use:focusable={{ group: 'row-3', onSelect: play }}>…</button>
 * `onSelect` also fires on mouse click / tap.
 */
export const focusable: Action<HTMLElement, FocusOpts | undefined> = (node, opts = {}) => {
	let current: FocusOpts = opts ?? {};
	const onClick = (e: Event) => {
		if (current.disabled) return;
		current.onSelect?.(e);
	};
	node.addEventListener('click', onClick);
	nav.register(node, current);
	return {
		update(o) {
			current = o ?? {};
			nav.update(node, current);
		},
		destroy() {
			node.removeEventListener('click', onClick);
			nav.unregister(node);
		}
	};
};

/**
 * Focus trap for modals/overlays. Back key calls `onBack` (usually: close).
 *   <div use:navScope={{ onBack: close }}>…</div>
 */
export const navScope: Action<HTMLElement, { onBack?: () => void } | undefined> = (node, opts) => {
	const scope = nav.pushScope(node, opts?.onBack);
	return {
		update(o) {
			nav.updateScope(scope, o?.onBack);
		},
		destroy() {
			nav.popScope(scope);
		}
	};
};

/**
 * onKey handler for focusable scroll areas (long descriptions, transcripts): Up/Down scroll the
 * element while it can scroll, then let navigation continue.
 *   <div class="long" use:focusable={{ onKey: scrollByKeys }}>…</div>
 */
export function scrollByKeys(key: string, e: KeyboardEvent): boolean {
	const el = e.target as HTMLElement;
	const step = Math.max(80, el.clientHeight * 0.6);
	if (key === 'down' && el.scrollTop + el.clientHeight < el.scrollHeight - 2) {
		el.scrollBy({ top: step, behavior: 'smooth' });
		return true;
	}
	if (key === 'up' && el.scrollTop > 0) {
		el.scrollBy({ top: -step, behavior: 'smooth' });
		return true;
	}
	return false;
}
