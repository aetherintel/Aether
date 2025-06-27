import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';
import path from 'path'
import sirv from 'sirv'

const mediaServePlugin = () => {
  return {
    name: 'media-serve',
    configureServer(server) {
      const mediaPath = path.resolve(process.cwd(), '../shared/media')
      
      const serve = sirv(mediaPath, {
        dev: true,
        etag: true,
        maxAge: 31536000,
        immutable: true
      })
      
      server.middlewares.use('/app/public/media', serve)
    }
  }
}

export default defineConfig({
  plugins: [react(), tsconfigPaths(),mediaServePlugin()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './vitest.setup.mjs',
  },
});
