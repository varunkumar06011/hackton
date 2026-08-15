// Shared status badge helper used by Dashboard and OrderDetail.
// Emojis are intentionally empty to match the original Dashboard styling;
// TODO(owner): add emoji glyphs here if you want icons on the badges.
export const STATUS_EMOJI = {
  pending: '',
  preparing: '',
  ready: '',
  delivered: '',
  cancelled: '',
}

const BADGE_CLASS = {
  pending: 'badge-pending',
  preparing: 'badge-preparing',
  ready: 'badge-ready',
  delivered: 'badge-delivered',
  cancelled: 'badge-cancelled',
}

export const statusBadge = (status) => (
  <span className={BADGE_CLASS[status] || 'badge-pending'}>
    {STATUS_EMOJI[status]} {status}
  </span>
)
