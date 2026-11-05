import { useEffect, useState } from 'react'
import { fetchPrivateImage } from '../api/client'

export default function PrivateImage({ path, alt, className }: {
  path: string; alt: string; className?: string
}) {
  const [image, setImage] = useState<{ path: string; url: string } | null>(null)
  const [errorPath, setErrorPath] = useState<string | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    let url: string | undefined
    void fetchPrivateImage(path, controller.signal).then((blob) => {
      if (controller.signal.aborted) return
      url = URL.createObjectURL(blob)
      setImage({ path, url })
    }).catch(() => {
      if (!controller.signal.aborted) setErrorPath(path)
    })
    return () => {
      controller.abort()
      if (url) URL.revokeObjectURL(url)
    }
  }, [path])
  if (image?.path === path) return <img src={image.url} alt={alt} className={className} />
  return <p role="status" className="p-4 text-sm text-neutral-500">
    {errorPath === path ? 'Image unavailable. Please reload to try again.' : 'Loading image…'}
  </p>
}
