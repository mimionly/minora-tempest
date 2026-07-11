import { Platform, StyleSheet, View, Text } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Globe } from '@/components/Globe';
import Particles from '@/components/Particles';

export default function HomeScreen() {
  return (
    <ThemedView style={styles.container}>
      {/* React Bits Particles Background */}
      <View style={StyleSheet.absoluteFill}>
        {Platform.OS === 'web' && (
          <Particles
            particleColors={['#ffffff']}
            particleCount={800}
            particleSpread={15}
            speed={0.2}
            particleBaseSize={180}
            moveParticlesOnHover={true}
            alphaParticles={false}
            disableRotation={false}
          />
        )}
      </View>

      <SafeAreaView style={styles.safeArea}>
        <View style={styles.content}>
          <View style={styles.leftColumn}>
            <Text style={styles.title}>
              Real-Time{'\n'}Flood <Text style={styles.titleHighlight}>Routing.</Text>
            </Text>
            <Text style={styles.subtitle}>
              A dynamic, zero-pipeline routing engine that computes safe-zone paths in-memory to minimize emergency response times during extreme monsoons.
            </Text>
            
            <View style={styles.buttonGroup}>
              <View style={styles.primaryButton}>
                <Text style={styles.primaryButtonText}>View Live Demo</Text>
              </View>
              <View style={styles.secondaryButton}>
                <Text style={styles.secondaryButtonText}>Download App</Text>
              </View>
            </View>
          </View>
          <View style={styles.rightColumn}>
            <View style={styles.globeWrapper}>
              <Globe />
            </View>
          </View>
        </View>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#020205', // Deep space blue/black
    ...Platform.select({
      web: {
        backgroundImage: 'radial-gradient(circle at 0% 0%, #111122 0%, #020205 50%, #000000 100%)',
      }
    })
  },
  safeArea: {
    flex: 1,
  },
  content: {
    flex: 1,
    flexDirection: Platform.OS === 'web' ? 'row' : 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
    maxWidth: 1200,
    width: '100%',
    alignSelf: 'center',
  },
  leftColumn: {
    flex: 1,
    paddingRight: 40,
    justifyContent: 'center',
    alignItems: 'flex-start',
    zIndex: 10,
  },
  title: {
    fontSize: 72,
    fontWeight: '900',
    lineHeight: 80,
    marginBottom: 24,
    color: '#ffffff',
    letterSpacing: -1,
  },
  titleHighlight: {
    ...Platform.select({
      web: {
        backgroundImage: 'linear-gradient(135deg, #00f0ff 0%, #0055ff 100%)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
      },
      default: {
        color: '#00aaff',
      }
    })
  },
  subtitle: {
    fontSize: 20,
    color: '#a1a1aa',
    textAlign: Platform.OS === 'web' ? 'left' : 'center',
    lineHeight: 28,
    marginBottom: 40,
  },
  buttonGroup: {
    flexDirection: 'row',
    gap: 16,
    alignItems: 'center',
  },
  primaryButton: {
    backgroundColor: '#ffffff',
    paddingHorizontal: 32,
    paddingVertical: 16,
    borderRadius: 100,
    ...Platform.select({
      web: {
        boxShadow: '0 0 20px rgba(255, 255, 255, 0.2)',
        cursor: 'pointer',
      }
    })
  },
  primaryButtonText: {
    color: '#000000',
    fontSize: 16,
    fontWeight: '700',
  },
  secondaryButton: {
    backgroundColor: 'transparent',
    paddingHorizontal: 32,
    paddingVertical: 16,
    borderRadius: 100,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.2)',
    ...Platform.select({
      web: {
        cursor: 'pointer',
      }
    })
  },
  secondaryButtonText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '600',
  },
  rightColumn: {
    flex: 1,
    width: '100%',
    height: '100%',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: 500,
  },
  globeWrapper: {
    width: '100%',
    aspectRatio: 1, // Locks it to a square so 3D aspect ratio never distorts/clips
    backgroundColor: 'transparent',
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
    transform: [{ scale: 1.6 }, { translateX: 80 }], // Scale up heavily and push right
  }
});
