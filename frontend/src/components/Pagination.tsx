interface Props {
  page: number;
  totalPages: number | null;
  hasMore: boolean;
  disabled?: boolean;
  onPage: (page: number) => void;
  perPage?: number;
  perPageOptions?: number[];
  onPerPage?: (perPage: number) => void;
}

export function Pagination({ page, totalPages, hasMore, disabled, onPage, perPage, perPageOptions, onPerPage }: Props) {
  return (
    <div className="pagination">
      <div className="pagination-controls">
        <button type="button" className="btn btn-secondary" disabled={disabled || page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </button>
        <span className="pagination-status">
          Page {page}
          {totalPages ? ` of ${totalPages}` : ""}
        </span>
        <button type="button" className="btn btn-secondary" disabled={disabled || !hasMore} onClick={() => onPage(page + 1)}>
          Next
        </button>
      </div>
      {perPage && perPageOptions && onPerPage && (
        <label className="pagination-per-page">
          Rows per page
          <select value={perPage} disabled={disabled} onChange={(e) => onPerPage(Number(e.target.value))}>
            {perPageOptions.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
