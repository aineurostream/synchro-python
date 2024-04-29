import os

from dotenv import load_dotenv

"""
Loads environment variables from the .env file into the current environment.
"""
load_dotenv()


class Configuration:
    """A class for managing the configuration of an application.

    Attributes:
        _env_mode (str): Application environment mode (development, production, etc.).
        _host (str): The host on which the application is running.
        _port (str): The port on which the application is running.
        _audio_device (str): The audio device used for audio input/output.
        _input_language (str): The language in which speech is recognized.
        _output_language (str): The language into which the speech is translated.
        _translation_mode (str): The mode of translation (ru-en, en-ru, etc.).
        _translation_quality (str): Translation quality (standard, high, etc.).
        _translation_speed (str): Translation speed (standard, high, etc.).
        _current_model_translation (str): The current translation model used by the application.
        _api_key (str): API key for accessing translation services.
    """
    def __init__(self):
        """
        Initializes an instance of the Configuration class by loading the values of the environment variables
        environment variables from the .env file or using default values.
        """
        self._env_mode = os.getenv("ENVIRONMENT_MODE", "development")
        self._host = os.getenv("HOST", "localhost")
        self._port = os.getenv("PORT", "8000")
        self._audio_device = os.getenv("AUDIO_DEVICE", "default")
        self._input_language = os.getenv("INPUT_LANGUAGE", "en")
        self._output_language = os.getenv("OUTPUT_LANGUAGE", "ru")
        self._translation_mode = os.getenv("TRANSLATION_MODE", "ru-en")
        self._translation_quality = os.getenv("TRANSLATION_QUALITY", "standard")
        self._translation_speed = os.getenv("TRANSLATION_SPEED", "standard")
        self._current_model_translation = os.getenv("CURRENT_MODEL_TRANSLATION", "seamlessStreaming")
        self._api_key = os.getenv("API_KEY", "default_api_key")


config = Configuration()
