import { getSatelliteMarkerColor } from '../../utils/formatters';

export function createASVMarkerElement(satellitesCount, headingValid = false) {
  const color = getSatelliteMarkerColor(satellitesCount);
  const strokeColor = headingValid ? '#38BDF8' : color;
  
  const el = document.createElement('div');
  el.className = 'asv-marker-container';
  el.style.width = '44px';
  el.style.height = '44px';
  el.style.cursor = 'pointer';
  el.style.display = 'flex';
  el.style.alignItems = 'center';
  el.style.justifyContent = 'center';
  el.style.position = 'relative';

  el.innerHTML = `
    <!-- Pulse radar ring -->
    <div style="position: absolute; width: 44px; height: 44px; border-radius: 50%; background: ${color}; opacity: 0.20; animation: ping 2.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
    
    <!-- Forward Bow Vector Beam (+X Axis) -->
    <div style="position: absolute; top: -10px; width: 2px; height: 12px; background: linear-gradient(to top, ${strokeColor}, transparent); border-radius: 1px;"></div>
    
    <!-- Vessel Hull (Pointed Bow at Top +X, Transom Stern at Bottom -X) -->
    <div style="position: relative; width: 32px; height: 38px; display: flex; align-items: center; justify-content: center; filter: drop-shadow(0 0 8px ${color}80);">
      <svg width="32" height="38" viewBox="0 0 32 38" fill="none" xmlns="http://www.w3.org/2000/svg">
        <!-- Hull Outline -->
        <path d="M16 2 C23 9, 27 18, 27 30 C27 34, 23 35, 16 35 C9 35, 5 34, 5 30 C5 18, 9 9, 16 2 Z" 
              fill="#0B111E" stroke="${color}" stroke-width="2" stroke-linejoin="round"/>
              
        <!-- Forward Cockpit / Sensor Mast (+X indicator) -->
        <path d="M16 8 L20 18 L16 16 L12 18 Z" 
              fill="${strokeColor}" stroke="${strokeColor}" stroke-width="1"/>
              
        <!-- Bow Tip Dot -->
        <circle cx="16" cy="4" r="1.5" fill="#38BDF8"/>
      </svg>
    </div>
  `;

  return el;
}

