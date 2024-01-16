import concurrent.futures
import asyncio

import deepl
from loguru import logger

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException
from time import sleep

# Google Cloud
from google.cloud import texttospeech

from appconfig import AppConfig
from nlp_modules.japanese_nlp import Classifier
import api_keys


class ApiKeyHandler:

    @staticmethod
    def get_deepl_api_key() -> str:
        return api_keys.deepl_api_key


class Transmute:
    logger.add(sink=AppConfig.rekai_log_path)

    # Jisho web scrape and parse
    @staticmethod
    def parse_string_with_jisho(line: str, index: str = 0) -> tuple[str, str]:

        """DOCSTRING PENDING"""

        options = AppConfig.ChromeOptions.options
        driver = webdriver.Chrome(options=options)

        jisho_parsed_html_element = str()

        if Classifier.contains_no_parsable_ja_text(line):
            jisho_parsed_html_element += 'unparsable'

        else:
            url = f'https://jisho.org/search/{line}'

            try:

                logger.info(f'Trying to parse line {index}')

                driver.get(url=url)
                logger.info(f'{index} - Webdriver instance Started')

                zen_bar_element = WebDriverWait(driver, 10).until(ec.visibility_of_element_located((By.ID, "zen_bar")))
                zen_outer_html = zen_bar_element.get_attribute('outerHTML')

                # Selenium also extracts linebreaks that mess with the html when assigned to a string
                zen_html = str(zen_outer_html).replace('\n', "").strip()

                jisho_parsed_html_element += zen_html

            except Exception as e:
                logger.error(f'An exception occured in jisho parse - f{str(e)}')
                zen_html = f'<p>((Text is not parsable or could not be parsed))</p>'
                jisho_parsed_html_element += zen_html

            driver.quit()

            jisho_parsed_html_element = jisho_parsed_html_element.replace('/search/', 'https://jisho.org/search/')
            jisho_parsed_html_element = jisho_parsed_html_element.replace('class="current"', 'class=""')
            jisho_parsed_html_element = jisho_parsed_html_element.replace('class=""', 'class="jisho-link"')

        return (line, jisho_parsed_html_element)


    # DeepL API translation
    @staticmethod
    def translate_string_with_deepl_api(line: str, index: str = 0, source_lang: str = 'JA',
                                        target_lang: str = 'EN-US') -> tuple[str, str]:

        """DOCSTRING PENDING"""

        translator = deepl.Translator(auth_key=ApiKeyHandler.get_deepl_api_key())

        result = translator.translate_text(text=line, source_lang=source_lang, target_lang=target_lang)

        return (line, result.text)

    # Google cloud text-to-speech
    @staticmethod
    def tts_string_with_google_api(line: str) -> tuple[str, bytes]:

        """DOCSTRING PENDING"""

        # Get configration on run
        language_code: str = AppConfig.GoogleTTSConfig.language_code
        ssml_gender = AppConfig.GoogleTTSConfig.ssml_gender
        voice_name: str = AppConfig.GoogleTTSConfig.voice_name
        audio_encoding = AppConfig.GoogleTTSConfig.audio_encoding
        speaking_rate: float = AppConfig.GoogleTTSConfig.speaking_rate
        pitch: float = AppConfig.GoogleTTSConfig.pitch
        volume_gain_db: float = AppConfig.GoogleTTSConfig.volume_gain_db

        tts_client = texttospeech.TextToSpeechClient()
        input_for_synthesis = texttospeech.SynthesisInput({"text": f"{line}"})
        voice_settings = texttospeech.VoiceSelectionParams(
            {
                "language_code": language_code,
                "ssml_gender": ssml_gender,
                "name": voice_name
            }
        )
        audio_configuration = texttospeech.AudioConfig(
            {
                "audio_encoding": audio_encoding,
                "speaking_rate": speaking_rate,
                "pitch": pitch,
                "volume_gain_db": volume_gain_db,
            }
        )
        logger.info(f'TTS_API_CALL: Line: {line}')

        api_response = tts_client.synthesize_speech(
            input=input_for_synthesis,
            voice=voice_settings,
            audio_config=audio_configuration)

        logger.info(f'TTS_API_CALL for {line} was sucessful')

        return (line, api_response.audio_content)
