import React, { useEffect, useState, useRef } from 'react'
import DepthCarousel from './reactbits/DepthCarousel'
import type { AuctionLot } from '../types'
import { api, mediaUrl } from '../api'
import AppIcon from './AppIcon'

interface AuctionLotModalProps {
  lot: AuctionLot
  lots?: AuctionLot[]
  onClose: () => void
  onAssessLot?: (lot: AuctionLot) => void
  onSelectLot?: (lot: AuctionLot) => void
}

const money = (v: number | null, code = 'VND') =>
  v === null
    ? 'Không đủ dữ liệu'
    : new Intl.NumberFormat('vi-VN', {
        style: 'currency',
        currency: code.toUpperCase(),
        maximumFractionDigits: 0,
      }).format(Math.round(v))

const dateOnly = (v: string) =>
  new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeZone: 'Asia/Ho_Chi_Minh' }).format(
    new Date(`${v}T12:00:00+07:00`)
  )

export function AuctionLotModal({ lot, lots, onClose, onAssessLot, onSelectLot }: AuctionLotModalProps) {
  const [images, setImages] = useState<Array<{ image: string; alt?: string; fallback?: string }>>(() => {
    const init = mediaUrl(lot.cover?.url) || lot.cover?.url
    return init ? [{ image: init, alt: lot.title }] : []
  })
  const [activeIndex, setActiveIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [imageLoaded, setImageLoaded] = useState(false)
  const [transitionDir, setTransitionDir] = useState<'left' | 'right' | 'up' | 'down' | null>(null)
  const [showDetails, setShowDetails] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)
  const backdropRef = useRef<HTMLDivElement>(null)
  const touchStartRef = useRef<{ x: number; y: number; time: number } | null>(null)
  const detailBodyRef = useRef<HTMLDivElement>(null)

  // Reset active photo index and loading state when lot changes
  useEffect(() => {
    setActiveIndex(0)
    setImageLoaded(false)
  }, [lot.lot_id])

  // Clear feedback toast
  useEffect(() => {
    if (!feedback) return
    const t = setTimeout(() => setFeedback(null), 1600)
    return () => clearTimeout(t)
  }, [feedback])

  // Fetch gallery images
  useEffect(() => {
    let cancelled = false
    setLoading(true)

    // Pre-populate with lot cover image immediately so transition is instant
    const initCover = mediaUrl(lot.cover?.url) || lot.cover?.url
    if (initCover) {
      setImages([{ image: initCover, alt: lot.title }])
    }

    api.lotImages(lot.lot_id)
      .then((res) => {
        if (cancelled) return

        const coverRecord = res.images.find((img) => img.idx === 0)
        const telegramFallback = coverRecord?.url || mediaUrl(lot.cover?.url) || lot.cover?.url || undefined

        const cdnGallery = res.images.filter(
          (img) => img.idx >= 1 && Boolean(img.direct_url || img.url)
        )

        if (cdnGallery.length > 0) {
          const valid = cdnGallery.map((img, i) => ({
            image: (img.direct_url || img.url)!,
            alt: `${lot.title} - Ảnh ${i + 1}`,
            fallback: i === 0 ? telegramFallback : undefined,
          }))
          setImages(valid)
        } else if (telegramFallback) {
          setImages([{ image: telegramFallback, alt: `${lot.title} - Ảnh bìa` }])
        }
      })
      .catch(() => {
        const fb = mediaUrl(lot.cover?.url) || lot.cover?.url
        if (fb) {
          setImages([{ image: fb, alt: lot.title }])
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [lot.lot_id, lot.title, lot.cover?.url])

  // Keyboard navigation
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showDetails) {
          setShowDetails(false)
        } else {
          onClose()
        }
      } else if (e.key === 'ArrowRight' && images.length > 1) {
        setTransitionDir('left')
        setImageLoaded(false)
        setActiveIndex((prev) => (prev + 1) % images.length)
      } else if (e.key === 'ArrowLeft' && images.length > 1) {
        setTransitionDir('right')
        setImageLoaded(false)
        setActiveIndex((prev) => (prev - 1 + images.length) % images.length)
      } else if (e.key === 'ArrowDown' && lots && lots.length > 0 && onSelectLot) {
        const cur = lots.findIndex((l) => l.lot_id === lot.lot_id)
        if (cur >= 0 && cur < lots.length - 1) {
          setTransitionDir('up')
          setImageLoaded(false)
          setFeedback(`Lô #${lots[cur + 1].lot_id}`)
          onSelectLot(lots[cur + 1])
        }
      } else if (e.key === 'ArrowUp' && lots && lots.length > 0 && onSelectLot) {
        const cur = lots.findIndex((l) => l.lot_id === lot.lot_id)
        if (cur > 0) {
          setTransitionDir('down')
          setImageLoaded(false)
          setFeedback(`Lô #${lots[cur - 1].lot_id}`)
          onSelectLot(lots[cur - 1])
        }
      }
    }
    window.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [onClose, showDetails, images.length, lots, lot.lot_id, onSelectLot])

  // Mobile Touch Gestures
  const handleTouchStart = (e: React.TouchEvent) => {
    if (e.touches.length !== 1) return
    touchStartRef.current = {
      x: e.touches[0].clientX,
      y: e.touches[0].clientY,
      time: Date.now(),
    }
  }

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (!touchStartRef.current) return
    const touch = e.changedTouches[0]
    const deltaX = touch.clientX - touchStartRef.current.x
    const deltaY = touch.clientY - touchStartRef.current.y
    const absX = Math.abs(deltaX)
    const absY = Math.abs(deltaY)
    const elapsed = Date.now() - touchStartRef.current.time
    touchStartRef.current = null

    if (elapsed > 700) return

    // 1. Swipe Horizontal: Prev/Next photo (when details sheet is closed)
    if (absX > 36 && absX > absY * 1.1) {
      if (showDetails) return
      if (images.length <= 1) return
      if (deltaX < 0) {
        // Dragged left -> view next photo (slides in from right)
        setTransitionDir('left')
        setImageLoaded(false)
        setActiveIndex((prev) => (prev + 1) % images.length)
      } else {
        // Dragged right -> view prev photo (slides in from left)
        setTransitionDir('right')
        setImageLoaded(false)
        setActiveIndex((prev) => (prev - 1 + images.length) % images.length)
      }
      return
    }

    // 2. Swipe Vertical
    if (absY > 48 && absY > absX * 1.1) {
      if (!showDetails) {
        if (deltaY < 0) {
          // Chi tiết đang ĐÓNG + Vuốt LÊN -> Mở Panel Chi tiết
          setShowDetails(true)
        } else if (deltaY > 0) {
          // Chi tiết đang ĐÓNG + Vuốt XUỐNG -> Đóng Modal (quay về danh sách)
          onClose()
        }
      } else {
        if (deltaY > 0) {
          // Chi tiết đang MỞ + Vuốt XUỐNG -> Hạ/Đóng Panel Chi tiết
          if (detailBodyRef.current && detailBodyRef.current.scrollTop > 10) {
            return
          }
          setShowDetails(false)
        }
      }
    }
  }

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === backdropRef.current) {
      onClose()
    }
  }

  const isCancelled =
    lot.source_available === 0 || lot.source_available === false || lot.review_status === 'cancelled'

  return (
    <div
      ref={backdropRef}
      className="auction-modal-backdrop"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="auction-modal-title"
    >
      <div className="auction-modal-content">
        {/* Top bar: title on left, close button on right */}
        <header className="auction-modal-topbar">
          <div className="auction-modal-title-wrap">
            <span className="auction-modal-lot-tag">Lô #{lot.lot_id}</span>
            <h2 id="auction-modal-title" title={lot.title}>
              {lot.title}
            </h2>
          </div>
          <button
            type="button"
            className="auction-modal-close-btn"
            onClick={onClose}
            aria-label="Đóng (Esc)"
            title="Đóng (Esc)"
          >
            <AppIcon name="close" />
          </button>
        </header>

        {/* Feedback toast when swiping between lots */}
        {feedback && (
          <div className="auction-lot-swipe-toast" role="status">
            {feedback}
          </div>
        )}

        {/* Canvas: Desktop 3D DepthCarousel vs Mobile Full-bleed Swipe Stage */}
        <div className="auction-modal-body">
          {/* Desktop Canvas (React Bits DepthCarousel) */}
          <div className="auction-canvas-desktop">
            {images.length > 0 ? (
              <>
                <DepthCarousel
                  items={images}
                  cardWidth={580}
                  cardHeight={580}
                  depth={220}
                  spread={100}
                  tilt={14}
                  tiltDirection="right"
                  duration={600}
                  onChange={(idx) => setActiveIndex(idx)}
                />
                {loading && (
                  <div className="desktop-photo-loading-tag" aria-live="polite">
                    <span className="photo-loading-spinner photo-loading-spinner--sm" />
                    <span>Đang nạp bộ sưu tập ảnh…</span>
                  </div>
                )}
              </>
            ) : (
              <div className="empty" style={{ color: '#fff', minHeight: '320px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
                {loading && <span className="photo-loading-spinner" />}
                <span>{loading ? 'Đang nạp ảnh chất lượng cao…' : 'Chưa có ảnh cho lô này.'}</span>
              </div>
            )}
          </div>

          {/* Mobile Canvas (Touch swipeable full-bleed stage) */}
          <div
            className="auction-canvas-mobile"
            onTouchStart={handleTouchStart}
            onTouchEnd={handleTouchEnd}
          >
            {images.length > 0 ? (
              <div className="mobile-photo-stage">
                <img
                  key={`${lot.lot_id}-${activeIndex}`}
                  src={images[activeIndex]?.image}
                  alt={images[activeIndex]?.alt || lot.title}
                  className={`mobile-main-photo ${transitionDir ? `slide-${transitionDir}` : ''}`}
                  onLoad={() => setImageLoaded(true)}
                  onError={(e) => {
                    setImageLoaded(true)
                    if (images[activeIndex]?.fallback) {
                      e.currentTarget.src = images[activeIndex].fallback!
                    }
                  }}
                />

                {/* Loading indicator during lot switch or image download */}
                {(loading || !imageLoaded) && (
                  <div className="mobile-photo-loading-overlay" role="status" aria-live="polite">
                    <span className="photo-loading-spinner" />
                    <span className="photo-loading-text">
                      {loading ? 'Đang nạp ảnh lô mới…' : 'Đang tải ảnh…'}
                    </span>
                  </div>
                )}

              </div>
            ) : (
              <div className="empty" style={{ color: '#fff', minHeight: '320px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
                {loading && <span className="photo-loading-spinner" />}
                <span>{loading ? 'Đang nạp ảnh chất lượng cao…' : 'Chưa có ảnh cho lô này.'}</span>
              </div>
            )}
          </div>
        </div>

        {/* Glassmorphism Detail Sheet Overlay (Triggered by bottom-left Pill or Swipe Up) */}
        {showDetails && (
          <div
            className="auction-detail-overlay"
            onClick={(e) => {
              if (e.target === e.currentTarget) setShowDetails(false)
            }}
            onTouchStart={handleTouchStart}
            onTouchEnd={handleTouchEnd}
          >
            <div className="auction-detail-sheet" role="region" aria-label="Thông số chi tiết">
              <div className="detail-sheet-handle" aria-hidden="true" />
              <div className="detail-sheet-header">
                <div>
                  <span className="detail-sheet-tag">Lô #{lot.lot_id}</span>
                  <h3 className="detail-sheet-title">{lot.title}</h3>
                </div>
                <button
                  type="button"
                  className="detail-sheet-close-btn"
                  onClick={() => setShowDetails(false)}
                  aria-label="Đóng chi tiết"
                >
                  <AppIcon name="close" />
                </button>
              </div>

              <div ref={detailBodyRef} className="detail-sheet-body">
                {/* Finance block */}
                <div className="detail-sheet-finance">
                  <div className="finance-item">
                    <span className="finance-label">Trạng thái</span>
                    <span className="finance-val">
                      {lot.status === 'settled' ? (
                        isCancelled ? (
                          <span className="chip-cancelled">Cancelled</span>
                        ) : (
                          <span className={lot.sold ? 'chip-sold' : 'chip-unsold'}>
                            {lot.sold ? 'Settled' : 'Unsold'}
                          </span>
                        )
                      ) : (
                        <span className={lot.status === 'open' ? 'chip-open' : 'chip-waiting'}>
                          {lot.status === 'open' ? 'Open' : 'Waiting'}
                        </span>
                      )}
                    </span>
                  </div>

                  {lot.hammer_eur != null && (
                    <div className="finance-item">
                      <span className="finance-label">Giá gõ búa</span>
                      <span className="finance-val highlight">{money(lot.hammer_eur, 'EUR')}</span>
                    </div>
                  )}

                  {!lot.sold && lot.highest_bid_eur != null && (
                    <div className="finance-item">
                      <span className="finance-label">Giá cao nhất</span>
                      <span className="finance-val highlight">{money(lot.highest_bid_eur, 'EUR')}</span>
                    </div>
                  )}

                  {lot.bidding_end_at && (
                    <div className="finance-item">
                      <span className="finance-label">Thời điểm kết thúc</span>
                      <span className="finance-val">{dateOnly(lot.bidding_end_at.slice(0, 10))}</span>
                    </div>
                  )}
                </div>

                {/* Badges / Specs block */}
                <div className="detail-sheet-badges">
                  {lot.condition_tag && (
                    <span className={`chip-accessory chip-accessory--${lot.condition_tag}`}>
                      {lot.condition_tag === 'fullset'
                        ? 'Full Set'
                        : lot.condition_tag === 'box'
                        ? 'Box'
                        : lot.condition_tag === 'papers'
                        ? 'Papers'
                        : 'Naked'}
                    </span>
                  )}
                  {lot.quality && (
                    <span className={`chip-quality chip-quality--${lot.quality}`}>
                      {lot.quality === 'new_unworn'
                        ? 'New / Unworn'
                        : lot.quality === 'very_good'
                        ? 'Very Good'
                        : lot.quality === 'good'
                        ? 'Good'
                        : 'Fair'}
                    </span>
                  )}
                  {lot.movement && (
                    <span className={`chip-movement chip-movement--${lot.movement}`}>
                      {lot.movement === 'auto'
                        ? 'Automatic'
                        : lot.movement === 'manual'
                        ? 'Manual'
                        : lot.movement === 'quartz'
                        ? 'Quartz'
                        : lot.movement}
                    </span>
                  )}
                  {lot.case_material && (
                    <span className={`chip-material chip-material--${lot.case_material}`}>
                      {lot.case_material === 'steel'
                        ? 'Steel'
                        : lot.case_material === 'gold'
                        ? 'Gold'
                        : lot.case_material === 'gold_plated'
                        ? 'Gold Plated'
                        : lot.case_material === 'titanium'
                        ? 'Titanium'
                        : lot.case_material}
                    </span>
                  )}
                  {lot.case_diameter_mm && (
                    <span className="chip-diameter">{lot.case_diameter_mm}mm</span>
                  )}
                  {lot.needs_review === 1 && (
                    <span className="chip-unclassified">Review: {lot.unclassified_reason || 'Cần kiểm tra'}</span>
                  )}
                </div>

                {lot.subtitle && <p className="detail-sheet-desc">{lot.subtitle}</p>}

                <div className="detail-sheet-meta-footer">
                  {lot.bids_count != null && (
                    <span className="meta-footer-item meta-footer-bids" title="Lượt đặt giá" aria-label={`Lượt đặt giá: ${lot.bids_count}`}>
                      <AppIcon name="gavel" />
                      <strong>{lot.bids_count}</strong>
                    </span>
                  )}
                  {lot.hearts != null && (
                    <span className="meta-footer-item meta-footer-hearts" title="Lượt quan tâm" aria-label={`Lượt quan tâm: ${lot.hearts}`}>
                      <AppIcon name="heart" />
                      <strong>{lot.hearts}</strong>
                    </span>
                  )}
                  <span className="meta-footer-item meta-footer-source" title="Sàn đấu giá" aria-label={`Sàn đấu giá: ${lot.source || 'Catawiki'}`}>
                    <AppIcon name="platform" />
                    <strong>{lot.source || 'Catawiki'}</strong>
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Floating Dock: Left (Detail Pill) - Center (1 / 16) - Right (Thẩm định | Nguồn) */}
        <footer className="auction-modal-dock">
          {/* Left Pill: Toggle Detail Sheet */}
          <button
            type="button"
            className={`dock-pill dock-pill--detail ${showDetails ? 'active' : ''}`}
            onClick={() => setShowDetails(!showDetails)}
            aria-expanded={showDetails}
            title="Xem chi tiết thông số đồng hồ"
          >
            <AppIcon name="assessment" />
            <span>{showDetails ? 'Ẩn chi tiết' : 'Chi tiết'}</span>
          </button>

          {/* Center Pill: Photo Counter */}
          <div className="dock-pill dock-pill--counter" title={`Ảnh ${activeIndex + 1} trong tổng số ${images.length} ảnh`}>
            <span>{images.length > 0 ? `${activeIndex + 1} / ${images.length}` : '0 / 0'}</span>
          </div>

          {/* Right Pill: Actions (Thẩm định + Nguồn) */}
          <div className="dock-pill dock-pill--actions">
            {onAssessLot && (
              <button
                type="button"
                className="dock-action-btn"
                onClick={() => onAssessLot(lot)}
                title="Đưa sang Thẩm định cơ hội"
              >
                <AppIcon name="transfer" />
                <span>Thẩm định</span>
              </button>
            )}
            <a
              className="dock-action-btn dock-action-btn--primary"
              href={lot.url}
              target="_blank"
              rel="noreferrer"
              title="Xem nguồn trực tiếp trên sàn"
            >
              <span>Nguồn</span>
              <AppIcon name="external" />
            </a>
          </div>
        </footer>
      </div>
    </div>
  )
}
