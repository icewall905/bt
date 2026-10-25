import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

const backend = process.env.BT_BACKEND ?? 'http://localhost:6699';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		port: 5173,
		proxy: { '/api': { target: backend, changeOrigin: false, ws: false } }
	},
	preview: { proxy: { '/api': { target: backend } } },
	build: { target: 'es2022', chunkSizeWarningLimit: 1200 }
});
