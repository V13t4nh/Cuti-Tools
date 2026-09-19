import { useEffect, useId, useState } from 'react'
import AppIcon from './AppIcon'

export interface PaginationProps {
  page: number
  pages: number
  total?: number
  setPage: (p: number) => void
  ariaLabel?: string
}

export function Pagination({
  page,
  pages,
  total,
  setPage,
  ariaLabel = 'Phân trang thị trường',
}: PaginationProps) {
  const inputId = useId()
  const [draft, setDraft] = useState(String(page))

  useEffect(() => {
    setDraft(String(page))
  }, [page])

  const commit = () => {
    const trimmed = draft.trim()
    if (!trimmed) {
      setDraft(String(page))
      return
    }
    const parsed = parseInt(trimmed, 10)
    if (isNaN(parsed) || parsed < 1) {
      setDraft(String(page))
      return
    }
    const clamped = Math.min(Math.max(parsed, 1), pages)
    setDraft(String(clamped))
    setPage(clamped)
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    if (/^\d*$/.test(val)) {
      setDraft(val)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      commit()
      e.currentTarget.blur()
    } else if (e.key === 'Escape') {
      setDraft(String(page))
      e.currentTarget.blur()
    }
  }

  if (pages <= 1) return null

  return (
    <nav className="pagination" aria-label={ariaLabel}>
      <button
        type="button"
        className="page-button"
        disabled={page <= 1}
        onClick={(e) => {
          e.currentTarget.blur()
          setPage(page - 1)
        }}
        aria-label="Trang trước"
      >
        <AppIcon name="previous" />
        <span>Trước</span>
      </button>

      <div className="page-summary">
        <label className="page-jump-label" htmlFor={inputId}>
          Trang
        </label>
        <div className="page-input-wrap">
          <input
            id={inputId}
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            className="page-input"
            aria-label={`Trang hiện tại, nhập từ 1 đến ${pages}`}
            value={draft}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onBlur={commit}
          />
          <span className="page-total">/ {pages}</span>
        </div>
        <span className="page-summary-sep" aria-hidden="true">
          ·
        </span>
        <span className="page-count">{total ?? 'Không đủ dữ liệu'} mục</span>
      </div>

      <button
        type="button"
        className="page-button"
        disabled={page >= pages}
        onClick={(e) => {
          e.currentTarget.blur()
          setPage(page + 1)
        }}
        aria-label="Trang sau"
      >
        <span>Sau</span>
        <AppIcon name="next" />
      </button>
    </nav>
  )
}
