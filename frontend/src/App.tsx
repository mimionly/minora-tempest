import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, Marker, Popup, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet's default icon issues in bundlers
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Component to dynamically fit map view to GeoJSON content bounds
function MapAutoBounds({ data }: { data: any }) {
  const map = useMap();
  useEffect(() => {
    if (data && data.features && data.features.length > 0) {
      try {
        const geojson = L.geoJSON(data);
        map.fitBounds(geojson.getBounds(), { padding: [100, 100], maxZoom: 15 });
      } catch (e) {
        console.error('Error auto-fitting map bounds:', e);
      }
    }
  }, [data, map]);
  return null;
}

// Component to dynamically track map zoom level
function MapZoomTracker({ onZoomChange }: { onZoomChange: (zoom: number) => void }) {
  const map = useMapEvents({
    zoomend() {
      onZoomChange(map.getZoom());
    },
  });
  return null;
}

function App() {
  const [geoJsonData, setGeoJsonData] = useState<any>(null);
  const [weather, setWeather] = useState<any>(null);
  const [routeStats, setRouteStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMethod, setSelectedMethod] = useState<'method1' | 'method2'>('method1');
  const [zoomLevel, setZoomLevel] = useState<number>(13);
  const [location, setLocation] = useState<string>('Mangaluru, Karnataka, India');
  const [locationInput, setLocationInput] = useState<string>('Mangaluru, Karnataka, India');
  const [currentLevel, setCurrentLevel] = useState<number>(8.2);
  const [normalLevel, setNormalLevel] = useState<number>(5.0);
  const [rain1h, setRain1h] = useState<number>(12.5);
  const [lastFetchedLocation, setLastFetchedLocation] = useState<string>('');

  const fetchMapData = (
    method: 'method1' | 'method2',
    activeLocation: string,
    curLevel?: number,
    normLevel?: number,
    rain?: number
  ) => {
    setLoading(true);
    setError(null);
    
    const finalCurLevel = curLevel !== undefined ? curLevel : currentLevel;
    const finalNormLevel = normLevel !== undefined ? normLevel : normalLevel;
    const finalRain = rain !== undefined ? rain : rain1h;

    const params = new URLSearchParams({
      location: activeLocation,
      method: method,
      current_level: finalCurLevel.toString(),
      normal_level: finalNormLevel.toString(),
      rain_1h: finalRain.toString()
    });
    fetch(`http://localhost:8000/api/simulate?${params.toString()}`)
      .then((res) => {
        if (!res.ok) {
          return res.json().then(errData => {
            throw new Error(errData.error || 'Server error running simulation.');
          });
        }
        return res.json();
      })
      .then((data) => {
        setGeoJsonData(data);
        if (data.weather_metadata) {
          setWeather(data.weather_metadata);
          if (activeLocation !== lastFetchedLocation) {
            setRain1h(data.weather_metadata.rain_1h ?? 0.0);
            setLastFetchedLocation(activeLocation);
          }
        }
        if (data.route_analysis) setRouteStats(data.route_analysis);
        setError(null);
      })
      .catch((err) => {
        console.error(err);
        setError(err.message);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    const delayDebounce = setTimeout(() => {
      fetchMapData(selectedMethod, location, currentLevel, normalLevel, rain1h);
    }, 500);
    return () => clearTimeout(delayDebounce);
  }, [selectedMethod, location, currentLevel, normalLevel, rain1h]);

  // Filter out line/polygon features for standard GeoJSON rendering
  const lineAndPolygonFeatures = geoJsonData
    ? {
        ...geoJsonData,
        features: geoJsonData.features.filter((f: any) => f.geometry.type !== 'Point'),
      }
    : null;

  // Extract points for custom rendering (using high-fidelity CSS + SVG divIcons)
  const pointFeatures = geoJsonData
    ? geoJsonData.features.filter((f: any) => f.geometry.type === 'Point')
    : [];

  const getFeatureStyle = (feature: any) => {
    const props = feature.properties;
    if (!props) return {};

    switch (props.type) {
      case 'flood_zone':
        return {
          fillColor: '#ef4444', // Red overlay for the active hazard/flood zone
          fillOpacity: 0.35,
          color: '#ef4444',
          weight: 2,
        };
      case 'route_before':
        return {
          color: '#10b981', // Clean green for standard route
          weight: 5,
          opacity: 0.6,
        };
      case 'route_after':
        return {
          color: '#3b82f6', // Bright neon blue for recalculated detour route
          weight: 6,
          opacity: 0.9,
          dashArray: '8, 8',
        };
      case 'route_shelter':
        return {
          color: '#8b5cf6', // Violet for shelter transport route
          weight: 5,
          opacity: 0.8,
        };
      case 'waterway':
        return {
          color: '#06b6d4', // Vibrant Cyan/Teal for waterways
          weight: 3.5,
          opacity: 0.85,
        };
      default:
        return {
          color: props.color || '#3b82f6',
          weight: props.width || 3,
          opacity: props.opacity || 0.8,
        };
    }
  };

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }} className={`zoom-level-${zoomLevel}`}>
      {/* Premium Glassmorphic Sidebar */}
      <div className="dashboard-overlay">
        <div className="dashboard-header">
          <h1 className="brand-title">
            <span>⛈️</span> SAHYADRI
          </h1>
          <div className="brand-subtitle">Disaster Routing Suite</div>
        </div>

        <div className="dashboard-content">
          {/* Location Simulator Panel */}
          <div className="widget location-widget">
            <div className="widget-title">
              <span>📍</span> Simulation Location
            </div>
            <div className="location-input-group">
              <input
                type="text"
                className="location-input"
                value={locationInput}
                onChange={(e) => setLocationInput(e.target.value)}
                placeholder="e.g. Venice, Italy"
                disabled={loading}
              />
              <button
                className="location-btn"
                onClick={() => setLocation(locationInput)}
                disabled={loading || !locationInput.trim()}
              >
                {loading ? 'Simulating...' : 'Run Simulation'}
              </button>
            </div>
          </div>

          {/* Status Panel */}
          <div className="widget">
            <div className="widget-title">
              <span>🚨</span> System Status
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '14px',
                fontWeight: 600,
                color: error ? 'var(--danger-color)' : 'var(--success-color)',
              }}
            >
              <div
                style={{
                  width: '10px',
                  height: '10px',
                  borderRadius: '50%',
                  backgroundColor: error ? 'var(--danger-color)' : 'var(--success-color)',
                }}
                className={!error ? 'pulse-animation' : ''}
              />
              {error ? 'Data Sync Error' : 'Live Simulation Sync Active'}
            </div>
            {error && (
              <div style={{ fontSize: '11px', color: 'var(--danger-color)', marginTop: '8px', lineHeight: 1.4 }}>
                {error}
              </div>
            )}
          </div>

          {/* Flood Ingestion Model Selector */}
          <div className="widget">
            <div className="widget-title">
              <span>📡</span> Flood Ingestion Model
            </div>
            <div className="method-selector">
              <button 
                className={`method-card ${selectedMethod === 'method1' ? 'active' : ''}`}
                onClick={() => setSelectedMethod('method1')}
              >
                <div className="method-icon">🛰️</div>
                <div className="method-info">
                  <div className="method-name">Method 1: Satellite SAR</div>
                  <div className="method-desc">Sentinel-1 Radar Imagery</div>
                </div>
              </button>
              <button 
                className={`method-card ${selectedMethod === 'method2' ? 'active' : ''}`}
                onClick={() => setSelectedMethod('method2')}
              >
                <div className="method-icon">🌊</div>
                <div className="method-info">
                  <div className="method-name">Method 2: River Gauge + DEM</div>
                  <div className="method-desc">Gauge surge & elevation mapping</div>
                </div>
              </button>
            </div>
          </div>

          {/* Rainfall Simulator Widget (Method 1 only) */}
          {selectedMethod === 'method1' && (
            <div className="widget">
              <div className="widget-title">
                <span>🌧️</span> Rainfall Simulation
              </div>
              <div className="slider-group">
                <div className="slider-header">
                  <span className="slider-label">Precipitation Rate</span>
                  <span className="slider-val">{rain1h.toFixed(1)} mm/h</span>
                </div>
                <input
                  type="range"
                  className="slider-input"
                  min="0.0"
                  max="50.0"
                  step="0.5"
                  value={rain1h}
                  onChange={(e) => setRain1h(parseFloat(e.target.value))}
                />
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '8px', fontStyle: 'italic' }}>
                Higher rainfall expands waterlogging buffer zones in satellite SAR imaging.
              </div>
            </div>
          )}

          {/* River Gauge Level Widget (Method 2 only) */}
          {selectedMethod === 'method2' && (
            <div className="widget gauge-widget">
              <div className="widget-title">
                <span>📊</span> River Gauge Analytics
              </div>
              <div className="gauge-stats">
                <div className="gauge-row">
                  <span className="gauge-label">Current River Level</span>
                  <span className="gauge-val danger">{currentLevel.toFixed(1)} m</span>
                </div>
                <div className="gauge-row">
                  <span className="gauge-label">Normal Baseline Level</span>
                  <span className="gauge-val secondary">{normalLevel.toFixed(1)} m</span>
                </div>
                <div className="gauge-divider" />
                <div className="gauge-row highlight">
                  <span className="gauge-label">Active Water Surge</span>
                  <span className={`gauge-val ${currentLevel > normalLevel ? 'warning' : 'secondary'}`}>
                    {currentLevel > normalLevel ? '+' : ''}{(currentLevel - normalLevel).toFixed(1)} m
                  </span>
                </div>
              </div>

              {/* Interactive sliders for Method 2 parameters */}
              <div className="slider-group" style={{ marginTop: '16px' }}>
                <div className="slider-header">
                  <span className="slider-label">Simulated Current Level</span>
                  <span className="slider-val">{currentLevel.toFixed(1)} m</span>
                </div>
                <input
                  type="range"
                  className="slider-input"
                  min="0.0"
                  max="15.0"
                  step="0.1"
                  value={currentLevel}
                  onChange={(e) => setCurrentLevel(parseFloat(e.target.value))}
                />
              </div>

              <div className="slider-group" style={{ marginTop: '12px' }}>
                <div className="slider-header">
                  <span className="slider-label">Simulated Baseline Level</span>
                  <span className="slider-val">{normalLevel.toFixed(1)} m</span>
                </div>
                <input
                  type="range"
                  className="slider-input"
                  min="0.0"
                  max="10.0"
                  step="0.1"
                  value={normalLevel}
                  onChange={(e) => setNormalLevel(parseFloat(e.target.value))}
                />
              </div>

              <div className="gauge-footer-note" style={{ marginTop: '12px' }}>
                DEM spreads surge water across regions under {currentLevel.toFixed(1)}m elevation.
              </div>
            </div>
          )}

          {/* Live Weather Widget */}
          {weather && (
            <div className="widget">
              <div className="widget-title">
                <span>🌦️</span> Live Weather Ingestion
              </div>
              <div className="weather-grid">
                <div className="stat-box">
                  <span className="stat-label">Temp</span>
                  <span className="stat-val">{weather.temp?.toFixed(1)}°C</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Humidity</span>
                  <span className="stat-val">{weather.humidity}%</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Wind</span>
                  <span className="stat-val">{weather.wind_speed?.toFixed(1)} m/s</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Rainfall</span>
                  <span className="stat-val" style={{ color: weather.rain_1h > 0 ? 'var(--warning-color)' : 'white' }}>
                    {weather.rain_1h?.toFixed(1)} mm/h
                  </span>
                </div>
                <div className="weather-desc">{weather.description}</div>
              </div>
            </div>
          )}

          {/* Route Metrics Widget */}
          {routeStats && (
            <div className="widget">
              <div className="widget-title">
                <span>📊</span> Navigation & Cost Metrics
              </div>
              <div className="metrics-row">
                <span>Normal Est. Time:</span>
                <span className="metric-highlight" style={{ color: 'var(--success-color)' }}>
                  {(routeStats.cost_before / 60).toFixed(1)} mins
                </span>
              </div>
              <div className="metrics-row">
                <span>Detour Est. Time:</span>
                <span className="metric-highlight" style={{ color: routeStats.time_increase_pct > 0 ? 'var(--warning-color)' : 'var(--accent-color)' }}>
                  {(routeStats.cost_after / 60).toFixed(1)} mins
                </span>
              </div>
              <div className="metrics-row">
                <span>Route Delay:</span>
                <span
                  className="metric-highlight"
                  style={{
                    color: routeStats.time_increase_pct > 0 ? 'var(--danger-color)' : 'var(--success-color)',
                  }}
                >
                  +{routeStats.time_increase_pct?.toFixed(1)}%
                </span>
              </div>
            </div>
          )}

          {/* Map Layer Legend Widget */}
          <div className="widget">
            <div className="widget-title">
              <span>🗺️</span> Map Layers
            </div>
            <div className="legend-list">
              <div className="legend-item">
                <div className="legend-color-line" style={{ backgroundColor: '#10b981' }} />
                <span>Normal Safe Route</span>
              </div>
              <div className="legend-item">
                <div
                  className="legend-color-line"
                  style={{
                    borderTop: '3px dashed #3b82f6',
                    height: 0,
                    width: '32px',
                  }}
                />
                <span>Active Detour Route</span>
              </div>
              <div className="legend-item">
                <div className="legend-color-line" style={{ backgroundColor: '#8b5cf6' }} />
                <span>Shelter Transport Route</span>
              </div>
              <div className="legend-item">
                <div
                  className="legend-color-poly"
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.25)',
                    borderColor: '#ef4444',
                  }}
                />
                <span>Active Flood Polygon</span>
              </div>
              <div className="legend-item">
                <div className="legend-color-line" style={{ backgroundColor: '#06b6d4' }} />
                <span>OSM Waterway (Riverbed)</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Interactive Controls */}
      <div className="map-controls-panel">
        <button className="control-btn" onClick={() => fetchMapData(selectedMethod, location, currentLevel, normalLevel, rain1h)} disabled={loading}>
          <span>🔄</span> {loading ? 'Syncing...' : 'Sync Live Data'}
        </button>
      </div>
      

      {/* Leaflet Map Area */}
      <MapContainer center={[12.8717, 74.8463]} zoom={13} zoomControl={false} scrollWheelZoom={true}>
        <MapZoomTracker onZoomChange={setZoomLevel} />
        {/* Dark-theme Map Tiles */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        {/* Vector Line and Polygon Features */}
        {lineAndPolygonFeatures && (
          <GeoJSON 
            key={JSON.stringify(lineAndPolygonFeatures)} 
            data={lineAndPolygonFeatures} 
            style={getFeatureStyle} 
          />
        )}

        {/* Custom Point Markers */}
        {pointFeatures.map((feature: any, index: number) => {
          const [lon, lat] = feature.geometry.coordinates;
          const props = feature.properties;

          let iconHtml = '📍';

          switch (props.type) {
            case 'incident':
              iconHtml = '<span style="font-size: 20px;">🚨</span>';
              break;
            case 'rescue_station':
              iconHtml = '<span style="font-size: 20px;">🛡️</span>';
              break;
            case 'hospital':
              iconHtml = '<span class="hospital-marker">+</span>';
              break;
            case 'shelter':
              iconHtml = '<span class="shelter-marker">-</span>';
              break;
          }

          const customIcon = L.divIcon({
            html: `
              <div class="map-marker-container">
                <div class="${props.type === 'incident' ? 'pulse-animation' : ''}">
                  ${iconHtml}
                </div>
              </div>
            `,
            className: 'custom-marker-icon',
            iconSize: [32, 32],
            iconAnchor: [16, 16],
            popupAnchor: [0, -16],
          });

          return (
            <Marker key={index} position={[lat, lon]} icon={customIcon}>
              <Popup>
                <div style={{ fontFamily: 'Outfit, sans-serif' }}>
                  <h3 style={{ margin: '0 0 4px 0', fontSize: '15px', fontWeight: 600 }}>{props.name}</h3>
                  <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                    Type:{' '}
                    <span style={{ textTransform: 'capitalize', color: 'white' }}>{props.type.replace('_', ' ')}</span>
                  </p>
                  {props.capacity && (
                    <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#94a3b8' }}>
                      Capacity: <span style={{ color: '#10b981', fontWeight: 600 }}>{props.capacity}</span>
                    </p>
                  )}
                  {props.severity && (
                    <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#94a3b8' }}>
                      Severity: <span style={{ color: '#ef4444', fontWeight: 600 }}>{props.severity}</span>
                    </p>
                  )}
                </div>
              </Popup>
            </Marker>
          );
        })}

        {/* Fits bounds automatically when data changes */}
        {geoJsonData && <MapAutoBounds data={geoJsonData} />}
      </MapContainer>
    </div>
  );
}

export default App;
