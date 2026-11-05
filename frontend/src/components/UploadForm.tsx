import { useState } from 'react'
import type { FormEvent } from 'react'
import { DECOR_STYLES } from '../types'
import type { DecorStyle } from '../types'

const BUDGET_MIN = 20
const BUDGET_MAX = 500
const BUDGET_STEP = 10

interface UploadFormProps {
  onSubmit: (params: {
    image: File
    budget: number
    style: DecorStyle
  }) => void
  isSubmitting: boolean
}

export default function UploadForm({ onSubmit, isSubmitting }: UploadFormProps) {
  const [image, setImage] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [budget, setBudget] = useState(150)
  const [style, setStyle] = useState<DecorStyle>('scandinavian')

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null
    setImage(file)
    setPreview(file ? URL.createObjectURL(file) : null)
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!image) return
    onSubmit({
      image,
      budget,
      style,
    })
  }

  const fillPct = ((budget - BUDGET_MIN) / (BUDGET_MAX - BUDGET_MIN)) * 100

  return (
    <form onSubmit={handleSubmit} className="space-y-6 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-neutral-200">
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-2">Photo of your dorm room</label>
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp"
          onChange={handleFileChange}
          required
          className="block w-full text-sm text-neutral-600 file:mr-4 file:rounded-lg file:border-0 file:bg-neutral-900 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-neutral-700"
        />
        {preview && (
          <img src={preview} alt="Room preview" className="mt-3 h-48 w-full rounded-lg object-cover" />
        )}
      </div>

      <div>
        <div className="mb-2 flex items-baseline justify-between">
          <span className="text-sm font-medium text-neutral-700">Budget</span>
          <span className="text-sm font-medium text-neutral-700">
            <strong className="font-bold text-neutral-900">${budget}</strong>
          </span>
        </div>
        <div className="relative h-5">
          <div className="absolute left-0 right-0 top-1/2 h-1 -mt-0.5 rounded-full bg-neutral-200" />
          <div
            className="absolute top-1/2 h-1 -mt-0.5 rounded-full bg-neutral-900"
            style={{ left: '0%', width: `${fillPct}%` }}
          />
          <input
            type="range"
            className="dual-range"
            min={BUDGET_MIN}
            max={BUDGET_MAX}
            step={BUDGET_STEP}
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
            aria-label="Budget"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-2">Style</label>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {DECOR_STYLES.map((s) => (
            <button
              type="button"
              key={s.value}
              onClick={() => setStyle(s.value)}
              className={`relative h-28 overflow-hidden rounded-lg border text-sm transition ${
                style === s.value
                  ? 'border-neutral-900 ring-[3px] ring-neutral-900 ring-offset-2'
                  : 'border-neutral-200 hover:border-neutral-400'
              }`}
            >
              <img src={s.image} alt="" className="absolute inset-0 h-full w-full object-cover" />
              <span className="absolute inset-0 bg-black/25" />
              <span
                className="absolute inset-x-0 top-0 px-3 pt-2 text-left font-medium text-white"
                style={{ textShadow: '0 1px 3px rgba(0,0,0,0.8)' }}
              >
                {s.label}
              </span>
              {style === s.value && (
                <span className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-neutral-900 ring-2 ring-white">
                  <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 13l4 4L19 7" />
                  </svg>
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      <button
        type="submit"
        disabled={!image || isSubmitting}
        className="w-full rounded-lg bg-neutral-900 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50"
      >
        {isSubmitting ? 'Generating suggestions…' : 'Get furniture suggestions'}
      </button>
    </form>
  )
}
