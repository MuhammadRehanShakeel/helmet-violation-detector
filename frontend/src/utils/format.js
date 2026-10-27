/** Small display helpers used on many pages. */
export const VIOLATION_LABEL = { NO_HELMET: 'No helmet', TRIPLE_RIDING: 'Triple riding' };
export const STATUS_COLOR = { pending: 'warning', approved: 'success', rejected: 'default' };

export const rupees = (n) => `Rs ${Number(n || 0).toLocaleString('en-PK')}`;
export const percent = (x) => (x === null || x === undefined ? '-' : `${Math.round(x * 100)}%`);

export function dateTime(value) {
  if (!value) return '-';
  const d = new Date(value);
  return d.toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export const canReview = (user) => ['admin', 'officer'].includes(user?.role);
export const isAdmin = (user) => user?.role === 'admin';
