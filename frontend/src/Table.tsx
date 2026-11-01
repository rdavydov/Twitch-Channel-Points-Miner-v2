import { useMemo, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  ChevronDown,
  Columns3,
  Download,
  GripVertical,
  Search,
  X,
} from "lucide-react";
import {
  type ColumnDef,
  type SortingState,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { downloadCSV, label, usePreference } from "./lib";

type View = {
  name: string;
  sorting: SortingState;
  order: string[];
  visibility: VisibilityState;
  filter: string;
};
export function DataTable<T extends object>({
  rows,
  columns,
  account,
  name,
  initialSort = [],
  hidden = [],
  searchPlaceholder = "Search this table...",
  onRow,
  toolbar,
}: {
  rows: T[];
  columns: ColumnDef<T>[];
  account: string;
  name: string;
  initialSort?: SortingState;
  hidden?: string[];
  searchPlaceholder?: string;
  onRow?: (row: T) => void;
  toolbar?: React.ReactNode;
}) {
  const key = `miner:${account}:${name}`;
  const [sorting, setSorting] = usePreference<SortingState>(
    key + ":sort",
    initialSort,
  );
  const [visibility, setVisibility] = usePreference<VisibilityState>(
    key + ":columns",
    Object.fromEntries(hidden.map((k) => [k, false])),
  );
  const [order, setOrder] = usePreference<string[]>(key + ":order", []);
  const [sizes, setSizes] = usePreference<Record<string, number>>(
    key + ":sizes",
    {},
  );
  const [filter, setFilter] = usePreference(key + ":search", "");
  const [views, setViews] = usePreference<View[]>(key + ":views", []);
  const [viewName, setViewName] = useState("");
  const [menu, setMenu] = useState(false);
  const dragged = useRef<string | null>(null);
  const table = useReactTable({
    data: rows,
    columns,
    state: {
      sorting,
      columnVisibility: visibility,
      columnOrder: order,
      columnSizing: sizes,
      globalFilter: filter,
    },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setVisibility,
    onColumnOrderChange: setOrder,
    onColumnSizingChange: setSizes,
    onGlobalFilterChange: setFilter,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    columnResizeMode: "onChange",
    getRowId: (row, index) =>
      String(
        (row as Record<string, unknown>).id ??
          (row as Record<string, unknown>).channel ??
          index,
      ),
    defaultColumn: {
      minSize: 90,
      size: 155,
      maxSize: 600,
      sortUndefined: "last",
    },
  });
  const result = table.getRowModel().rows;
  const [frozen, freeze] = useState<string[] | null>(null);
  const display = useMemo(() => {
    if (!frozen) return result;
    const rank = new Map(frozen.map((id, i) => [id, i]));
    return [...result].sort(
      (a, b) => (rank.get(a.id) ?? 100000) - (rank.get(b.id) ?? 100000),
    );
  }, [result, frozen]);
  function move(id: string, before: string) {
    const current = table
      .getAllLeafColumns()
      .map((c) => c.id)
      .filter((k) => k !== id);
    current.splice(current.indexOf(before), 0, id);
    setOrder(current);
  }
  function shift(id: string, step: number) {
    const current = table.getAllLeafColumns().map((c) => c.id),
      index = current.indexOf(id),
      next = index + step;
    if (next < 0 || next >= current.length) return;
    [current[index], current[next]] = [current[next], current[index]];
    setOrder(current);
  }
  const visible = table.getVisibleLeafColumns();
  return (
    <section className="table-panel" aria-label={label(name) + " table"}>
      <div className="table-toolbar">
        <label className="search">
          <Search size={15} />
          <input
            aria-label={"Search " + name}
            placeholder={searchPlaceholder}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          {filter && (
            <button aria-label="Clear search" onClick={() => setFilter("")}>
              <X size={14} />
            </button>
          )}
        </label>
        {toolbar}
        <span className="row-count">
          {result.length} of {rows.length}
        </span>
        <button
          className="button subtle"
          onClick={() => setMenu(!menu)}
          aria-expanded={menu}
        >
          <Columns3 size={15} />
          Columns & views
          <ChevronDown size={13} />
        </button>
        <button
          className="icon-button"
          aria-label="Export visible rows to CSV"
          title="Export visible columns and filtered rows"
          onClick={() =>
            downloadCSV(
              name + ".csv",
              visible.map((c) =>
                typeof c.columnDef.header === "string"
                  ? c.columnDef.header
                  : c.id,
              ),
              result.map((r) => visible.map((c) => r.getValue(c.id))),
            )
          }
        >
          <Download size={16} />
        </button>
      </div>
      {menu && (
        <div className="column-menu">
          <div>
            <h3>Columns</h3>
            <p className="muted">Drag to reorder, or use the arrow buttons.</p>
            {table.getAllLeafColumns().map((column, i, all) => (
              <div
                className="column-option"
                key={column.id}
                draggable
                onDragStart={() => (dragged.current = column.id)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (dragged.current) move(dragged.current, column.id);
                }}
              >
                <GripVertical size={14} />
                <label>
                  <input
                    type="checkbox"
                    checked={column.getIsVisible()}
                    onChange={column.getToggleVisibilityHandler()}
                    disabled={column.id === "channel"}
                  />
                  {typeof column.columnDef.header === "string"
                    ? column.columnDef.header
                    : label(column.id)}
                </label>
                <button
                  className="icon-button"
                  aria-label={"Move " + column.id + " left"}
                  disabled={i === 0}
                  onClick={() => shift(column.id, -1)}
                >
                  <ArrowUp size={13} />
                </button>
                <button
                  className="icon-button"
                  aria-label={"Move " + column.id + " right"}
                  disabled={i === all.length - 1}
                  onClick={() => shift(column.id, 1)}
                >
                  <ArrowDown size={13} />
                </button>
              </div>
            ))}
          </div>
          <div>
            <h3>Saved views</h3>
            <p className="muted">
              Search, sorting and columns are saved on this browser.
            </p>
            <div className="save-view">
              <input
                aria-label="View name"
                placeholder="Name this view"
                maxLength={40}
                value={viewName}
                onChange={(e) => setViewName(e.target.value)}
              />
              <button
                className="button"
                disabled={!viewName.trim()}
                onClick={() => {
                  setViews([
                    ...views.filter((v) => v.name !== viewName.trim()),
                    {
                      name: viewName.trim(),
                      sorting,
                      order,
                      visibility,
                      filter,
                    },
                  ]);
                  setViewName("");
                }}
              >
                Save view
              </button>
            </div>
            {views.map((view) => (
              <div className="saved-view" key={view.name}>
                <button
                  onClick={() => {
                    setSorting(view.sorting);
                    setOrder(view.order);
                    setVisibility(view.visibility);
                    setFilter(view.filter);
                    setMenu(false);
                  }}
                >
                  {view.name}
                </button>
                <button
                  aria-label={"Delete view " + view.name}
                  onClick={() =>
                    setViews(views.filter((v) => v.name !== view.name))
                  }
                >
                  <X size={14} />
                </button>
              </div>
            ))}
            <button
              className="text-button"
              onClick={() => {
                setSorting(initialSort);
                setVisibility(
                  Object.fromEntries(hidden.map((k) => [k, false])),
                );
                setOrder([]);
                setSizes({});
                setFilter("");
              }}
            >
              Reset table layout
            </button>
          </div>
        </div>
      )}
      <div
        className="table-scroll"
        onPointerEnter={() => freeze(result.map((r) => r.id))}
        onPointerLeave={() => freeze(null)}
      >
        <table style={{ width: table.getTotalSize() }}>
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => (
                  <th
                    key={header.id}
                    style={{ width: header.getSize() }}
                    className={header.column.id === "channel" ? "pinned" : ""}
                    aria-sort={
                      header.column.getIsSorted() === "asc"
                        ? "ascending"
                        : header.column.getIsSorted() === "desc"
                          ? "descending"
                          : "none"
                    }
                  >
                    <button
                      onClick={(e) => {
                        freeze(null);
                        header.column.getToggleSortingHandler()?.(e);
                      }}
                      title="Click to sort. Shift-click to add another sort."
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                      {header.column.getIsSorted() === "asc" ? (
                        <ArrowUp size={12} />
                      ) : header.column.getIsSorted() === "desc" ? (
                        <ArrowDown size={12} />
                      ) : null}
                    </button>
                    <div
                      role="separator"
                      aria-label={"Resize " + header.column.id}
                      aria-orientation="vertical"
                      onMouseDown={header.getResizeHandler()}
                      onTouchStart={header.getResizeHandler()}
                      className="resizer"
                    />
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {display.map((row) => (
              <tr key={row.id} onDoubleClick={() => onRow?.(row.original)}>
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className={cell.column.id === "channel" ? "pinned" : ""}
                    style={{ width: cell.column.getSize() }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {result.length === 0 && (
          <div className="empty">
            <Search size={25} />
            <h3>No matching rows</h3>
            <p>Try another search or clear the active filters.</p>
          </div>
        )}
      </div>
      <div className="table-footer">
        <span>
          {frozen
            ? "Row positions held while you browse"
            : "Live values update automatically"}
        </span>
        <span>Shift-click headers for multiple sorting</span>
      </div>
    </section>
  );
}
