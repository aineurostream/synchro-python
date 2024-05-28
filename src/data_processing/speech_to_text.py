import whisper


"""
Class: SpeechToText

This class represents a speech to text converter. It initializes with a specified language and loads a model using the whisper library. The method speech_to_text takes audio data as input, transcribes it using the loaded model and returns the transcribed text.
"""
class SpeechToText:
    def __init__(self, language):
        self.language = language
        self.model = whisper.load_model("base")

    def speech_to_text(self, audio_data):
        transcript = self.model.transcribe(audio_data, language=self.language)
        return transcript["text"]
        
