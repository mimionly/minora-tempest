import { Platform, StyleSheet, View, Text } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function ExploreScreen() {
  // We use a completely sandboxed iframe with Leaflet CDN.
  // This bypasses Metro bundler module resolution errors entirely and is extremely fast.
  const mapHtml = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
      <style>
        body { margin: 0; padding: 0; background: #020205; overflow: hidden; font-family: sans-serif; color: white; }
        #map { width: 100vw; height: 100vh; background: #020205; }
        
        .overlay-panel {
          position: absolute;
          top: 20px;
          right: 20px;
          z-index: 1000;
          background: rgba(10, 15, 30, 0.85);
          backdrop-filter: blur(10px);
          border: 1px solid rgba(100, 150, 255, 0.2);
          border-radius: 12px;
          padding: 20px;
          width: 320px;
          box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }
        .overlay-panel h3 { margin: 0 0 15px 0; font-size: 16px; text-transform: uppercase; letter-spacing: 1px; color: #aaccff; }
        .status-row { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 14px; }
        .status-label { color: #8899aa; }
        .status-value { font-weight: bold; }
        
        .btn {
          display: block;
          width: 100%;
          padding: 12px;
          margin-top: 15px;
          background: #0066ff;
          color: white;
          border: none;
          border-radius: 6px;
          font-weight: bold;
          cursor: pointer;
          transition: background 0.2s;
        }
        .btn:hover { background: #0055dd; }
        
        .pulse-warning { animation: pulseRed 2s infinite; }
        @keyframes pulseRed {
          0% { color: #ff3333; text-shadow: 0 0 5px rgba(255,51,51,0.5); }
          50% { color: #ff9999; text-shadow: 0 0 20px rgba(255,51,51,1); }
          100% { color: #ff3333; text-shadow: 0 0 5px rgba(255,51,51,0.5); }
        }
        
        .pulse-safe { animation: pulseGreen 2s infinite; }
        @keyframes pulseGreen {
          0% { color: #00ffaa; text-shadow: 0 0 5px rgba(0,255,170,0.5); }
          50% { color: #88ffcc; text-shadow: 0 0 20px rgba(0,255,170,1); }
          100% { color: #00ffaa; text-shadow: 0 0 5px rgba(0,255,170,0.5); }
        }
        
        /* Animations */
        .dash-anim { animation: dash 20s linear infinite; }
        @keyframes dash { to { stroke-dashoffset: -1000; } }
        
        .water-flow-anim { animation: waterFlow 3s linear infinite; filter: drop-shadow(0 0 5px #00aaff); }
        @keyframes waterFlow { to { stroke-dashoffset: -100; } }
        
        /* Custom popup styling */
        .leaflet-popup-content-wrapper { background: rgba(10, 10, 20, 0.9); color: white; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.1); }
        .leaflet-popup-tip { background: rgba(10, 10, 20, 0.9); }
      </style>
    </head>
    <body>
      <div id="map"></div>
      
      <div class="overlay-panel">
        <h3>Emergency Routing Engine</h3>
        <div class="status-row">
          <span class="status-label">Target:</span>
          <span class="status-value">Mumbai -> Pune</span>
        </div>
        <div class="status-row">
          <span class="status-label">Environment:</span>
          <span class="status-value pulse-warning" id="env-status">Flash Flood Detected</span>
        </div>
        <div class="status-row">
          <span class="status-label">Original Route:</span>
          <span class="status-value" style="color:#ff3333" id="orig-route">Submerged (Impassable)</span>
        </div>
        <div class="status-row" id="safe-route-row" style="display:none;">
          <span class="status-label">Dynamic Route:</span>
          <span class="status-value pulse-safe">Optimal (Bypassing Flood)</span>
        </div>
        
        <button class="btn" id="recalc-btn" onclick="recalculateRoute()">Compute Safe Route</button>
      </div>

      <script>
        const map = L.map('map', { zoomControl: false, attributionControl: false }).setView([18.8, 73.3], 9);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png').addTo(map);

        const createPin = (color) => L.divIcon({
          html: \`<svg width="32" height="32" viewBox="0 0 24 24" fill="\${color}" stroke="#fff" stroke-width="1.5"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/><circle cx="12" cy="9" r="2.5" fill="#fff"/></svg>\`,
          className: '', iconSize: [32, 32], iconAnchor: [16, 32]
        });

        // Mumbai and Pune coordinates (Lng, Lat for OSRM API)
        const start = [72.8777, 19.0760];
        const end = [73.8567, 18.5204];
        const detour = [73.18, 18.65]; // Safe waypoint bypassing flood

        L.marker([start[1], start[0]], { icon: createPin('#0066ff') }).addTo(map).bindPopup('<b>Rescue Fleet HQ (Mumbai)</b>');
        L.marker([end[1], end[0]], { icon: createPin('#00ffaa') }).addTo(map).bindPopup('<b>Target Zone (Pune)</b>');

        let origLines = [], safeLine, floodMarker;

        // Fetch Original Route from OpenStreetMap (OSRM)
        fetch(\`https://router.project-osrm.org/route/v1/driving/\${start[0]},\${start[1]};\${end[0]},\${end[1]}?overview=full&geometries=geojson\`)
          .then(res => res.json())
          .then(data => {
            const coords = data.routes[0].geometry.coordinates.map(c => [c[1], c[0]]);
            
            // Calculate indices for the flooded segment (from 35% to 65% of the route)
            const len = coords.length;
            const floodStart = Math.floor(len * 0.35);
            const floodEnd = Math.floor(len * 0.65);
            
            const preFloodCoords = coords.slice(0, floodStart + 1);
            const floodedCoords = coords.slice(floodStart, floodEnd + 1);
            const postFloodCoords = coords.slice(floodEnd);
            
            // Draw normal impassable sections (muted red)
            origLines.push(L.polyline(preFloodCoords, { color: '#ff3333', weight: 4, dashArray: '10, 15', className: 'dash-anim' }).addTo(map));
            origLines.push(L.polyline(postFloodCoords, { color: '#ff3333', weight: 4, dashArray: '10, 15', className: 'dash-anim' }).addTo(map));
            
            // Draw flooded section (water flowing over the road)
            origLines.push(L.polyline(floodedCoords, { color: '#002244', weight: 10 }).addTo(map)); // Deep water base
            origLines.push(L.polyline(floodedCoords, { color: '#00aaff', weight: 6, dashArray: '15, 15', className: 'water-flow-anim' }).addTo(map)); // Flowing crests
            
            // Add a warning marker exactly at the center of the flooded road
            const centerCoord = coords[Math.floor(len * 0.5)];
            const warningIcon = L.divIcon({
              html: \`<svg width="24" height="24" viewBox="0 0 24 24" fill="#ff3333" stroke="#fff" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>\`,
              className: '', iconSize: [24, 24], iconAnchor: [12, 12], popupAnchor: [0, -12]
            });
            floodMarker = L.marker(centerCoord, { icon: warningIcon })
              .addTo(map)
              .bindPopup('<b>SEVERE FLASH FLOOD</b><br/>Water depth: 1.5m<br/>Highway Submerged & Impassable')
              .openPopup();
          });

        window.recalculateRoute = function() {
          const btn = document.getElementById('recalc-btn');
          btn.innerText = "Computing via OSM Engine...";
          btn.style.background = "#aaaaaa";
          
          // Fetch Safe Route from OpenStreetMap (OSRM) bypassing the flood
          fetch(\`https://router.project-osrm.org/route/v1/driving/\${start[0]},\${start[1]};\${detour[0]},\${detour[1]};\${end[0]},\${end[1]}?overview=full&geometries=geojson\`)
            .then(res => res.json())
            .then(data => {
              btn.style.display = "none";
              document.getElementById('safe-route-row').style.display = "flex";
              document.getElementById('orig-route').style.textDecoration = "line-through";
              document.getElementById('orig-route').style.opacity = "0.5";
              
              const coords = data.routes[0].geometry.coordinates.map(c => [c[1], c[0]]);
              safeLine = L.polyline(coords, {
                color: '#00ffaa', weight: 5, className: 'dash-anim'
              }).addTo(map);
              
              map.fitBounds(safeLine.getBounds(), { padding: [50, 50] });
            });
        };
      </script>
    </body>
    </html>
  `;

  return (
    <View style={styles.container}>
      <SafeAreaView style={styles.header}>
        <Text style={styles.headerTitle}>Live Flood Routing Engine</Text>
        <Text style={styles.headerSubtitle}>Active region: South Asia / India</Text>
      </SafeAreaView>
      
      {Platform.OS === 'web' ? (
        <iframe
          srcDoc={mapHtml}
          style={{ width: '100%', height: '100%', border: 'none' }}
          sandbox="allow-scripts allow-same-origin"
        />
      ) : (
        <View style={styles.nativeFallback}>
          <Text style={{ color: 'white' }}>Map view is only available on web.</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#020205',
  },
  header: {
    padding: 20,
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 100,
    pointerEvents: 'none',
  },
  headerTitle: {
    color: '#ffffff',
    fontSize: 28,
    fontWeight: '900',
    letterSpacing: -0.5,
  },
  headerSubtitle: {
    color: '#aaccff',
    fontSize: 16,
    fontWeight: '600',
  },
  nativeFallback: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  }
});
