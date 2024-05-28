import espeak_ng


"""
A class for converting text to speech using the eSpeak NG library.

Attributes:
    language (str): The language in which the text should be spoken.
    tts (espeak_ng.EspeakNG): An instance of the eSpeak NG text-to-speech engine.

Methods:
    text_to_speech(text): Converts the input text to speech in the specified language and returns the audio data.
"""
class TextToSpeech:
    def __init__(self, language):
        self.language = language
        self.tts = espeak_ng.EspeakNG()
    
    def text_to_speech(self, text):
        audio_data = self.tts.synth_wav(text, language=self.language)
        return audio_data