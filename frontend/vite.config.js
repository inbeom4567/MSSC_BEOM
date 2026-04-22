import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// 프론트엔드는 http://localhost:8001 (VITE_API_URL 오버라이드 가능)로 직접 호출합니다.
// 모든 fetch는 `${API}/api/...` 절대 URL을 사용하므로 Vite dev 프록시는 사용하지 않습니다.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'node',
  },
})
