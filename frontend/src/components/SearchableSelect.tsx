import { useState, useEffect, useRef, useCallback } from 'react'
import { Search, Loader2 } from 'lucide-react'

interface SearchableSelectProps<T> {
  value: T | null
  options: T[]
  onChange: (item: T | null) => void
  onSearch: (query: string) => void
  onFocus?: () => void
  loading: boolean
  placeholder: string
  emptyText: string
  renderLabel: (item: T) => string
  renderSublabel?: (item: T) => string
  getKey: (item: T) => string | number
}

export default function SearchableSelect<T>({
  value,
  options,
  onChange,
  onSearch,
  onFocus,
  loading,
  placeholder,
  emptyText,
  renderLabel,
  renderSublabel,
  getKey,
}: SearchableSelectProps<T>) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [highlightIndex, setHighlightIndex] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => {
    return () => clearTimeout(debounceRef.current)
  }, [])

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const handleInput = useCallback((val: string) => {
    setQuery(val)
    setHighlightIndex(-1)
    setOpen(true)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      onSearch(val)
    }, 250)
  }, [onSearch])

  const handleFocus = () => {
    setOpen(true)
    if (onFocus) onFocus()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') { setOpen(true); e.preventDefault() }
      return
    }

    if (e.key === 'ArrowDown') { e.preventDefault(); setHighlightIndex(i => Math.min(i + 1, options.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlightIndex(i => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter') {
      e.preventDefault()
      if (highlightIndex >= 0 && options[highlightIndex]) {
        selectItem(options[highlightIndex])
      }
    } else if (e.key === 'Escape') {
      setOpen(false); inputRef.current?.blur()
    }
  }

  const selectItem = (item: T) => {
    onChange(item)
    setQuery('')
    setOpen(false)
    setHighlightIndex(-1)
    inputRef.current?.blur()
  }

  const showDropdown = open

  return (
    <div ref={containerRef} className="relative">
      {value ? (
        <div className="flex items-center border border-blue-300 bg-blue-50/50 rounded-lg px-3 py-2 text-sm">
          <span className="flex-1 text-slate-900 font-medium truncate">
            {renderLabel(value)}
            {renderSublabel && <span className="text-slate-400 font-normal ml-1.5">{renderSublabel(value)}</span>}
          </span>
          <button
            type="button"
            className="text-slate-400 hover:text-slate-600 ml-2"
            onClick={() => { onChange(null); setQuery(''); setTimeout(() => inputRef.current?.focus(), 0) }}
          >
            ×
          </button>
        </div>
      ) : (
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => handleInput(e.target.value)}
            onFocus={handleFocus}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="border border-slate-200 rounded-lg pl-9 pr-3 py-2 text-sm w-full focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400 bg-white"
            autoComplete="off"
          />
        </div>
      )}

      {showDropdown && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-64 overflow-y-auto">
          {loading && (
            <div className="px-3 py-3 text-sm text-slate-400 text-center">
              <Loader2 className="w-4 h-4 inline animate-spin mr-1.5" />搜索中...
            </div>
          )}
          {!loading && options.length === 0 && query && (
            <div className="px-3 py-3 text-sm text-slate-400 text-center">{emptyText}</div>
          )}
          {!loading && options.length === 0 && !query && (
            <div className="px-3 py-3 text-sm text-slate-400 text-center">输入关键词搜索</div>
          )}
          {!loading && options.map((item, idx) => (
            <button
              key={getKey(item)}
              type="button"
              className={`w-full text-left px-3 py-2 text-sm hover:bg-blue-50 flex items-center gap-2 ${idx === highlightIndex ? 'bg-blue-50' : ''}`}
              onMouseDown={() => selectItem(item)}
              onMouseEnter={() => setHighlightIndex(idx)}
            >
              <span className="flex-1 truncate">{renderLabel(item)}</span>
              {renderSublabel && <span className="text-xs text-slate-400 flex-shrink-0">{renderSublabel(item)}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
