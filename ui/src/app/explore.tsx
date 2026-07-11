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
        body { margin: 0; padding: 0; background: #020205; overflow: hidden; font-family: sans-serif; }
        #map { width: 100vw; height: 100vh; background: #020205; }
        
        .map-animate-in {
          animation: mapZoomIn 2s cubic-bezier(0.25, 1, 0.5, 1) forwards;
          opacity: 0;
          transform: scale(1.1);
        }
        @keyframes mapZoomIn {
          0% { opacity: 0; transform: scale(1.2); filter: blur(10px); }
          100% { opacity: 1; transform: scale(1); filter: blur(0px); }
        }
        
        /* Custom popup styling */
        .leaflet-popup-content-wrapper {
          background: rgba(10, 10, 20, 0.9);
          color: white;
          border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .leaflet-popup-tip {
          background: rgba(10, 10, 20, 0.9);
        }
      </style>
    </head>
    <body>
      <div id="map" class="map-animate-in"></div>
      <script>
        // Initialize map centered on India
        const map = L.map('map', { zoomControl: false, attributionControl: false }).setView([20.5937, 78.9629], 5);
        
        // Dark mode minimal tiles
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png').addTo(map);

        // SVG Icons
        const createSvgIcon = (color) => L.divIcon({
          html: \`<svg width="36" height="36" viewBox="0 0 24 24" fill="rgba(0,0,0,0.5)" stroke="\${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>\`,
          className: '',
          iconSize: [36, 36],
          iconAnchor: [18, 36],
          popupAnchor: [0, -36]
        });

        const redIcon = createSvgIcon('#ff3333');
        const orangeIcon = createSvgIcon('#ffaa00');
        const greenIcon = createSvgIcon('#00ffaa');

        // Flash Flood Zone
        L.marker([19.0760, 72.8777], { icon: redIcon })
          .addTo(map).bindPopup('<b>Mumbai</b><br/>Severe Flash Flooding<br/>Routing: Disabled').openPopup();

        // High Water Level
        L.marker([22.5726, 88.3639], { icon: orangeIcon })
          .addTo(map).bindPopup('<b>Kolkata</b><br/>High Water Level<br/>Routing: Restricted');

        // Safe Zone
        L.marker([28.7041, 77.1025], { icon: greenIcon })
          .addTo(map).bindPopup('<b>Delhi</b><br/>Safe Zone<br/>Routing: Optimal');
          
        // Draw a routing path between Safe Zone and Flood Zone perimeter
        const latlngs = [
          [28.7041, 77.1025],
          [26.2006, 78.1772],
          [23.2599, 77.4126],
          [20.5937, 75.9629]
        ];
        L.polyline(latlngs, { color: '#00ffaa', weight: 3, dashArray: '10, 10' }).addTo(map);
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
