from fairseq.models.m2m_100 import M2M100Model


"""
MachineTranslation class for translating text from a source language to a target language using the M2M100Model.

Attributes:
    source_language (str): The source language for translation.
    target_language (str): The target language for translation.
    model (M2M100Model): The pre-trained M2M100 model for translation.

Methods:
    translate_text(text): Translates the input text from the source language to the target language.
"""
class MachineTranslation:
    def __init__(self, source_language, target_language):
        self.source_language = source_language
        self.target_language = target_language
        self.model = M2M100Model.from_pretrained('ai_models/m2m_100_1.2G.pt')
    
    def translate_text(self, text):
        encoded = self.model.encode(text, self.source_language)
        translated = self.model.generate(**encoded, target_lang=self.target_language)
        return self.model.decode(translated, self.target_language)