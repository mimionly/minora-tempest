import { Canvas, useFrame } from '@react-three/fiber/native';
import { useRef, Suspense } from 'react';
import { Mesh, TextureLoader } from 'three';
import { View, StyleSheet } from 'react-native';
import { OrbitControls, useTexture } from '@react-three/drei/native';

function Earth() {
  const earthRef = useRef<Mesh>(null);
  const cloudsRef = useRef<Mesh>(null);
  
  const [colorMap, cloudsMap] = useTexture([
    'https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/earth_atmos_2048.jpg',
    'https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/earth_clouds_1024.png'
  ]);

  const startTime = useRef(Date.now());

  useFrame(() => {
    const elapsed = (Date.now() - startTime.current) * 0.001;
    if (earthRef.current) {
      earthRef.current.rotation.y = elapsed * 0.1;
    }
    if (cloudsRef.current) {
      cloudsRef.current.rotation.y = elapsed * 0.15; // Move faster
      cloudsRef.current.rotation.z = elapsed * 0.03; // Drift slightly
    }
  });

  return (
    <group>
      {/* Earth Sphere - Increased size for better fit */}
      <mesh ref={earthRef}>
        <sphereGeometry args={[2, 64, 64]} />
        <meshStandardMaterial 
          map={colorMap} 
          roughness={0.8}
          metalness={0.0}
        />
      </mesh>
      {/* Clouds Sphere */}
      <mesh ref={cloudsRef}>
        <sphereGeometry args={[2.02, 64, 64]} />
        <meshStandardMaterial 
          map={cloudsMap} 
          transparent={true} 
          opacity={0.9}
          depthWrite={false}
          blending={2} // THREE.AdditiveBlending
          color="#ffffff"
        />
      </mesh>
    </group>
  );
}

export function Globe() {
  return (
    <View style={styles.container}>
      <Canvas camera={{ position: [0, 0, 8.5], fov: 45 }}>
        {/* Bright, even ambient lighting to prevent pitch black shadows */}
        <ambientLight intensity={1.2} color="#ffffff" />
        {/* Main soft sunlight from the front right */}
        <directionalLight position={[5, 3, 5]} intensity={1.0} color="#ffffff" />
        {/* Fill light from the back left to gently illuminate the dark side */}
        <directionalLight position={[-5, 3, -5]} intensity={0.8} color="#ccddff" />
        <Suspense fallback={
          <mesh>
            <sphereGeometry args={[2, 32, 32]} />
            <meshStandardMaterial color="#1a1a1a" />
          </mesh>
        }>
          <Earth />
        </Suspense>
        <OrbitControls enableZoom={false} enablePan={false} autoRotate={false} />
      </Canvas>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    height: '100%',
    backgroundColor: 'transparent',
  },
});
