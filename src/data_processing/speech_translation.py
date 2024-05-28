from models.seamless_streaming import SeamlessStreamingModel


"""
Class representing a Speech Translation model.

Attributes:
    source_language (str): The source language for translation.
    target_language (str): The target language for translation.
    translation_model (SeamlessStreamingModel): An instance of SeamlessStreamingModel for translation.

Methods:
    __init__: Initializes the SpeechTranslation model with the provided source and target languages.
    translate_speech: Translates the given audio data from the source language to the target language.
"""
class SpeechTranslation:
  def __init__(self, source_language, target_language):
    self.source_language = source_language
    self.target_language = target_language
    self.translation_model = SeamlessStreamingModel()
  
  def translate_speech(self, audio_data):
    translated_text = self.translation_model.translate_speech(
      audio_data, self.source_language, self.target_language
    )
    return translated_text