export function Pagination({
  currentPage,
  totalItems,
  pageSize,
  onPageChange,
}: {
  currentPage: number
  totalItems: number
  pageSize: number
  onPageChange: (page: number) => void
}) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
  if (totalItems <= pageSize) return null

  const start = (currentPage - 1) * pageSize + 1
  const end = Math.min(totalItems, currentPage * pageSize)

  return (
    <nav className="pagination-bar" aria-label="Pagination">
      <span className="pagination-info">
        Showing <strong>{start}–{end}</strong> of <strong>{totalItems}</strong>
      </span>
      <div className="pagination-actions">
        <button
          type="button"
          className="secondary-button pagination-button"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
        >
          Previous
        </button>
        <span className="pagination-page-indicator">
          Page <strong>{currentPage}</strong> of <strong>{totalPages}</strong>
        </span>
        <button
          type="button"
          className="secondary-button pagination-button"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
        >
          Next
        </button>
      </div>
    </nav>
  )
}
