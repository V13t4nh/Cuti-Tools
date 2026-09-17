import React, { useEffect, useState, useRef } from 'react'
import DepthCarousel from './reactbits/DepthCarousel'
import type { AuctionLot } from '../types'
import { api, mediaUrl } from '../api'
import AppIcon from './AppIcon'

interface AuctionLotModalProps {
  lot: AuctionLot
  onClose: () => void
  onAssessLot?: (lot: AuctionLot) => void
}

const money = (v: number | null, code = 'VND') =>
  v === null
    ? 'Không đủ dữ liệu'
    : new Intl.NumberFormat('vi-VN', {
        style: 'currency',
        currency: code.toUpperCase(),
        maximumFractionDigits: code.toLowerCase() === 'vnd' ? 0 : 2,
      }).format(v)

const dateOnly = (v: string) =>
  new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeZone: 'Asia/Ho_Chi_Minh' }).format(
    new Date(`${v}T12:00:00+07:00`)
  )

export function AuctionLotModal({ lot, onClose, onAssessLot }: AuctionLotModalProps) {
  const [images, setImages] = useState<Array<{ image: string; alt?: string; fallback?: string }>>(() => {
    const init = mediaUrl(lot.cover?.url) || lot.cover?.url
    return init ? [{ image: init, alt: lot.title }] : []
  })
  const [activeIndex, setActiveIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const backdropRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)

    api.lotImages(lot.lot_id)
      .then((res) => {
        if (cancelled) return

        // 1. Cover from Telegram Vault (idx = 0)
        const coverRecord = res.images.find((img) => img.idx === 0)
        const telegramFallback = coverRecord?.url || mediaUrl(lot.cover?.url) || lot.cover?.url || undefined

        // 2. Gallery photos from direct CDN (idx >= 1)
        const cdnGallery = res.images.filter(
          (img) => img.idx >= 1 && Boolean(img.direct_url || img.url)
        )

        if (cdnGallery.length > 0) {
          // Prioritize direct CDN URLs for all slides:
          // Photo 1 (idx=1) has fallback to Telegram cover if CDN fails or returns error
          const valid = cdnGallery.map((img, i) => ({
            image: (img.direct_url || img.url)!,
            alt: `${lot.title} - Ảnh ${i + 1}`,
            fallback: i === 0 ? telegramFallback : undefined,
          }))
          setImages(valid)
        } else if (telegramFallback) {
          // CDN didn't return gallery photos -> fall back to Telegram cover
          setImages([{ image: telegramFallback, alt: `${lot.title} - Ảnh bìa` }])
        }
      })
      .catch(() => {
        // Fallback to Telegram cover on network or API failure
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

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [onClose])

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
        <header className="auction-modal-header">
          <div className="auction-modal-title-area">
            <h2 id="auction-modal-title" title={lot.title}>
              {lot.title}
            </h2>
            <div className="auction-modal-subtitle">
              <span>Lô #{lot.lot_id}</span>
              <span>·</span>
              {lot.status === 'settled' ? (
                <>
                  {isCancelled ? (
                    <span className="chip-cancelled">Bị gỡ / Hủy</span>
                  ) : (
                    <span className={lot.sold ? 'chip-sold' : 'chip-unsold'}>
                      {lot.sold ? 'Đã bán' : 'Không bán được'}
                    </span>
                  )}
                  {lot.hammer_eur != null && (
                    <span>
                      Giá gõ búa: <strong>{money(lot.hammer_eur, 'EUR')}</strong>
                    </span>
                  )}
                  {!lot.sold && lot.highest_bid_eur != null && (
                    <span>
                      Giá cao nhất: <strong>{money(lot.highest_bid_eur, 'EUR')}</strong>
                    </span>
                  )}
                  {lot.condition_tag && (
                    <span className="chip-accessory">
                      {lot.condition_tag === 'fullset' ? 'Đủ bộ (Fullset)' : lot.condition_tag === 'box' ? 'Có hộp (Box)' : lot.condition_tag === 'papers' ? 'Có giấy (Papers)' : 'Chỉ đồng hồ (Naked)'}
                    </span>
                  )}
                  {lot.quality && (
                    <span className="chip-quality">
                      {lot.quality === 'new_unworn' ? 'Mới tinh / Chưa đeo' : lot.quality === 'very_good' ? 'Rất đẹp / Ít xước' : lot.quality === 'good' ? 'Khá' : 'Cũ / Cần bảo dưỡng'}
                    </span>
                  )}
                  {lot.bidding_end_at && (
                    <span>Kết thúc: {dateOnly(lot.bidding_end_at.slice(0, 10))}</span>
                  )}
                </>
              ) : (
                <span>{lot.status === 'open' ? 'Đang mở đấu giá' : 'Chờ kết quả'}</span>
              )}
            </div>
          </div>
          <button
            type="button"
            className="auction-modal-close"
            onClick={onClose}
            aria-label="Đóng popup (Esc)"
            title="Đóng (Esc)"
          >
            <AppIcon name="close" />
          </button>
        </header>

        <div className="auction-modal-body">
          {images.length > 0 ? (
            <DepthCarousel
              items={images}
              cardWidth={620}
              cardHeight={620}
              depth={240}
              spread={120}
              tilt={15}
              tiltDirection="right"
              duration={600}
              onChange={(idx) => setActiveIndex(idx)}
            />
          ) : (
            <div className="empty" style={{ color: '#fff', minHeight: '320px' }}>
              {loading ? 'Đang nạp ảnh chất lượng cao…' : 'Chưa có ảnh cho lô này.'}
            </div>
          )}
        </div>

        <footer className="auction-modal-footer">
          <div className="auction-modal-counter">
            {images.length > 0 ? (
              <span>
                Ảnh <strong>{activeIndex + 1}</strong> / {images.length}
                {loading && ' (đang đồng bộ thêm…)'}
              </span>
            ) : (
              <span>0 ảnh</span>
            )}
          </div>
          <div className="auction-modal-actions">
            {images[activeIndex]?.image && (
              <a
                className="secondary button"
                href={images[activeIndex].image}
                target="_blank"
                rel="noreferrer"
                title="Mở ảnh gốc trong tab mới"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              >
                <AppIcon name="external" />
                <span>Ảnh gốc</span>
              </a>
            )}
            {onAssessLot && (
              <button
                type="button"
                className="secondary"
                onClick={() => onAssessLot(lot)}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              >
                <AppIcon name="transfer" />
                <span>Thẩm định</span>
              </button>
            )}
            <a
              className="primary button"
              href={lot.url}
              target="_blank"
              rel="noreferrer"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            >
              <span>Xem nguồn sàn</span>
              <AppIcon name="external" />
            </a>
          </div>
        </footer>
      </div>
    </div>
  )
}
