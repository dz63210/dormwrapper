import { Link } from 'react-router-dom'
import { DECOR_STYLES } from '../types'
import type { Submission, Suggestion } from '../types'
import { catalogueImageUrl } from '../api/client'
import PrivateImage from './PrivateImage'

interface ResultViewProps {
  submission: Submission
  suggestion: Suggestion
  onIterate: () => void
  onSave: () => void
  saved: boolean
  saving: boolean
  saveError: string | null
}

function styleLabel(value: string): string {
  return DECOR_STYLES.find((s) => s.value === value)?.label ?? value
}

export default function ResultView({
  submission,
  suggestion,
  onIterate,
  onSave,
  saved,
  saving,
  saveError,
}: ResultViewProps) {
  return (
    <div className="pb-24">
      <div className="space-y-6 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-neutral-200">
        <div>
          <h2 className="text-lg font-semibold text-neutral-900">Your decorated room</h2>
          {suggestion.generated_image_path ? (
            <PrivateImage
              path={suggestion.generated_image_path}
              alt="Generated room suggestion"
              className="mt-3 w-full rounded-xl object-cover"
            />
          ) : (
            <div className="mt-3 rounded-xl bg-amber-50 px-4 py-6 text-center text-sm text-amber-800 ring-1 ring-amber-200">
              We picked your furniture, but the room image couldn't be generated this time.
            </div>
          )}
          <p className="mt-2 text-sm text-neutral-500">
            Total: ${suggestion.total_price.toFixed(2)}
          </p>
        </div>

        <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
          <h3 className="mb-2.5 text-xs font-bold uppercase tracking-wide text-neutral-500">
            Your selections
          </h3>
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center gap-1 rounded-full border border-neutral-200 bg-white px-3 py-1 text-sm">
              <span className="text-neutral-500">Style</span>{' '}
              <span className="font-semibold text-neutral-900">{styleLabel(submission.style)}</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-neutral-200 bg-white px-3 py-1 text-sm">
              <span className="text-neutral-500">Budget</span>{' '}
              <span className="font-semibold text-neutral-900">${submission.budget}</span>
            </span>
          </div>
        </div>

        <div>
          <h3 className="mb-2 text-sm font-semibold text-neutral-700">Suggested items</h3>
          <ul className="space-y-2.5">
            {suggestion.items.map((item) => (
              <li key={item.id} className="flex gap-3 rounded-xl border border-neutral-200 p-3">
                <img
                  src={catalogueImageUrl(item.image_url)}
                  alt=""
                  className="h-16 w-16 flex-shrink-0 rounded-lg bg-neutral-100 object-cover"
                />
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-neutral-900">{item.name}</p>
                      <p className="text-xs text-neutral-500">{item.category} · {item.retailer === 'ikea' ? 'IKEA' : item.retailer}</p>
                    </div>
                    <div className="flex flex-shrink-0 items-center gap-2">
                      <span className="text-sm font-bold text-neutral-900">{new Intl.NumberFormat('en-US', { style: 'currency', currency: item.currency }).format(item.price)}</span>
                      <a
                        href={item.affiliate_url || item.product_url}
                        target="_blank"
                        rel="noreferrer"
                        aria-label={`Open listing for ${item.name}`}
                        title="Open listing"
                        className="flex h-6.5 w-6.5 flex-shrink-0 items-center justify-center rounded-md border border-neutral-200 text-neutral-600 hover:border-neutral-400 hover:bg-neutral-50"
                      >
                        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M14 4h6v6" />
                          <path d="M10 14L20 4" />
                          <path d="M18 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h6" />
                        </svg>
                      </a>
                    </div>
                  </div>
                  <p className="line-clamp-2 text-xs text-neutral-600">{item.description}</p>
                </div>
              </li>
            ))}
            {suggestion.items.length === 0 && (
              <li className="text-sm text-neutral-500">No items fit within the given budget.</li>
            )}
          </ul>
        </div>

        {saveError && <p className="text-sm text-red-600">{saveError}</p>}

        {saved && (
          <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-800 ring-1 ring-green-200">
            Saved.{' '}
            <Link to="/" className="font-medium underline">
              See it on your home page
            </Link>
            .
          </div>
        )}
      </div>

      <div className="fixed inset-x-0 bottom-0 border-t border-neutral-200 bg-white">
        <div className="mx-auto flex max-w-2xl gap-3 px-4 py-3">
          <button
            type="button"
            onClick={onSave}
            disabled={saving || saved}
            className="flex-1 rounded-lg bg-neutral-900 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {saved ? 'Saved' : saving ? 'Saving…' : 'Save'}
          </button>
          <button
            type="button"
            onClick={onIterate}
            className="flex-1 rounded-lg border border-neutral-300 px-4 py-2.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50"
          >
            Restart
          </button>
        </div>
      </div>
    </div>
  )
}
