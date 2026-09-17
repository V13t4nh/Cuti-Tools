import { useState } from 'react'
import AppIcon from './AppIcon'
import { api, setStoredToken } from '../api'

interface LockScreenProps {
  onSuccess: () => void
}

export function LockScreen({ onSuccess }: LockScreenProps) {
  const [secret, setSecret] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!secret.trim()) {
      setError('Vui lòng nhập mã bảo vệ.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await api.login(secret.trim())
      if (res.ok) {
        setStoredToken(res.token)
        onSuccess()
      } else {
        setError('Mã bảo vệ không chính xác.')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể xác thực.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="lock-screen-wrapper">
      <div className="lock-screen-card">
        <div className="lock-screen-brand">
          <AppIcon name="cuti-mark" width={36} height={36} />
          <div>
            <h1 className="lock-screen-title">CUTI Decision Terminal</h1>
            <p className="lock-screen-subtitle">Bảo vệ quyền truy cập từ xa</p>
          </div>
        </div>

        <p className="lock-screen-desc">
          Hệ thống được thiết lập chế độ riêng tư. Vui lòng nhập mã truy cập bí mật để mở khoá phiên làm việc.
        </p>

        <form className="lock-screen-form" onSubmit={handleSubmit}>
          <div className="lock-input-group">
            <label htmlFor="auth-secret-input" className="lock-input-label">
              Mã bảo vệ (Secret Key)
            </label>
            <input
              id="auth-secret-input"
              type="password"
              autoComplete="current-password"
              autoFocus
              placeholder="Nhập mã bí mật..."
              value={secret}
              onChange={(e) => {
                setSecret(e.target.value)
                if (error) setError('')
              }}
              className="lock-input"
              disabled={loading}
            />
          </div>

          {error && (
            <p className="inline-error lock-error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="primary lock-submit-btn" disabled={loading || !secret.trim()}>
            {loading ? 'Đang xác thực...' : 'Mở khoá hệ thống'}
          </button>
        </form>

        <div className="lock-screen-footer">
          <span>Khóa bảo vệ cá nhân · Cloudflare Tunnel</span>
        </div>
      </div>
    </div>
  )
}
