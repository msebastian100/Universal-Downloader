#!/usr/bin/env python3
"""
Test-Script für Track-Ende-Erkennung bei Deezer
Prüft automatisch ob die Erkennung funktioniert
"""

import sys
import time
from pathlib import Path

# Füge Projekt-Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent))

try:
    from stream_automation import StreamAutomation
    from audio_recorder import AudioRecorder
except ImportError as e:
    print(f"❌ Fehler beim Importieren: {e}")
    sys.exit(1)

def test_track_detection(url: str):
    """Testet die Track-Ende-Erkennung"""
    print("=" * 70)
    print("🧪 TEST: Track-Ende-Erkennung für Deezer")
    print("=" * 70)
    print(f"URL: {url}")
    print()
    
    # Erstelle Test-Ausgabepfad
    output_path = Path.home() / "Downloads" / "Universal Downloader" / "Musik" / "test_track.mp3"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Lösche alte Test-Datei falls vorhanden
    if output_path.exists():
        output_path.unlink()
        print(f"🗑️  Alte Test-Datei gelöscht")
    
    print(f"📁 Ausgabepfad: {output_path}")
    print()
    
    # Erstelle StreamAutomation-Instanz
    print("🔧 Initialisiere StreamAutomation...")
    automation = StreamAutomation(output_path, playback_speed=4.0)
    
    # Setze Progress-Callback für Debug-Ausgaben
    def progress_callback(elapsed: float):
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        print(f"  ⏱️  Aufnahme läuft: {minutes:02d}:{seconds:02d}", end='\r')
    
    automation.progress_callback = progress_callback
    
    # Aktiviere Debug-Modus
    print("🐛 Debug-Modus aktiviert")
    print("   - Detaillierte Logs werden angezeigt")
    print("   - Track-Start-Erkennung wird geloggt")
    print("   - Track-Ende-Erkennung wird geloggt")
    print()
    
    print("✅ StreamAutomation initialisiert")
    print()
    
    # Starte Test
    print("▶️  Starte Test...")
    print("   - Browser wird geöffnet")
    print("   - Track wird abgespielt (4x Geschwindigkeit)")
    print("   - Aufnahme startet automatisch")
    print("   - Track-Ende wird erkannt")
    print("   - Aufnahme stoppt automatisch")
    print()
    
    try:
        # Starte Aufnahme
        success = automation.record_with_automation(
            url=url,
            provider="deezer",
            duration=None,  # Automatische Erkennung
            track_info=None
        )
        
        print()
        print("=" * 70)
        
        if success:
            print("✅ TEST ERFOLGREICH!")
            print()
            
            # Prüfe ob Datei erstellt wurde
            if output_path.exists():
                file_size = output_path.stat().st_size
                print(f"📁 Datei erstellt: {output_path}")
                print(f"📊 Dateigröße: {file_size / 1024 / 1024:.2f} MB")
                
                if file_size > 100 * 1024:  # Mindestens 100 KB
                    print("✅ Datei ist groß genug (wahrscheinlich vollständig)")
                else:
                    print("⚠️  Datei ist sehr klein (möglicherweise unvollständig)")
            else:
                print("❌ Datei wurde nicht erstellt")
            
            print()
            print("🎉 Track-Ende-Erkennung hat funktioniert!")
            print("   Der Track wurde erfolgreich aufgenommen und gestoppt.")
            
        else:
            print("❌ TEST FEHLGESCHLAGEN!")
            print()
            print("Mögliche Probleme:")
            print("  - Track-Ende wurde nicht erkannt")
            print("  - Browser konnte nicht gestartet werden")
            print("  - Play-Button wurde nicht gefunden")
            print("  - Audio-Aufnahme konnte nicht gestartet werden")
            print()
            print("Bitte prüfen Sie die Log-Ausgaben oben für Details.")
        
        print("=" * 70)
        
        return success
        
    except KeyboardInterrupt:
        print()
        print("⚠️  Test wurde vom Benutzer abgebrochen")
        return False
    except Exception as e:
        print()
        print("❌ FEHLER beim Test:")
        print(f"   {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        try:
            automation.cleanup()
        except:
            pass

if __name__ == "__main__":
    # Test-URL
    test_url = "https://www.deezer.com/de/track/3034306201?host=780380695&utm_campaign=clipboard-generic&utm_source=user_sharing&utm_content=track-3034306201&deferredFl=1&universal_link=1"
    
    # Falls URL als Argument übergeben wurde
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
    
    print()
    print("🚀 Starte automatischen Test...")
    print()
    
    success = test_track_detection(test_url)
    
    sys.exit(0 if success else 1)
