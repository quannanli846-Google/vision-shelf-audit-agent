import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Bind to all IPv4 interfaces (not just the "localhost" hostname) so the
    // dev server is still reachable when a VPN/corporate network adapter
    // changes how "localhost" resolves (e.g. to ::1 instead of 127.0.0.1, or
    // via a virtual adapter). Access via http://127.0.0.1:5173 if
    // http://localhost:5173 doesn't load.
    host: true,
    port: 5173,
    strictPort: true,
  },
})
