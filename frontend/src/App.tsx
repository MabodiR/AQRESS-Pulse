import { useQuery } from '@tanstack/react-query'

type HealthResponse = {
  status: 'healthy'
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${apiBaseUrl}/health`)
  if (!response.ok) {
    throw new Error('The API health check failed.')
  }
  return response.json() as Promise<HealthResponse>
}

function App() {
  const health = useQuery({
    queryKey: ['api-health'],
    queryFn: fetchHealth,
    retry: 1,
  })

  const status = health.isPending ? 'Checking…' : health.isSuccess ? 'Healthy' : 'Unavailable'

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-16 text-slate-100">
      <section className="mx-auto max-w-3xl rounded-3xl border border-slate-800 bg-slate-900 p-8 shadow-2xl sm:p-12">
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-400">AQRESS</p>
        <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">SenseGrid</h1>
        <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-300">
          Local-first IoT sensor and device management platform. The Phase 1 project foundation is running.
        </p>
        <div className="mt-10 flex items-center gap-3 rounded-xl border border-slate-700 bg-slate-950/60 px-4 py-3">
          <span
            aria-hidden="true"
            className={`h-3 w-3 rounded-full ${health.isSuccess ? 'bg-emerald-400' : health.isPending ? 'bg-amber-400' : 'bg-red-400'}`}
          />
          <span className="font-medium">FastAPI status: {status}</span>
        </div>
      </section>
    </main>
  )
}

export default App

