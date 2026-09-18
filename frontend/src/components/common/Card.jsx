export function Card({ title, icon: Icon, children, className = '', headerAction }) {
  return (
    <div className={`bg-[#111827]/90 border border-slate-800/80 rounded-xl p-4 shadow-lg backdrop-blur-sm transition-all duration-200 hover:border-slate-700/80 ${className}`}>
      {(title || Icon) && (
        <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800/60">
          <div className="flex items-center gap-2">
            {Icon && <Icon className="w-4 h-4 text-cyan-400" />}
            <h3 className="text-xs font-semibold tracking-wider text-slate-400 uppercase">{title}</h3>
          </div>
          {headerAction && <div>{headerAction}</div>}
        </div>
      )}
      <div>{children}</div>
    </div>
  );
}

export function StatRow({ label, value, unit, highlight = false, alert = false }) {
  return (
    <div className="flex items-center justify-between py-1 text-sm">
      <span className="text-slate-400 text-xs">{label}</span>
      <div className="flex items-baseline gap-1">
        <span className={`font-mono font-medium ${alert ? 'text-rose-400' : highlight ? 'text-cyan-300 font-semibold' : 'text-slate-200'}`}>
          {value !== null && value !== undefined ? value : '--'}
        </span>
        {unit && <span className="text-[11px] text-slate-500 font-normal">{unit}</span>}
      </div>
    </div>
  );
}
