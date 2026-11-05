import { useState } from 'react'
import { Link } from 'react-router-dom'
import UploadForm from '../components/UploadForm'
import ResultView from '../components/ResultView'
import { createSubmission, generateSuggestion, saveDesign } from '../api/client'
import { useUser } from '../context/UserContext'
import type { DecorStyle, Submission, Suggestion } from '../types'

export default function DesignPage() {
  const { user } = useUser()
  const [submission, setSubmission] = useState<Submission | null>(null)
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  if (!user) return null

  async function handleSubmit(params: {
    image: File
    budget: number
    style: DecorStyle
  }) {
    setIsSubmitting(true)
    setError(null)
    try {
      const newSubmission = await createSubmission(params)
      const result = await generateSuggestion(newSubmission.id)
      setSubmission(newSubmission)
      setSuggestion(result)
      setSaved(false)
      setSaveError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleSave() {
    if (submission === null) return
    setSaving(true)
    setSaveError(null)
    try {
      await saveDesign(submission.id)
      setSaved(true)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Could not save this design')
    } finally {
      setSaving(false)
    }
  }

  function handleIterate() {
    setSuggestion(null)
    setSubmission(null)
    setSaved(false)
    setSaveError(null)
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="border-b border-neutral-200 bg-white">
        <div className="mx-auto max-w-2xl px-4 py-5">
          {suggestion ? (
            <div className="mb-1 flex items-center justify-between">
              <button
                type="button"
                onClick={handleIterate}
                className="inline-flex items-center gap-1 text-sm font-medium text-neutral-700 hover:text-neutral-900"
              >
                <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M15 18l-6-6 6-6" />
                </svg>
                Back
              </button>
              <Link to="/" className="text-sm font-medium text-neutral-700 hover:text-neutral-900">
                Cancel
              </Link>
            </div>
          ) : (
            <Link to="/" className="text-sm text-neutral-500 hover:text-neutral-800">
              ← Home
            </Link>
          )}
          <h1 className="mt-1 text-xl font-bold text-neutral-900">New design</h1>
          <p className="text-sm text-neutral-500">
            Upload a photo of your dorm, set a budget and style, and get furniture suggestions from IKEA.
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-8">
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200">
            {error}
          </div>
        )}

        {suggestion && submission ? (
          <ResultView
            submission={submission}
            suggestion={suggestion}
            onIterate={handleIterate}
            onSave={handleSave}
            saved={saved}
            saving={saving}
            saveError={saveError}
          />
        ) : (
          <UploadForm onSubmit={handleSubmit} isSubmitting={isSubmitting} />
        )}
      </main>
    </div>
  )
}
