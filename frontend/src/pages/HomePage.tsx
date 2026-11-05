import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listSavedDesigns, unsaveDesign } from '../api/client'
import PrivateImage from '../components/PrivateImage'
import { useUser } from '../context/UserContext'
import { DECOR_STYLES } from '../types'
import type { SavedDesign } from '../types'

function styleLabel(value: string): string {
  return DECOR_STYLES.find((s) => s.value === value)?.label ?? value
}

export default function HomePage() {
  const { user } = useUser()
  const navigate = useNavigate()
  const [designs, setDesigns] = useState<SavedDesign[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [openId, setOpenId] = useState<number | null>(null)
  const [removingId, setRemovingId] = useState<number | null>(null)

  useEffect(() => {
    if (!user) return
    let cancelled = false
    listSavedDesigns()
      .then((d) => !cancelled && setDesigns(d))
      .catch((e) =>
        !cancelled && setError(e instanceof Error ? e.message : 'Could not load your saved designs'),
      )
    return () => {
      cancelled = true
    }
  }, [user])

  if (!user) return null

  async function handleRemove(submissionId: number) {
    setRemovingId(submissionId)
    try {
      await unsaveDesign(submissionId)
      setDesigns((current) =>
        (current ?? []).filter((d) => d.submission_id !== submissionId),
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not remove that design')
    } finally {
      setRemovingId(null)
    }
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="border-b border-neutral-200 bg-white">
        <div className="mx-auto max-w-2xl px-4 py-5">
          <h1 className="text-xl font-bold text-neutral-900">Welcome back, @{user.handle}</h1>
          <p className="text-sm text-neutral-500">Pick up a saved design or start a new one.</p>
        </div>
      </header>

      <main className="mx-auto max-w-2xl space-y-8 px-4 py-8">
        <button
          type="button"
          onClick={() => navigate('/new')}
          className="w-full rounded-2xl bg-neutral-900 px-6 py-5 text-left text-white shadow-sm transition hover:bg-neutral-800"
        >
          <span className="block text-base font-semibold">Start a new design</span>
          <span className="block text-sm text-neutral-300">
            Upload a room photo, set your budget and style, get IKEA suggestions.
          </span>
        </button>

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-neutral-500">
            Your saved designs
          </h2>

          {error && (
            <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200">
              {error}
            </div>
          )}

          {designs === null && !error && (
            <p className="text-sm text-neutral-500">Loading…</p>
          )}

          {designs !== null && designs.length === 0 && (
            <div className="rounded-2xl border border-dashed border-neutral-300 px-4 py-8 text-center text-sm text-neutral-500">
              No saved designs yet. Start a new design and choose{' '}
              <span className="font-medium text-neutral-700">Save this design</span> to keep it here.
            </div>
          )}

          <ul className="space-y-4">
            {(designs ?? []).map((design) => {
              const isOpen = openId === design.submission_id
              return (
                <li
                  key={design.submission_id}
                  className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-neutral-200"
                >
                  <PrivateImage
                    path={design.generated_image_path || design.room_image_path}
                    alt="Saved room design"
                    className="block w-full h-auto"
                  />
                  <div className="space-y-3 p-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium text-neutral-900">
                          {styleLabel(design.style)} · ${design.total_price.toFixed(2)}
                        </p>
                        <p className="text-xs text-neutral-500">
                          Budget ${design.budget.toFixed(0)} ·{' '}
                          {new Date(design.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemove(design.submission_id)}
                        disabled={removingId === design.submission_id}
                        className="rounded-md border border-neutral-300 px-2 py-1 text-xs text-neutral-600 hover:bg-neutral-50 disabled:opacity-50"
                      >
                        {removingId === design.submission_id ? 'Removing…' : 'Remove'}
                      </button>
                    </div>

                    <button
                      type="button"
                      onClick={() => setOpenId(isOpen ? null : design.submission_id)}
                      className="text-sm font-medium text-neutral-700 underline"
                    >
                      {isOpen ? 'Hide items' : `Show items (${design.items.length})`}
                    </button>

                    {isOpen && (
                      <ul className="space-y-2">
                        {design.items.map((item) => (
                          <li
                            key={item.id}
                            className="flex items-center justify-between rounded-lg border border-neutral-200 px-3 py-2 text-sm"
                          >
                            <div>
                              <a
                                href={item.affiliate_url || item.product_url}
                                target="_blank"
                                rel="noreferrer"
                                className="font-medium text-neutral-900 underline"
                              >
                                {item.name}
                              </a>
                              <p className="text-neutral-500">{item.category} · {item.retailer === 'ikea' ? 'IKEA' : item.retailer}</p>
                            </div>
                            <span className="font-medium text-neutral-900">
                              {new Intl.NumberFormat('en-US', { style: 'currency', currency: item.currency }).format(item.price)}
                            </span>
                          </li>
                        ))}
                        {design.items.length === 0 && (
                          <li className="text-sm text-neutral-500">No items in this design.</li>
                        )}
                      </ul>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        </section>
      </main>
    </div>
  )
}
