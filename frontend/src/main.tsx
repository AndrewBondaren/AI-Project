import { createRoot } from 'react-dom/client'
import '@/app/styles/tailwind.css'
import App from '@/app/App'

const root = document.getElementById('root')
if (!root) throw new Error('Missing application root')
createRoot(root).render(<App />)
