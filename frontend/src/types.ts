// Matches DecorStyle in backend/app/models.py (the catalog.json `styles` values).
export type DecorStyle =
  | 'scandinavian'
  | 'minimalist'
  | 'modern'
  | 'industrial'
  | 'mid-century'
  | 'boho'
  | 'traditional'

export const DECOR_STYLES: { value: DecorStyle; label: string; image: string }[] = [
  {
    value: 'scandinavian',
    label: 'Scandinavian',
    image: 'https://i.pinimg.com/736x/52/7e/cb/527ecb83b77c00b40a7319e641000cf8.jpg',
  },
  {
    value: 'minimalist',
    label: 'Minimalist',
    image: 'https://i.pinimg.com/736x/d4/40/25/d440258900b51c537a155c608c55d51a.jpg',
  },
  {
    value: 'modern',
    label: 'Modern',
    image: 'https://i.pinimg.com/736x/8a/c5/3d/8ac53d6d3bc9fe9eefee067153b4e9f6.jpg',
  },
  {
    value: 'industrial',
    label: 'Industrial',
    image: 'https://i.pinimg.com/736x/e1/6c/66/e16c664f5fac086b091fceda25dbb783.jpg',
  },
  {
    value: 'mid-century',
    label: 'Mid-century',
    image: 'https://i.pinimg.com/736x/e6/46/b3/e646b3dd966195c70625b23ada61ab36.jpg',
  },
  {
    value: 'boho',
    label: 'Boho',
    image: 'https://i.pinimg.com/736x/ec/1b/b0/ec1bb04921c0870a11b1a9563f673990.jpg',
  },
  {
    value: 'traditional',
    label: 'Traditional',
    image: 'https://i.pinimg.com/736x/74/03/b5/7403b5244268f4ac19768cdd5038a248.jpg',
  },
]

export interface CatalogueItem {
  id: number
  name: string
  category: string
  price: number
  dominant_color: string
  style_tags: string
  description: string
  image_url: string
  product_url: string
  retailer: string
  external_product_id: string
  currency: string
  availability: 'unknown' | 'in_stock' | 'out_of_stock' | 'discontinued'
  room_type: string
  dimensions: Record<string, unknown>
  materials: string[]
  affiliate_url: string
  source_type: string
  license_status: string
  fetched_at: string
  last_verified_at: string
}

export interface User {
  id: number
  handle: string
  created_at: string
  email?: string | null
}

export interface AuthSession extends User {
  token: string
  expires_at: string
}

export type GuestSession = AuthSession

export interface Submission {
  id: number
  created_at: string
  room_image_path: string
  budget: number
  style: DecorStyle
  notes: string
}

// Stage 1 (furniture recommendation) output. App-facing metadata; the user
// sees the generated image, not this.
export interface RecommendedItem {
  item_id: number
  quantity: number
  placement: string
  reason: string
}

export interface Recommendation {
  items: RecommendedItem[]
  total_price: number
  summary: string
}

export interface Suggestion {
  id: number
  submission_id: number
  generated_image_path: string
  total_price: number
  item_ids: string
  created_at: string
  items: CatalogueItem[]
  recommendation: Recommendation | null
}

export interface SavedDesign {
  submission_id: number
  created_at: string
  style: DecorStyle
  budget: number
  room_image_path: string
  generated_image_path: string
  total_price: number
  items: CatalogueItem[]
  recommendation: Recommendation | null
}
