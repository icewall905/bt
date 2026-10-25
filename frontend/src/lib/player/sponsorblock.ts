import type { SbAction, SbSegment, Settings } from '../types';

export interface Segment {
	start: number;
	end: number;
	category: string;
	action: SbAction;
	uuid: string;
	poi: boolean;
}

/** Normalise SponsorBlock segments using the user's per-category actions + minimum length. */
export function prepareSegments(raw: SbSegment[], sb: Settings['sponsorblock'] | undefined): Segment[] {
	if (!sb?.enabled) return [];
	const min = sb.min_segment_s ?? 0;
	return raw
		.map((r) => ({
			start: r.segment[0],
			end: r.segment[1],
			category: r.category,
			action: (sb.categories?.[r.category] ?? 'show') as SbAction,
			uuid: r.UUID,
			poi: r.actionType === 'poi' || r.category === 'poi_highlight'
		}))
		.filter((s) => s.action !== 'off' && (s.poi || s.end - s.start >= min))
		.sort((a, b) => a.start - b.start);
}
