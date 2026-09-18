export function Badge({ children, variant = 'default', size = 'md' }) {
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs';
  
  const variantClasses = {
    success: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    warning: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    danger: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    info: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
    neutral: 'bg-slate-800 text-slate-400 border-slate-700',
    default: 'bg-slate-800/80 text-slate-300 border-slate-700/60'
  }[variant] || 'bg-slate-800 text-slate-300 border-slate-700';

  return (
    <span className={`inline-flex items-center gap-1.5 font-medium border rounded-md font-mono ${sizeClasses} ${variantClasses}`}>
      {children}
    </span>
  );
}
