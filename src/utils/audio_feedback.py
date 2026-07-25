"""
Audio Feedback für NovaFlow
Spielt einfache Benachrichtigungstöne via sounddevice (plattformunabhängig)
"""
import numpy as np
import sounddevice as sd


class AudioFeedback:
    """Spielt Audio-Feedback Töne ab"""

    SAMPLE_RATE = 44100  # Standard Sample Rate

    @staticmethod
    def play_beep(frequency: int = 800, duration: float = 0.15, volume: float = 0.3) -> None:
        """
        Spielte einen einzelnen Beep-Ton ab

        Args:
            frequency: Frequenz in Hz (default 800)
            duration: Länge in Sekunden (default 0.15)
            volume: Lautstärke 0.0-1.0 (default 0.3)
        """
        try:
            frames = int(AudioFeedback.SAMPLE_RATE * duration)
            t = np.arange(frames) / AudioFeedback.SAMPLE_RATE
            waveform = volume * np.sin(2 * np.pi * frequency * t).astype(np.float32)

            fade_out_frames = int(0.02 * AudioFeedback.SAMPLE_RATE)
            if fade_out_frames > 0:
                fade_out = np.linspace(1, 0, fade_out_frames)
                waveform[-fade_out_frames:] *= fade_out

            sd.play(waveform, samplerate=AudioFeedback.SAMPLE_RATE, blocking=False)
        except Exception as e:
            print(f"Warnung: Audio-Feedback konnte nicht abgespielt werden: {e}")

    @staticmethod
    def play_startup_sound() -> None:
        """Spielt ein kurzes Startup-Signal ab (aufsteigender Ton)"""
        try:
            AudioFeedback.play_beep(frequency=600, duration=0.1, volume=0.25)
            sd.wait()
            AudioFeedback.play_beep(frequency=900, duration=0.15, volume=0.3)
        except Exception:
            pass

    @staticmethod
    def play_recording_start() -> None:
        """Spielt ein Signal ab, wenn Aufnahme startet"""
        try:
            AudioFeedback.play_beep(frequency=1000, duration=0.1, volume=0.4)
        except Exception:
            pass

    @staticmethod
    def play_ready() -> None:
        """Spielt ein Signal ab, wenn NovaFlow wieder aufnahmebereit ist (nach Injektion)"""
        try:
            AudioFeedback.play_beep(frequency=600, duration=0.08, volume=0.25)
        except Exception:
            pass


# Modul-Level Singleton
audio_feedback = AudioFeedback()
